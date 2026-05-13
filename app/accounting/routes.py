from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file, session, current_app
from flask_login import login_required, current_user
import pyodbc
from io import BytesIO
import xlsxwriter
from datetime import date, timedelta, datetime
from decimal import Decimal, InvalidOperation
from collections import OrderedDict

acc = Blueprint('accounting', __name__, url_prefix='/accounting')

# DB connection string (move to config for production)
CONN_STR = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;'

def fetch_rows_as_dicts(cursor):
    cols = [col[0] for col in cursor.description]
    rows = cursor.fetchall()
    return [dict(zip(cols, row)) for row in rows]

def _compute_prev_month_start_and_current_month_end():
    today = date.today()
    first_of_this_month = today.replace(day=1)
    prev_month_end = first_of_this_month - timedelta(days=1)
    prev_month_start = prev_month_end.replace(day=1)
    first_of_next_month = (first_of_this_month + timedelta(days=32)).replace(day=1)
    current_month_end = first_of_next_month - timedelta(days=1)
    return prev_month_start.isoformat(), current_month_end.isoformat()

def _apply_filters_from_request(base_sql, params, where_clauses, use_defaults=True):
    qs_cost_center = request.args.get('cost_center')
    qs_actual_code = request.args.get('actual_code')  # 추가
    qs_billing_start = request.args.get('billing_start')
    qs_billing_end = request.args.get('billing_end')
    qs_key_start = request.args.get('key_start')
    qs_key_end = request.args.get('key_end')

    # normalize empty / whitespace-only values to None
    if isinstance(qs_cost_center, str):
        qs_cost_center = qs_cost_center.strip() or None
    if isinstance(qs_billing_start, str):
        qs_billing_start = qs_billing_start.strip() or None
    if isinstance(qs_billing_end, str):
        qs_billing_end = qs_billing_end.strip() or None
    if isinstance(qs_key_start, str):           
        qs_key_start = qs_key_start.strip() or None
    if isinstance(qs_key_end, str):
        qs_key_end = qs_key_end.strip() or None

        # <-- 여기에 추가 -->
    if isinstance(qs_actual_code, str):
        qs_actual_code = qs_actual_code.strip() or None

    if use_defaults:
        billing_default_start, billing_default_end = _compute_prev_month_start_and_current_month_end()
        effective_billing_start = qs_billing_start or billing_default_start
        effective_billing_end = qs_billing_end or billing_default_end
        effective_key_start = qs_key_start
        effective_key_end = qs_key_end
    else:
        effective_billing_start = qs_billing_start
        effective_billing_end = qs_billing_end
        effective_key_start = qs_key_start
        effective_key_end = qs_key_end

    # only add cost_center filter when a non-empty value was provided
    if qs_cost_center is not None:
        where_clauses.append("COST_CENTER = ?")
        params.append(qs_cost_center)

    if qs_actual_code is not None:  # 추가
        where_clauses.append("Actual_Code = ?")
        params.append(qs_actual_code)

    if effective_billing_start:
        where_clauses.append("BILLING_DATE >= ?")
        params.append(effective_billing_start)

    if effective_billing_end:
        where_clauses.append("BILLING_DATE <= ?")
        params.append(effective_billing_end)

    if effective_key_start:
        where_clauses.append("KEY_DATE >= ?")
        params.append(effective_key_start)

    if effective_key_end:
        where_clauses.append("KEY_DATE <= ?")
        params.append(effective_key_end)

    if where_clauses:
        base_sql += " WHERE " + " AND ".join(where_clauses)
    base_sql += " ORDER BY BILLING_DATE DESC"
    return base_sql, params

def get_flash_message(key, session_lang='ko'):
    messages = {
        'saved': {
            'ko': '저장되었습니다.',
            'en': 'Saved successfully.',
            'th': 'บันทึกเรียบร้อยแล้ว'
        },
        'updated': {
            'ko': '수정되었습니다.',
            'en': 'Updated successfully.',
            'th': 'อัปเดตเรียบร้อยแล้ว'
        },
        'deleted': {
            'ko': '삭제되었습니다.',
            'en': 'Deleted successfully.',
            'th': 'ลบเรียบร้อยแล้ว'
        }
    }
    return messages.get(key, {}).get(session_lang, messages[key]['ko'])

def parse_number(value):
    """Normalize numeric input from request form.

    - Accepts strings like "533,580.82" and returns Decimal('533580.82').
    - Returns None for empty/None inputs or when parsing fails.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == '':
        return None
    # remove common thousands separators and non-breaking spaces
    s = s.replace(',', '').replace('\u00A0', '')
    try:
        return Decimal(s)
    except InvalidOperation:
        return None

# LIST - /accounting/actual
@acc.route('/actual')
@login_required
def account_actual_list():
    billing_start_default, billing_end_default = _compute_prev_month_start_and_current_month_end()
    conn = None
    cursor = None
    items = []
    
    # 페이징 파라미터 처리
    page = request.args.get('page', 1, type=int)
    per_page = 20  # 페이지당 항목 수
    offset = (page - 1) * per_page
    
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        # include vendor name AND account name via LEFT JOINs
        # Use session language to pick the right account name column
        lang = session.get('language', 'en')
        if lang == 'ko':
            account_name_col = 'ac.NAME_KO'
        elif lang == 'th':
            account_name_col = 'ac.NAME_TH'
        else:
            account_name_col = 'ac.NAME_EN'
        
        base_sql = (f"SELECT a.*, v.vd_name AS partner_name, {account_name_col} AS account_name "
                    "FROM Account_Actual a "
                    "LEFT JOIN code_vendor_expense v "
                    "  ON a.PARTNER = v.vd_code AND a.PARTNER IS NOT NULL "
                    "LEFT JOIN code_Account ac "
                    "  ON a.Actual_Code = ac.account_code AND a.Actual_Code IS NOT NULL")
        where_clauses = []
        params = []
        # apply filters and use defaults for billing only; key_date has no default
        base_sql, params = _apply_filters_from_request(base_sql, params, where_clauses, use_defaults=True)

        # 전체 개수 조회 (페이징을 위해)
        count_sql = base_sql.replace(f"SELECT a.*, v.vd_name AS partner_name, {account_name_col} AS account_name", "SELECT COUNT(*)")
        count_sql = count_sql.replace(" ORDER BY BILLING_DATE DESC", "")
        
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()[0]

        # 전체 PAYMENT, BEFORE_VAT_AMT, VAT_AMOUNT, WHT_AMOUNT 합계 계산
        sum_sql = base_sql.replace(
            f"SELECT a.*, v.vd_name AS partner_name, {account_name_col} AS account_name",
            "SELECT ISNULL(SUM(a.PAYMENT), 0), ISNULL(SUM(a.BEFORE_VAT_AMT), 0), ISNULL(SUM(a.VAT_AMOUNT), 0), ISNULL(SUM(a.WHT_AMOUNT), 0)"
        )
        sum_sql = sum_sql.replace(" ORDER BY BILLING_DATE DESC", "")
        cursor.execute(sum_sql, params)
        sum_result = cursor.fetchone()
        total_payment = sum_result[0] or 0
        total_before_vat = sum_result[1] or 0
        total_vat = sum_result[2] or 0
        total_wht = sum_result[3] or 0

        # 페이징을 위한 OFFSET, FETCH 추가
        base_sql += f" OFFSET {offset} ROWS FETCH NEXT {per_page} ROWS ONLY"

        # DEBUG: 로그 출력 — 실제 SQL, 파라미터, 요청 쿼리스트링 확인
        try:
            # use INFO so messages appear when running under waitress
            current_app.logger.info("REQUEST ARGS: %s", dict(request.args))
            current_app.logger.info("ACCOUNT_ACTUAL SQL: %s", base_sql)
            current_app.logger.info("ACCOUNT_ACTUAL PARAMS: %r", params)
            current_app.logger.info("TOTAL_COUNT: %d, PAGE: %d, OFFSET: %d", total_count, page, offset)
            # also print to stdout for immediate visibility
            print("REQUEST ARGS:", dict(request.args))
            print("ACCOUNT_ACTUAL SQL:", base_sql)
            print("ACCOUNT_ACTUAL PARAMS:", params)
            print(f"TOTAL_COUNT: {total_count}, PAGE: {page}, OFFSET: {offset}")
        except Exception:
            pass

        cursor.execute(base_sql, params)
        items = fetch_rows_as_dicts(cursor)

        # 템플릿에서 사용하는 키가 DB 컬럼명 대소문자/스네이크/캠멜 형태로 섞여 있을 수 있으므로
        # 화면에 보일 'PAYMENT_METHOD'와 'partner_name' 키를 항상 존재하도록 정규화합니다.
        for r in items:
            # PAYMENT_METHOD 보장 (우선순위: 다양한 가능한 키 확인)
            pm = None
            for k in ('PAYMENT_METHOD', 'payment_method', 'PaymentMethod', 'paymentMethod'):
                if k in r and r.get(k) not in (None, ''):
                    pm = r.get(k)
                    break
            r['PAYMENT_METHOD'] = pm or ''

            # partner_name 보장 (partner_name 우선, 없으면 PARTNER_NAME 또는 partner 사용)
            r['partner_name'] = (r.get('partner_name') or r.get('PARTNER_NAME') or r.get('partner') or '')

        # 페이징 정보 계산
        total_pages = (total_count + per_page - 1) // per_page  # 올림 계산
        has_prev = page > 1
        has_next = page < total_pages
        prev_num = page - 1 if has_prev else None
        next_num = page + 1 if has_next else None

        # 페이지 번호 리스트 생성 (현재 페이지 주변 5개 페이지)
        def iter_pages(current_page, total_pages, left_edge=2, left_current=2, right_current=3, right_edge=2):
            pages = []
            for num in range(1, total_pages + 1):
                if (num <= left_edge or 
                    (current_page - left_current - 1 < num < current_page + right_current) or 
                    num > total_pages - right_edge):
                    pages.append(num)
            
            result = []
            last = 0
            for num in pages:
                if last + 1 != num:
                    result.append(None)  # 구분자 (...)
                result.append(num)
                last = num
            return result

        pagination_info = {
            'page': page,
            'per_page': per_page,
            'total': total_count,
            'pages': total_pages,
            'has_prev': has_prev,
            'has_next': has_next,
            'prev_num': prev_num,
            'next_num': next_num,
            'iter_pages': lambda: iter_pages(page, total_pages)
        }

        # DEBUG: 반환 행 수 및 샘플 행 로깅
        try:
            current_app.logger.debug("ACCOUNT_ACTUAL fetched rows: %d", len(items))
            if items:
                current_app.logger.debug("ACCOUNT_ACTUAL first row sample: %s", items[0])
        except Exception:
            pass

    except Exception as e:
        current_app.logger.error(f"Error fetching account actual list: {e}")
        items = []
        pagination_info = None
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

    return render_template(
        'accounting/actual/list.html',
        items=items,
        pagination=pagination_info,
        request_args=request.args,
        billing_start_default=billing_start_default,
        billing_end_default=billing_end_default,
        total_payment=total_payment,
        total_before_vat=total_before_vat,    # ← 추가
        total_vat=total_vat,                  # ← 추가
        total_wht=total_wht,                  # ← 추가
        # key defaults intentionally empty
        key_start_default='',
        key_end_default=''
    )

# CREATE - /accounting/actual/add
@acc.route('/actual/options')
@login_required
def account_options():
    """Return account options for expense_code selector."""
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute("SELECT CONCAT([account_code],' - ', [NAME_EN]) AS NAME_EN, [account_code] FROM dbo.code_Account ORDER BY [account_code]")
        rows = cursor.fetchall()
        data = []
        for r in rows:
            name_en = r[0] if r[0] is not None else ''
            code = r[1] if r[1] is not None else ''
            data.append({'account_code': code, 'NAME_EN': name_en})
        cursor.close()
        conn.close()
        return jsonify(data)
    except Exception as e:
        current_app.logger.error(f"Failed to load account options: {e}")
        return jsonify([]), 500

@acc.route('/actual/add', methods=['GET', 'POST'])
@login_required
def account_actual_add():
    if request.method == 'POST':
        id_val          = request.form.get('id')
        cost_center     = request.form.get('cost_center')
        actual_type     = request.form.get('actual_type')
        actual_code     = request.form.get('actual_code')
        billing_date    = request.form.get('billing_date') or None
        key_date        = date.today().isoformat()

        # 금액/비율 필드 파싱
        before_vat_amt  = parse_number(request.form.get('before_vat_amt'))
        vat_type        = request.form.get('vat_type')
        vat_rate        = parse_number(request.form.get('vat_rate'))
        vat_amount      = parse_number(request.form.get('vat_amount'))
        wht_rate        = parse_number(request.form.get('wht_rate'))
        wht_amount      = parse_number(request.form.get('wht_amount'))
        payment         = parse_number(request.form.get('payment'))

        payer           = request.form.get('payer') or None
        partner         = request.form.get('partner') or None
        partner_account = request.form.get('partner_account') or None
        payment_method  = request.form.get('payment_method') or None  # 새로 추가
        remark          = request.form.get('remark')
        created_by      = getattr(current_user, 'username', None) or str(current_user.get_id() or '')
        create_date     = datetime.now()

        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO Account_Actual (
                ID, COST_CENTER, Actual_TYPE, Actual_Code, BILLING_DATE, KEY_DATE,
                BEFORE_VAT_AMT, VAT_TYPE, VAT_RATE, VAT_AMOUNT, WHT_RATE, WHT_AMOUNT,
                PAYMENT, payer, partner, partner_account, payment_method, REMARK, created_by, create_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            id_val, cost_center, actual_type, actual_code, billing_date, key_date,
            before_vat_amt, vat_type, vat_rate, vat_amount, wht_rate, wht_amount,
            payment, payer, partner, partner_account, payment_method, remark, created_by, create_date
        ))
        conn.commit()
        cursor.close()
        conn.close()

        user_lang = session.get('language', 'ko')
        flash(get_flash_message('saved', user_lang) or '저장되었습니다.', 'Info')
        return redirect(url_for('accounting.account_actual_list'))

    # GET: compute next id and provide defaults
    next_id = ''
    default_wht_rate = 0
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute("SELECT MAX(TRY_CAST(ID AS INT)) FROM Account_Actual")
        row = cursor.fetchone()
        max_id = row[0] if row and row[0] is not None else 0
        try:
            next_id = int(max_id) + 1
        except Exception:
            # if ID not integer, fall back to empty
            next_id = ''
        cursor.close()
        conn.close()
    except Exception as e:
        current_app.logger.error(f"Failed to compute next ID: {e}")
        next_id = ''

    return render_template('accounting/actual/new.html',
                           next_id=next_id,
                           default_wht_rate=default_wht_rate)

# EDIT - /accounting/actual/edit/<id_val>
@acc.route('/actual/edit/<id_val>', methods=['GET', 'POST'])
@login_required
def account_actual_edit(id_val):
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    if request.method == 'POST':
        cost_center     = request.form.get('cost_center')
        actual_type     = request.form.get('actual_type')
        actual_code     = request.form.get('actual_code')
        billing_date    = request.form.get('billing_date') or None
        key_date        = request.form.get('key_date') or None

        # 금액/비율 필드 파싱
        before_vat_amt  = parse_number(request.form.get('before_vat_amt'))
        vat_type        = request.form.get('vat_type')
        vat_rate        = parse_number(request.form.get('vat_rate'))
        vat_amount      = request.form.get('vat_amount')
        wht_rate        = parse_number(request.form.get('wht_rate'))
        wht_amount      = request.form.get('wht_amount')
        payment         = parse_number(request.form.get('payment'))

        payer           = request.form.get('payer') or None
        partner         = request.form.get('partner') or None
        partner_account = request.form.get('partner_account') or None
        payment_method  = request.form.get('payment_method') or None  # 새로 추가
        remark          = request.form.get('remark')

        cursor.execute("""
            UPDATE Account_Actual
            SET COST_CENTER=?, Actual_TYPE=?, Actual_Code=?, BILLING_DATE=?, KEY_DATE=?,
                BEFORE_VAT_AMT=?, VAT_TYPE=?, VAT_RATE=?, VAT_AMOUNT=?, WHT_RATE=?, WHT_AMOUNT=?,
                PAYMENT=?, payer=?, partner=?, partner_account=?, payment_method=?, REMARK=?
            WHERE ID=?
        """, (
            cost_center, actual_type, actual_code, billing_date, key_date,
            before_vat_amt, vat_type, vat_rate, vat_amount, wht_rate, wht_amount,
            payment, payer, partner, partner_account, payment_method, remark, id_val
        ))
        conn.commit()
        cursor.close()
        conn.close()

        user_lang = session.get('language', 'ko')
        flash(get_flash_message('updated', user_lang) or '수정되었습니다.', 'Info')
        return redirect(url_for('accounting.account_actual_list'))

    # GET: load item
    cursor.execute("SELECT * FROM Account_Actual WHERE ID=?", (id_val,))
    rows = fetch_rows_as_dicts(cursor)
    cursor.close()
    conn.close()

    if not rows:
        return render_template('errors/404.html'), 404

    item = rows[0]
    return render_template('accounting/actual/edit.html', item=item)

# DELETE - /accounting/actual/delete/<id_val>
@acc.route('/actual/delete/<id_val>', methods=['POST'])
@login_required
def account_actual_delete(id_val):
    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM Account_Actual WHERE ID=?", (id_val,))
    conn.commit()
    cursor.close()
    conn.close()
    user_lang = session.get('language', 'ko')
    flash(get_flash_message('deleted', user_lang) or '삭제되었습니다.', 'Info')
    return redirect(url_for('accounting.account_actual_list'))

# EXCEL - /accounting/actual/excel
@acc.route('/actual/excel')
@login_required
def account_actual_excel():
    conn = None
    cursor = None
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        # include partner_name via LEFT JOIN
        base_sql = ("SELECT a.*, v.vd_name AS partner_name "
                    "FROM Account_Actual a "
                    "LEFT JOIN code_vendor_expense v "
                    "  ON COALESCE(a.PARTNER, '') = COALESCE(v.vd_code, '')")
        where_clauses = []
        params = []

        base_sql, params = _apply_filters_from_request(base_sql, params, where_clauses, use_defaults=True)

        cursor.execute(base_sql, params)
        rows = fetch_rows_as_dicts(cursor)

        # Build Excel in-memory
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('AccountActual')

        # formats
        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0'})
        num_fmt = workbook.add_format({'num_format': '#,##0.00'})
        pct_fmt = workbook.add_format({'num_format': '0.00'})

        headers = [
            'ID', 'Cost Center', 'Actual Type', 'Actual Code',
            'Billing Date', 'Key Date', 'Before VAT', 'VAT Amount', 'WHT Amount',
            'Payment', 'VAT Type', 'VAT Rate', 'WHT Rate',
            'Payer', 'Partner', 'Partner Account', 'Payment Method', 'Remark', 'Created By'
        ]
        for c, h in enumerate(headers):
            ws.write(0, c, h, header_fmt)

        for r_idx, r in enumerate(rows, start=1):
            ws.write(r_idx, 0, r.get('ID'))
            ws.write(r_idx, 1, r.get('COST_CENTER'))
            ws.write(r_idx, 2, r.get('Actual_TYPE'))
            ws.write(r_idx, 3, r.get('Actual_Code'))
            ws.write(r_idx, 4, str(r.get('BILLING_DATE')) if r.get('BILLING_DATE') is not None else '')
            ws.write(r_idx, 5, str(r.get('KEY_DATE')) if r.get('KEY_DATE') is not None else '')

            # BEFORE_VAT_AMT
            before_vat = r.get('BEFORE_VAT_AMT')
            if before_vat is not None:
                try:
                    ws.write_number(r_idx, 6, float(before_vat), num_fmt)
                except:
                    ws.write(r_idx, 6, before_vat)
            else:
                ws.write(r_idx, 6, '')

            # VAT_AMOUNT
            vat_amount = r.get('VAT_AMOUNT')
            if vat_amount is not None:
                try:
                    ws.write_number(r_idx, 7, float(vat_amount), num_fmt)
                except:
                    ws.write(r_idx, 7, vat_amount)
            else:
                ws.write(r_idx, 7, '')

            # WHT_AMOUNT
            wht_amount = r.get('WHT_AMOUNT')
            if wht_amount is not None:
                try:
                    ws.write_number(r_idx, 8, float(wht_amount), num_fmt)
                except:
                    ws.write(r_idx, 8, wht_amount)
            else:
                ws.write(r_idx, 8, '')

            # PAYMENT
            payment = r.get('PAYMENT')
            if payment is not None:
                try:
                    ws.write_number(r_idx, 9, float(payment), num_fmt)
                except:
                    ws.write(r_idx, 9, payment)
            else:
                ws.write(r_idx, 9, '')

            ws.write(r_idx, 10, r.get('VAT_TYPE') or '')
            
            # VAT_RATE
            vr = r.get('VAT_RATE')
            if vr is not None:
                try:
                    ws.write_number(r_idx, 11, float(vr), pct_fmt)
                except:
                    ws.write(r_idx, 11, vr)
            else:
                ws.write(r_idx, 11, '')

            # WHT_RATE
            wr = r.get('WHT_RATE')
            if wr is not None:
                try:
                    ws.write_number(r_idx, 12, float(wr), pct_fmt)
                except:
                    ws.write(r_idx, 12, wr)
            else:
                ws.write(r_idx, 12, '')

            ws.write(r_idx, 13, r.get('payer') or '')
            # prefer partner_name (joined from code_vendor_expense) if available
            ws.write(r_idx, 14, r.get('partner_name') or r.get('partner') or '')
            ws.write(r_idx, 15, r.get('partner_account') or '')
            ws.write(r_idx, 16, r.get('payment_method') or '')  # 새로 추가
            ws.write(r_idx, 17, r.get('REMARK') or '')
            ws.write(r_idx, 18, r.get('created_by') or '')

        workbook.close()
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        exporter = getattr(current_user, 'username', None) or str(current_user.get_id() or '')
        exporter_safe = str(exporter).replace(' ', '_')
        filename = f'account_actual_list_{timestamp}_{exporter_safe}.xlsx'
        return send_file(
            output,
            as_attachment=True,
            download_name=filename,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )

    except Exception as e:
        current_app.logger.error(f"Excel export failed: {e}")
        return jsonify({'error': 'excel_failed'}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

 # REPORT - /accounting/actual/report (grouped with subtotals)
@acc.route('/actual/report')
@login_required
def account_actual_report():
    # 현재 페이지 번호 (기본값 1)
    page = int(request.args.get('page', 1))
    per_page = 20  # 한 페이지에 보여줄 행 수

    # Billing Date 기본값 계산
    billing_start_default, billing_end_default = _compute_prev_month_start_and_current_month_end()

    conn = pyodbc.connect(CONN_STR)
    cursor = conn.cursor()

    # 전체 데이터 개수 쿼리
    base_sql = "SELECT COUNT(*) FROM Account_Actual"
    where_clauses = []
    params = []
    base_sql, params = _apply_filters_from_request(base_sql, params, where_clauses, use_defaults=True)
    cursor.execute(base_sql.replace(" ORDER BY BILLING_DATE DESC", ""), params)
    total_count = cursor.fetchone()[0]

    # 실제 데이터 select (페이징 적용)
    data_sql = "SELECT * FROM Account_Actual"
    data_sql, data_params = _apply_filters_from_request(data_sql, [], [], use_defaults=True)
    # 그룹 리포트는 Actual_Code 별로 먼저 묶이도록 정렬 변경
    data_sql = data_sql.replace(
        "ORDER BY BILLING_DATE DESC",
        "ORDER BY ISNULL(Actual_Code,'UNKNOWN'), BILLING_DATE DESC"
    )
    data_sql += f" OFFSET {(page-1)*per_page} ROWS FETCH NEXT {per_page} ROWS ONLY"
    cursor.execute(data_sql, data_params)
    rows = fetch_rows_as_dicts(cursor)

    # --- 전체(필터된) 합계 및 Actual_Code 별 전체 소계 계산 (KCC/Bulk 포함) ---
    grand_before = grand_vat = grand_wht = grand_payment = grand_kcc = grand_bulk = 0.0
    acct_group_sums = {}

    full_sql = "SELECT * FROM Account_Actual"
    full_sql, full_params = _apply_filters_from_request(full_sql, [], [], use_defaults=True)
    from_idx = full_sql.find("FROM Account_Actual")
    where_part = full_sql[from_idx:] if from_idx != -1 else ""
    where_part_no_order = where_part.replace(" ORDER BY BILLING_DATE DESC", "")

    # 전체 합계: BEFORE_VAT_AMT, VAT_AMOUNT, WHT_AMOUNT, PAYMENT, KCC, BULK
    sum_sql = ("SELECT ISNULL(SUM(BEFORE_VAT_AMT),0), ISNULL(SUM(VAT_AMOUNT),0), "
               "ISNULL(SUM(WHT_AMOUNT),0), ISNULL(SUM(PAYMENT),0), "
               "ISNULL(SUM(CASE WHEN PAYMENT_METHOD='KCC'  THEN PAYMENT ELSE 0 END),0), "
               "ISNULL(SUM(CASE WHEN PAYMENT_METHOD='BULK' THEN PAYMENT ELSE 0 END),0) "
               ) + where_part_no_order

    # Actual_Code 별 전체 소계 (KCC, BULK 포함)
    group_sum_sql = ("SELECT ISNULL(Actual_Code,'UNKNOWN') AS Actual_Code, "
                     "ISNULL(SUM(BEFORE_VAT_AMT),0), ISNULL(SUM(VAT_AMOUNT),0), "
                     "ISNULL(SUM(WHT_AMOUNT),0), ISNULL(SUM(PAYMENT),0), "
                     "ISNULL(SUM(CASE WHEN PAYMENT_METHOD='KCC'  THEN PAYMENT ELSE 0 END),0), "
                     "ISNULL(SUM(CASE WHEN PAYMENT_METHOD='BULK' THEN PAYMENT ELSE 0 END),0) "
                     + where_part_no_order +
                     " GROUP BY ISNULL(Actual_Code,'UNKNOWN')")
    try:
        cursor.execute(sum_sql, full_params)
        gr = cursor.fetchone() or (0, 0, 0, 0, 0, 0)
        grand_before   = gr[0] or 0
        grand_vat      = gr[1] or 0
        grand_wht      = gr[2] or 0
        grand_payment  = gr[3] or 0
        grand_kcc      = gr[4] or 0
        grand_bulk     = gr[5] or 0
    except Exception:
        grand_before = grand_vat = grand_wht = grand_payment = grand_kcc = grand_bulk = 0.0

    try:
        cursor.execute(group_sum_sql, full_params)
        for gr in cursor.fetchall():
            code_key = str(gr[0] or 'UNKNOWN').strip()
            acct_group_sums[code_key] = {
                'subtotal_before_vat': gr[1] or 0,
                'subtotal_vat':        gr[2] or 0,
                'subtotal_wht':        gr[3] or 0,
                'subtotal_payment':    gr[4] or 0,
                'subtotal_kcc':        gr[5] or 0,  # KCC 소계
                'subtotal_bulk':       gr[6] or 0   # Bulk 소계
            }
    except Exception:
        acct_group_sums = {}
    # --- 끝 ---

    # Actual_Code 별 그룹핑 (account name 포함)
    codes = sorted({ (r.get('Actual_Code') or '').strip() for r in rows if (r.get('Actual_Code') or '').strip() })
    account_names = {}
    if codes:
        placeholders = ','.join(['?'] * len(codes))
        lang = session.get('language', 'en')
        name_col = 'NAME_KO' if lang == 'ko' else ('NAME_TH' if lang == 'th' else 'NAME_EN')
        try:
            cursor.execute(f"SELECT account_code, {name_col} FROM dbo.code_Account WHERE account_code IN ({placeholders})", codes)
            acct_rows = cursor.fetchall()
            for ar in acct_rows:
                code_key = ar[0] if ar and len(ar) > 0 else None
                name_val = ar[1] if ar and len(ar) > 1 else ''
                if code_key:
                    account_names[str(code_key).strip()] = (name_val or '').strip()
        except Exception:
            current_app.logger.exception("Failed to load account names for report grouping")

    grouped_items = []
    group_map = {}
    for r in rows:
        code = (r.get('Actual_Code') or '').strip() or 'UNKNOWN'
        label = code
        if code != 'UNKNOWN':
            name = account_names.get(code, '')
            label = f"{code} - {name}" if name else code

        if code not in group_map:
            group_map[code] = {
                'type': label,
                'rows': [],
                'subtotal_before_vat': 0.0,
                'subtotal_vat':        0.0,
                'subtotal_wht':        0.0,
                'subtotal_payment':    0.0,
                'subtotal_kcc':        0.0,  # KCC 소계
                'subtotal_bulk':       0.0   # Bulk 소계
            }
            grouped_items.append(group_map[code])

        g = group_map[code]
        g['rows'].append(r)
        try:
            g['subtotal_before_vat'] += float(r.get('BEFORE_VAT_AMT') or 0)
            g['subtotal_vat']        += float(r.get('VAT_AMOUNT') or 0)
            g['subtotal_wht']        += float(r.get('WHT_AMOUNT') or 0)
            g['subtotal_payment']    += float(r.get('PAYMENT') or 0)
            pm  = (r.get('PAYMENT_METHOD') or '').strip()
            pay = float(r.get('PAYMENT') or 0)
            if pm == 'KCC':
                g['subtotal_kcc']  += pay
            elif pm == 'BULK':
                g['subtotal_bulk'] += pay
        except Exception:
            pass

        # 전체 소계값(DB 집계)으로 덮어쓰기
        sums = acct_group_sums.get(code)
        if sums:
            g['subtotal_before_vat'] = sums['subtotal_before_vat']
            g['subtotal_vat']        = sums['subtotal_vat']
            g['subtotal_wht']        = sums['subtotal_wht']
            g['subtotal_payment']    = sums['subtotal_payment']
            g['subtotal_kcc']        = sums['subtotal_kcc']
            g['subtotal_bulk']       = sums['subtotal_bulk']

    cursor.close()
    conn.close()

    args = request.args.to_dict()
    args.pop('page', None)
    extra_query = ''
    if args:
        extra_query = '&' + '&'.join(f'{k}={v}' for k, v in args.items() if v)

    return render_template(
        'accounting/report/list.html',
        page=page,
        total_pages=(total_count + per_page - 1) // per_page,
        extra_query=extra_query,
        request_args=request.args,
        billing_start_default=billing_start_default,
        billing_end_default=billing_end_default,
        key_start_default='',
        key_end_default='',
        grouped_items=grouped_items,
        grand_before=grand_before,
        grand_vat=grand_vat,
        grand_wht=grand_wht,
        grand_payment=grand_payment,
        grand_kcc=grand_kcc,    # KCC 전체 합계
        grand_bulk=grand_bulk   # Bulk 전체 합계
    )

@acc.route('/actual/report/excel')
@login_required
def account_actual_report_excel():
    conn = None
    cursor = None
    try:
        conn = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()

        base_sql = "SELECT * FROM Account_Actual"
        where_clauses = []
        params = []
        base_sql, params = _apply_filters_from_request(base_sql, params, where_clauses, use_defaults=True)
        # 리포트 목록과 동일한 정렬 순서 적용
        base_sql = base_sql.replace(
            "ORDER BY BILLING_DATE DESC",
            "ORDER BY ISNULL(Actual_Code,'UNKNOWN'), BILLING_DATE DESC"
        )

        cursor.execute(base_sql, params)
        rows = fetch_rows_as_dicts(cursor)

        # PAYMENT_METHOD, partner_name 키 정규화
        for r in rows:
            pm = None
            for k in ('PAYMENT_METHOD', 'payment_method', 'PaymentMethod', 'paymentMethod'):
                if k in r and r.get(k) not in (None, ''):
                    pm = r.get(k)
                    break
            r['PAYMENT_METHOD'] = pm or ''
            r['partner_name'] = (r.get('partner_name') or r.get('PARTNER_NAME') or r.get('partner') or '')

        # account name 조회
        codes = sorted({ (r.get('Actual_Code') or '').strip() for r in rows if (r.get('Actual_Code') or '').strip() })
        account_names = {}
        if codes:
            placeholders = ','.join(['?'] * len(codes))
            try:
                lang = session.get('language', 'en')
                name_col = 'NAME_KO' if lang == 'ko' else ('NAME_TH' if lang == 'th' else 'NAME_EN')
                cursor.execute(f"SELECT account_code, {name_col} FROM dbo.code_Account WHERE account_code IN ({placeholders})", codes)
                acct_rows = cursor.fetchall()
                for ar in acct_rows:
                    code = ar[0] if ar and len(ar) > 0 else None
                    name = ar[1] if ar and len(ar) > 1 else ''
                    if code:
                        account_names[str(code).strip()] = (name or '').strip()
            except Exception:
                current_app.logger.exception("Failed to load account names for excel grouping")

        # Actual_Code 별 그룹핑 및 소계 (KCC/Bulk 포함)
        grouped = OrderedDict()
        grand_before = grand_vat = grand_wht = grand_payment = grand_kcc = grand_bulk = 0.0

        for r in rows:
            raw_code = (r.get('Actual_Code') or '').strip() or 'UNKNOWN'
            if raw_code not in grouped:
                grouped[raw_code] = {
                    'rows': [],
                    'subtotal_before':  0.0,
                    'subtotal_vat':     0.0,
                    'subtotal_wht':     0.0,
                    'subtotal_payment': 0.0,
                    'subtotal_kcc':     0.0,  # KCC 소계
                    'subtotal_bulk':    0.0   # Bulk 소계
                }
            grouped[raw_code]['rows'].append(r)

            try: before_val  = float(r.get('BEFORE_VAT_AMT') or 0)
            except Exception: before_val = 0.0
            try: vat_val     = float(r.get('VAT_AMOUNT') or 0)
            except Exception: vat_val = 0.0
            try: wht_val     = float(r.get('WHT_AMOUNT') or 0)
            except Exception: wht_val = 0.0
            try: payment_val = float(r.get('PAYMENT') or 0)
            except Exception: payment_val = 0.0

            row_pm   = (r.get('PAYMENT_METHOD') or '').strip()
            kcc_val  = payment_val if row_pm == 'KCC'  else 0.0
            bulk_val = payment_val if row_pm == 'BULK' else 0.0

            grouped[raw_code]['subtotal_before']  += before_val
            grouped[raw_code]['subtotal_vat']     += vat_val
            grouped[raw_code]['subtotal_wht']     += wht_val
            grouped[raw_code]['subtotal_payment'] += payment_val
            grouped[raw_code]['subtotal_kcc']     += kcc_val
            grouped[raw_code]['subtotal_bulk']    += bulk_val

            grand_before  += before_val
            grand_vat     += vat_val
            grand_wht     += wht_val
            grand_payment += payment_val
            grand_kcc     += kcc_val
            grand_bulk    += bulk_val

        # Excel 생성
        output = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws = workbook.add_worksheet('AccountActualReport')

        header_fmt = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0', 'border': 1})
        group_fmt  = workbook.add_format({'bold': True, 'bg_color': '#eaf3ff', 'border': 1})
        num_fmt    = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        txt_fmt    = workbook.add_format({'border': 1})
        bold_fmt   = workbook.add_format({'bold': True, 'border': 1})

        # 컬럼 목록 (KCC, Bulk 추가 — Payment 다음, Remark 앞)
        cols = [
            'Key Date', 'Expense Type', 'Billing Date', 'Payer', 'Partner',
            'Payment Method', 'Before VAT Amount', 'VAT Amount', 'WHT Amount',
            'Payment', 'KCC', 'BULK', 'Remark'
        ]
        # 인덱스: 0~5 텍스트, 6~11 숫자, 12 텍스트

        row_idx = 0

        for code, info in grouped.items():
            name = account_names.get(code, '')
            header_label = f"{code} - {name}" if name else code

            # 그룹 헤더
            ws.merge_range(row_idx, 0, row_idx, len(cols) - 1, header_label, group_fmt)
            row_idx += 1

            # 컬럼 헤더
            for c, h in enumerate(cols):
                ws.write(row_idx, c, h, header_fmt)
                if c in (0, 2):               # Key Date, Billing Date
                    ws.set_column(c, c, 12)
                elif c in (3, 4, 5):          # Payer, Partner, Payment Method
                    ws.set_column(c, c, 18)
                elif c in (6, 7, 8, 9, 10, 11):  # 숫자 컬럼 (Before VAT ~ Bulk)
                    ws.set_column(c, c, 15)
                else:
                    ws.set_column(c, c, 20)
            row_idx += 1

            # 데이터 행
            for r in info['rows']:
                row_pm = (r.get('PAYMENT_METHOD') or '').strip()
                pay    = r.get('PAYMENT')

                ws.write(row_idx, 0, str(r.get('KEY_DATE') or ''), txt_fmt)
                ws.write(row_idx, 1, r.get('Actual_TYPE') or '', txt_fmt)
                ws.write(row_idx, 2, str(r.get('BILLING_DATE') or ''), txt_fmt)
                ws.write(row_idx, 3, r.get('payer') or '', txt_fmt)
                ws.write(row_idx, 4, r.get('partner_name') or '', txt_fmt)
                ws.write(row_idx, 5, row_pm, txt_fmt)

                # Before VAT Amount (col 6)
                bv = r.get('BEFORE_VAT_AMT')
                try:
                    ws.write_number(row_idx, 6, float(bv), num_fmt) if bv not in (None, '') else ws.write(row_idx, 6, '', txt_fmt)
                except Exception:
                    ws.write(row_idx, 6, bv, txt_fmt)

                # VAT Amount (col 7)
                vat = r.get('VAT_AMOUNT')
                try:
                    ws.write_number(row_idx, 7, float(vat), num_fmt) if vat not in (None, '') else ws.write(row_idx, 7, '', txt_fmt)
                except Exception:
                    ws.write(row_idx, 7, vat, txt_fmt)

                # WHT Amount (col 8)
                wht = r.get('WHT_AMOUNT')
                try:
                    ws.write_number(row_idx, 8, float(wht), num_fmt) if wht not in (None, '') else ws.write(row_idx, 8, '', txt_fmt)
                except Exception:
                    ws.write(row_idx, 8, wht, txt_fmt)

                # Payment (col 9)
                try:
                    ws.write_number(row_idx, 9, float(pay), num_fmt) if pay not in (None, '') else ws.write(row_idx, 9, '', txt_fmt)
                except Exception:
                    ws.write(row_idx, 9, pay, txt_fmt)

                # KCC (col 10) — PAYMENT_METHOD가 KCC인 경우 결제금액 표시
                try:
                    if row_pm == 'KCC' and pay not in (None, ''):
                        ws.write_number(row_idx, 10, float(pay), num_fmt)
                    else:
                        ws.write(row_idx, 10, '', txt_fmt)
                except Exception:
                    ws.write(row_idx, 10, '', txt_fmt)

                # Bulk (col 11) — PAYMENT_METHOD가 Bulk인 경우 결제금액 표시
                try:
                    if row_pm == 'BULK' and pay not in (None, ''):
                        ws.write_number(row_idx, 11, float(pay), num_fmt)
                    else:
                        ws.write(row_idx, 11, '', txt_fmt)
                except Exception:
                    ws.write(row_idx, 11, '', txt_fmt)

                # Remark (col 12)
                ws.write(row_idx, 12, r.get('REMARK') or '', txt_fmt)

                row_idx += 1

            # 그룹 소계 행
            ws.merge_range(row_idx, 0, row_idx, 5, f"{header_label} subtotal", bold_fmt)
            ws.write_number(row_idx, 6,  info['subtotal_before'],  num_fmt)
            ws.write_number(row_idx, 7,  info['subtotal_vat'],     num_fmt)
            ws.write_number(row_idx, 8,  info['subtotal_wht'],     num_fmt)
            ws.write_number(row_idx, 9,  info['subtotal_payment'], num_fmt)
            ws.write_number(row_idx, 10, info['subtotal_kcc'],     num_fmt)
            ws.write_number(row_idx, 11, info['subtotal_bulk'],    num_fmt)
            ws.write(row_idx, 12, '', txt_fmt)
            row_idx += 2

        # 전체 합계 행
        ws.merge_range(row_idx, 0, row_idx, 5, "GRAND TOTAL", group_fmt)
        ws.write_number(row_idx, 6,  grand_before,  num_fmt)
        ws.write_number(row_idx, 7,  grand_vat,     num_fmt)
        ws.write_number(row_idx, 8,  grand_wht,     num_fmt)
        ws.write_number(row_idx, 9,  grand_payment, num_fmt)
        ws.write_number(row_idx, 10, grand_kcc,     num_fmt)
        ws.write_number(row_idx, 11, grand_bulk,    num_fmt)

        workbook.close()
        output.seek(0)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        exporter = getattr(current_user, 'username', None) or str(current_user.get_id() or '')
        exporter_safe = str(exporter).replace(' ', '_')
        filename = f'account_actual_report_{timestamp}_{exporter_safe}.xlsx'
        return send_file(output, as_attachment=True, download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    except Exception as e:
        current_app.logger.error(f"Report Excel export failed: {e}")
        return jsonify({'error': 'report_excel_failed'}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass

# ──────────────────────────────────────────
#  Salary Management
# ──────────────────────────────────────────

def _compute_paid(data):
    salary    = float(data.get('SalaryAmount')   or 0)
    allowance = float(data.get('TotalAllowance') or 0)
    deduction = float(data.get('TotalDeduction') or 0)
    return salary + allowance - deduction


@acc.route('/salary')
@login_required
def salary_page():
    return render_template('accounting/salary/list.html')


@acc.route('/salary/list')
@login_required
def salary_list():
    company    = request.args.get('company',    '')
    year       = request.args.get('year',       '')
    month_from = request.args.get('month_from', '')
    month_to   = request.args.get('month_to',   '')
    try:
        conn   = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        sql    = """SELECT SalaryID, CompanyName, Year, Month, RecipientName,
                           SalaryAmount, TotalAllowance, TotalDeduction, PaidAmount, Remark
                    FROM dbo.salary_log WHERE 1=1"""
        params = []
        if company:    sql += " AND CompanyName = ?"; params.append(company)
        if year:       sql += " AND Year = ?";        params.append(int(year))
        if month_from: sql += " AND Month >= ?";      params.append(int(month_from))
        if month_to:   sql += " AND Month <= ?";      params.append(int(month_to))
        sql += " ORDER BY Year DESC, Month DESC, CompanyName, RecipientName"
        cursor.execute(sql, params)
        rows = fetch_rows_as_dicts(cursor)
        conn.close()
        for r in rows:
            for k, v in r.items():
                if hasattr(v, '__float__'):
                    r[k] = float(v) if v is not None else None
        return jsonify(rows)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@acc.route('/salary/detail/<int:salary_id>')
@login_required
def salary_detail(salary_id):
    try:
        conn   = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute("""SELECT SalaryID, CompanyName, Year, Month, RecipientName,
                                 SalaryAmount, TotalAllowance, TotalDeduction, PaidAmount, Remark
                          FROM dbo.salary_log WHERE SalaryID = ?""", (salary_id,))
        cols = [col[0] for col in cursor.description]
        row  = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({'error': 'Not found'}), 404
        item = dict(zip(cols, row))
        for k, v in item.items():
            if hasattr(v, '__float__'):
                item[k] = float(v) if v is not None else None
        return jsonify(item)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@acc.route('/salary/save', methods=['POST'])
@login_required
def salary_save():
    data = request.get_json()
    try:
        paid = _compute_paid(data)
        conn   = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.salary_log
                (CompanyName, Year, Month, RecipientName,
                 SalaryAmount, TotalAllowance, TotalDeduction, PaidAmount, Remark)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            data['CompanyName'], int(data['Year']), int(data['Month']),
            data['RecipientName'],
            float(data['SalaryAmount'])   if data.get('SalaryAmount')   else None,
            float(data['TotalAllowance']) if data.get('TotalAllowance') else None,
            float(data['TotalDeduction']) if data.get('TotalDeduction') else None,
            paid,
            data.get('Remark') or None
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@acc.route('/salary/update', methods=['POST'])
@login_required
def salary_update():
    data = request.get_json()
    try:
        paid = _compute_paid(data)
        conn   = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE dbo.salary_log
            SET CompanyName=?, Year=?, Month=?, RecipientName=?,
                SalaryAmount?, TotalAllowance?, TotalDeduction?, PaidAmount?, Remark=?
            WHERE SalaryID = ?
        """, (
            data['CompanyName'], int(data['Year']), int(data['Month']),
            data['RecipientName'],
            float(data['SalaryAmount'])   if data.get('SalaryAmount')   else None,
            float(data['TotalAllowance']) if data.get('TotalAllowance') else None,
            float(data['TotalDeduction']) if data.get('TotalDeduction') else None,
            paid,
            data.get('Remark') or None,
            int(data['SalaryID'])
        ))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@acc.route('/salary/delete', methods=['POST'])
@login_required
def salary_delete():
    data = request.get_json()
    ids  = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'error': 'No IDs'}), 400
    try:
        conn   = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in ids])
        cursor.execute(f"DELETE FROM dbo.salary_log WHERE SalaryID IN ({placeholders})", ids)
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@acc.route('/salary/excel')
@login_required
def salary_excel():
    company    = request.args.get('company',    '')
    year       = request.args.get('year',       '')
    month_from = request.args.get('month_from', '')
    month_to   = request.args.get('month_to',   '')
    conn = None; cursor = None
    try:
        conn   = pyodbc.connect(CONN_STR)
        cursor = conn.cursor()
        sql    = """SELECT SalaryID, CompanyName, Year, Month, RecipientName,
                           SalaryAmount, TotalAllowance, TotalDeduction, PaidAmount, Remark
                    FROM dbo.salary_log WHERE 1=1"""
        params = []
        if company:    sql += " AND CompanyName = ?"; params.append(company)
        if year:       sql += " AND Year = ?";        params.append(int(year))
        if month_from: sql += " AND Month >= ?";      params.append(int(month_from))
        if month_to:   sql += " AND Month <= ?";      params.append(int(month_to))
        sql += " ORDER BY Year DESC, Month DESC, CompanyName, RecipientName"
        cursor.execute(sql, params)
        rows = fetch_rows_as_dicts(cursor)

        output   = BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        ws       = workbook.add_worksheet('Salary')

        header_fmt    = workbook.add_format({'bold': True, 'bg_color': '#F0F0F0', 'border': 1, 'align': 'center'})
        num_fmt       = workbook.add_format({'num_format': '#,##0.00', 'border': 1})
        txt_fmt       = workbook.add_format({'border': 1})
        center_fmt    = workbook.add_format({'border': 1, 'align': 'center'})
        total_lbl_fmt = workbook.add_format({'bold': True, 'bg_color': '#eef2f7', 'border': 1})
        total_num_fmt = workbook.add_format({'bold': True, 'bg_color': '#eef2f7', 'border': 1, 'num_format': '#,##0.00'})

        headers    = ['#', 'Company', 'Year', 'Month', 'Recipient',
                      'Basic Salary', 'Allowance', 'Deduction', 'Net Pay', 'Remark']
        col_widths = [6, 14, 8, 8, 20, 16, 16, 16, 16, 24]
        for c, (h, w) in enumerate(zip(headers, col_widths)):
            ws.write(0, c, h, header_fmt)
            ws.set_column(c, c, w)

        tot_salary = tot_allow = tot_deduct = tot_paid = 0.0
        for i, r in enumerate(rows, start=1):
            salary = float(r.get('SalaryAmount')   or 0)
            allow  = float(r.get('TotalAllowance') or 0)
            deduct = float(r.get('TotalDeduction') or 0)
            paid   = float(r.get('PaidAmount')     or 0)
            tot_salary += salary; tot_allow += allow
            tot_deduct += deduct; tot_paid  += paid

            ws.write(i, 0, i,                                   center_fmt)
            ws.write(i, 1, r.get('CompanyName')   or '',        txt_fmt)
            ws.write(i, 2, r.get('Year')          or '',        center_fmt)
            ws.write(i, 3, str(r.get('Month') or '').zfill(2), center_fmt)
            ws.write(i, 4, r.get('RecipientName') or '',        txt_fmt)
            ws.write_number(i, 5, salary, num_fmt)
            ws.write_number(i, 6, allow,  num_fmt)
            ws.write_number(i, 7, deduct, num_fmt)
            ws.write_number(i, 8, paid,   num_fmt)
            ws.write(i, 9, r.get('Remark') or '',               txt_fmt)

        total_row = len(rows) + 1
        ws.merge_range(total_row, 0, total_row, 4, 'Grand Total', total_lbl_fmt)
        ws.write_number(total_row, 5, tot_salary, total_num_fmt)
        ws.write_number(total_row, 6, tot_allow,  total_num_fmt)
        ws.write_number(total_row, 7, tot_deduct, total_num_fmt)
        ws.write_number(total_row, 8, tot_paid,   total_num_fmt)
        ws.write(total_row, 9, '',                total_lbl_fmt)

        workbook.close(); output.seek(0)
        filename = f'salary_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        return send_file(output, as_attachment=True, download_name=filename,
                         mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if cursor:
            try: cursor.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass