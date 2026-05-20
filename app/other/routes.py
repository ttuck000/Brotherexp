import calendar as cal_mod
from calendar import monthrange
from datetime import datetime, date, time, timedelta
from io import BytesIO

import pandas as pd
import pyodbc
from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    send_file,
    current_app,
    session,
)
from flask_login import login_required, current_user

from config import Config

other = Blueprint('other', __name__, url_prefix='/other')

CONN_STR = (
    'DRIVER={ODBC Driver 17 for SQL Server};'
    'SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;'
)

# 차량 마스터 없음 — 고정 5대 (static/images/cars/*.jpg)
CAR_VEHICLES = [
    {'code': 'van_saha', 'label_key': 'car_vehicle_van_saha', 'image': 'images/cars/van_saha.png'},
    {'code': 'mobile_xray', 'label_key': 'car_vehicle_mobile_xray', 'image': 'images/cars/mobile_xray.png'},
    {'code': 'pickup_high', 'label_key': 'car_vehicle_pickup_high', 'image': 'images/cars/pickup_high.png'},
    {'code': 'pickup_low', 'label_key': 'car_vehicle_pickup_low', 'image': 'images/cars/pickup_low.png'},
    {'code': 'van_clinic', 'label_key': 'car_vehicle_van_clinic', 'image': 'images/cars/van_clinic.png'},
]


def _conn_str():
    return current_app.config.get('PYODBC_CONN_STR') or Config.PYODBC_CONN_STR or CONN_STR


def _vehicle_label(vehicle, lang='en'):
    try:
        from app import LANGUAGES
        return LANGUAGES.get(lang, {}).get(
            vehicle['label_key'],
            LANGUAGES.get('en', {}).get(vehicle['label_key'], vehicle['code']),
        )
    except Exception:
        return vehicle['code']


def _vehicles_for_ui(lang):
    return [{**v, 'label': _vehicle_label(v, lang)} for v in CAR_VEHICLES]


def _localize_car_item(row, lang):
    """DB에 저장된 VehicleLabel 대신 현재 언어 차량명 표시"""
    if not row:
        return row
    out = dict(row)
    code = out.get('VehicleCode')
    if code:
        vehicle = _vehicle_by_code(code)
        if vehicle:
            out['VehicleLabel'] = _vehicle_label(vehicle, lang)
    return out


def _localize_car_items(items, lang):
    return [_localize_car_item(r, lang) for r in items]


def _parse_date(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ('%Y-%m-%d', '%d/%m/%Y', '%d-%m-%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _parse_time(s):
    if not s:
        return None
    s = s.strip()
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    return None


def _is_same_use_day(use_date, use_date_to):
    """종료일이 없거나 시작일과 같으면 같은 날 시간 비교"""
    if not use_date:
        return True
    if not use_date_to:
        return True
    return use_date_to == use_date


def _car_time_range_invalid(time_from, time_to):
    if not time_from or not time_to:
        return False
    return time_to <= time_from


def _as_date(d):
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    return d


def _car_booking_window(use_date, use_date_to, is_allday, time_from, time_to):
    """예약 구간을 datetime 범위로 변환 (겹침 검사용)."""
    start_d = _as_date(use_date)
    end_d = _as_date(use_date_to) or start_d
    if is_allday:
        t_start = time(0, 0, 0)
        t_end = time(23, 59, 59)
    else:
        t_start = time_from or time(0, 0)
        t_end = time_to or time(23, 59, 59)
    return datetime.combine(start_d, t_start), datetime.combine(end_d, t_end)


def _booking_windows_overlap(start_a, end_a, start_b, end_b):
    return start_a < end_b and start_b < end_a


def _find_car_schedule_conflict(cursor, vehicle_code, use_date, use_date_to,
                                is_allday, time_from, time_to, exclude_id=None):
    """동일 차량·기간·시간이 겹치는 기존 신청이 있으면 해당 row 반환."""
    end_d = use_date_to or use_date
    sql = _CAR_LIST_SELECT + """
        WHERE VehicleCode = ?
          AND UseDate <= ? AND ISNULL(usedateto, UseDate) >= ?
    """
    params = [vehicle_code, end_d, use_date]
    if exclude_id is not None:
        sql += " AND ID <> ?"
        params.append(exclude_id)
    cursor.execute(sql, params)
    cols = [c[0] for c in cursor.description]
    new_start, new_end = _car_booking_window(
        use_date, use_date_to, is_allday, time_from, time_to
    )
    for row in cursor.fetchall():
        existing = dict(zip(cols, row))
        ex_start, ex_end = _car_booking_window(
            existing.get('UseDate'),
            existing.get('usedateto'),
            _is_allday(existing.get('is_allday')),
            existing.get('TimeFrom'),
            existing.get('TimeTo'),
        )
        if _booking_windows_overlap(new_start, new_end, ex_start, ex_end):
            return existing
    return None


def _render_car_new_form(form_data, vehicles, company_options):
    return render_template(
        'other/car/new.html',
        vehicles=vehicles,
        company_options=company_options,
        form=_merge_car_form_defaults(form_data),
        default_use_date=date.today().isoformat(),
        default_user_name=_current_username(),
        default_driver_name=_current_username(),
    )


def _vehicle_by_code(code):
    for v in CAR_VEHICLES:
        if v['code'] == code:
            return v
    return None


def _current_username():
    if getattr(current_user, 'is_authenticated', False) and current_user.is_authenticated:
        name = (getattr(current_user, 'username', None) or '').strip()
        if name:
            return name
    return (session.get('username') or '').strip()


def _default_car_form():
    """신규 화면 기본값: 사용 일자·종료일=오늘, 신청자/운전자=로그인 ID"""
    today = date.today().isoformat()
    username = _current_username()
    return {
        'use_date': today,
        'use_date_to': today,
        'user_name': username,
        'driver_name': username,
    }


def _merge_car_form_defaults(form_like):
    data = dict(form_like) if form_like else {}
    today = date.today().isoformat()
    if not data.get('use_date'):
        data['use_date'] = today
    if not data.get('use_date_to'):
        data['use_date_to'] = data.get('use_date') or today
    username = _current_username()
    if not data.get('user_name'):
        data['user_name'] = username
    if not data.get('driver_name'):
        data['driver_name'] = data.get('user_name') or username
    return data


def _load_company_options():
    """code_Account.company 목록 (회계 실적 조회와 동일)"""
    try:
        conn = pyodbc.connect(_conn_str())
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT company
            FROM dbo.code_Account
            WHERE company IS NOT NULL AND LTRIM(RTRIM(company)) <> ''
            ORDER BY company
        """)
        options = [
            {'value': (r[0] or '').strip(), 'label': (r[0] or '').strip()}
            for r in cur.fetchall()
            if (r[0] or '').strip()
        ]
        cur.close()
        conn.close()
        return options
    except Exception as e:
        current_app.logger.exception('car company options failed: %s', e)
        return []


_CAR_LIST_SELECT = """
    SELECT ID, SubmittedAt, UseDate, usedateto, is_allday, TimeFrom, TimeTo,
           VehicleCode, VehicleLabel, UserName, DriverName, Company,
           [Location], Remark, Approved, CreatedBy
    FROM dbo.Car_Use_Request
"""


def _t(key, lang=None):
    lang = lang or session.get('language', 'en')
    try:
        from app import LANGUAGES
        return LANGUAGES.get(lang, {}).get(key, LANGUAGES.get('en', {}).get(key, key))
    except Exception:
        return key


def _fmt_date(d):
    if d is None:
        return ''
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d')
    return str(d)


def _fmt_datetime(d):
    if d is None:
        return ''
    if hasattr(d, 'strftime'):
        return d.strftime('%Y-%m-%d %H:%M')
    return str(d)


def _fmt_time(t):
    if t is None:
        return ''
    if hasattr(t, 'strftime'):
        return t.strftime('%H:%M')
    return str(t)


def _is_allday(value):
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    return bool(value)


def _format_use_dates(use_date, use_date_to=None):
    start = _fmt_date(use_date)
    end = _fmt_date(use_date_to)
    if end and end != start:
        return f'{start} ~ {end}'
    return start


def _format_use_times(row, lang=None):
    if _is_allday(row.get('is_allday')):
        return _t('car_all_day', lang)
    t_from = _fmt_time(row.get('TimeFrom'))
    t_to = _fmt_time(row.get('TimeTo'))
    if t_from or t_to:
        return f'{t_from} — {t_to}'.strip(' —')
    return ''


def _schedule_event_time_label(row, lang):
    if _is_allday(row.get('is_allday')):
        return _t('car_all_day', lang)
    t_from = _fmt_time(row.get('TimeFrom'))
    t_to = _fmt_time(row.get('TimeTo'))
    if t_from and t_to:
        return f'{t_from}–{t_to}'
    return t_from or t_to or ''


def _parse_schedule_year_month():
    today = date.today()
    year = request.args.get('year', type=int) or today.year
    month = request.args.get('month', type=int) or today.month
    if month < 1:
        month = 1
    elif month > 12:
        month = 12
    return year, month


def _schedule_weekday_labels(lang):
    keys = (
        'car_weekday_sun', 'car_weekday_mon', 'car_weekday_tue', 'car_weekday_wed',
        'car_weekday_thu', 'car_weekday_fri', 'car_weekday_sat',
    )
    return [_t(k, lang) for k in keys]


def _load_car_schedule_items(year, month):
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    conn = pyodbc.connect(_conn_str())
    cur = conn.cursor()
    cur.execute(
        _CAR_LIST_SELECT
        + """
        WHERE UseDate <= ? AND ISNULL(usedateto, UseDate) >= ?
        ORDER BY UseDate, TimeFrom, ID
        """,
        (month_end, month_start),
    )
    cols = [c[0] for c in cur.description]
    items = [dict(zip(cols, r)) for r in cur.fetchall()]
    cur.close()
    conn.close()
    return items


def _build_schedule_calendar(year, month, items, lang):
    month_start = date(year, month, 1)
    month_end = date(year, month, monthrange(year, month)[1])
    by_day = {}

    for row in items:
        start = row.get('UseDate')
        if not start:
            continue
        if isinstance(start, datetime):
            start = start.date()
        end = row.get('usedateto') or start
        if isinstance(end, datetime):
            end = end.date()
        event = {
            'id': row.get('ID'),
            'vehicle': (row.get('VehicleLabel') or '').strip(),
            'time_label': _schedule_event_time_label(row, lang),
            'driver': (row.get('DriverName') or row.get('UserName') or '').strip(),
            'company': (row.get('Company') or '').strip(),
        }
        d = max(start, month_start)
        end_d = min(end, month_end)
        while d <= end_d:
            by_day.setdefault(d.isoformat(), []).append(dict(event))
            d += timedelta(days=1)

    cal = cal_mod.Calendar(firstweekday=6)
    weeks = []
    for week in cal.monthdatescalendar(year, month):
        days = []
        for d in week:
            in_month = d.month == month
            days.append({
                'date': d,
                'day': d.day,
                'in_month': in_month,
                'is_today': d == date.today(),
                'events': by_day.get(d.isoformat(), []) if in_month else [],
            })
        weeks.append(days)

    prev_month, prev_year = (12, year - 1) if month == 1 else (month - 1, year)
    next_month, next_year = (1, year + 1) if month == 12 else (month + 1, year)

    return {
        'year': year,
        'month': month,
        'weeks': weeks,
        'prev_year': prev_year,
        'prev_month': prev_month,
        'next_year': next_year,
        'next_month': next_month,
    }


def _default_list_filters():
    """목록 기본: 사용일 = 이번 달 1일 ~ 말일"""
    today = date.today()
    last_day = monthrange(today.year, today.month)[1]
    return {
        'use_date_from': today.replace(day=1),
        'use_date_to': today.replace(day=last_day),
        'vehicle_code': '',
        'driver': '',
        'company': '',
    }


def _filters_from_request(args, company_options=None):
    defaults = _default_list_filters()
    use_from = _parse_date(args.get('use_date_from')) or defaults['use_date_from']
    use_to = _parse_date(args.get('use_date_to')) or defaults['use_date_to']
    if use_from and use_to and use_from > use_to:
        use_from, use_to = use_to, use_from
    vehicle_code = (args.get('vehicle_code') or '').strip()
    if vehicle_code and not _vehicle_by_code(vehicle_code):
        vehicle_code = ''
    company = (args.get('company') or '').strip()
    if company and company_options:
        allowed = {o['value'] for o in company_options}
        if company not in allowed:
            company = ''
    return {
        'use_date_from': use_from,
        'use_date_to': use_to,
        'vehicle_code': vehicle_code,
        'driver': (args.get('driver') or '').strip(),
        'company': company,
    }


def _filters_for_form(filters):
    return {
        'use_date_from': _fmt_date(filters.get('use_date_from')),
        'use_date_to': _fmt_date(filters.get('use_date_to')),
        'vehicle_code': filters.get('vehicle_code') or '',
        'driver': filters.get('driver') or '',
        'company': filters.get('company') or '',
    }


def _fetch_requests_filtered(cursor, filters, limit=500):
    sql = _CAR_LIST_SELECT + " WHERE 1=1"
    params = []
    if filters.get('use_date_from'):
        sql += " AND UseDate >= ?"
        params.append(filters['use_date_from'])
    if filters.get('use_date_to'):
        sql += " AND UseDate <= ?"
        params.append(filters['use_date_to'])
    if filters.get('vehicle_code'):
        sql += " AND VehicleCode = ?"
        params.append(filters['vehicle_code'])
    if filters.get('driver'):
        sql += " AND (DriverName LIKE ? OR UserName LIKE ?)"
        like = f"%{filters['driver']}%"
        params.extend([like, like])
    if filters.get('company'):
        sql += " AND LTRIM(RTRIM(ISNULL(Company, N''))) = ?"
        params.append(filters['company'])
    sql += " ORDER BY SubmittedAt DESC, ID DESC"
    cursor.execute(sql, params)
    cols = [c[0] for c in cursor.description]
    return [dict(zip(cols, r)) for r in cursor.fetchmany(limit)]


def _fetch_request_by_id(cursor, req_id):
    cursor.execute(
        """
        SELECT ID, SubmittedAt, UseDate, usedateto, is_allday, TimeFrom, TimeTo,
               VehicleCode, VehicleLabel, UserName, DriverName, Company,
               [Location], Remark, Approved, CreatedBy
        FROM dbo.Car_Use_Request
        WHERE ID = ?
        """,
        (req_id,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    cols = [c[0] for c in cursor.description]
    return dict(zip(cols, row))


def _load_car_list(filters):
    conn = pyodbc.connect(_conn_str())
    cur = conn.cursor()
    items = _fetch_requests_filtered(cur, filters)
    cur.close()
    conn.close()
    return items


@other.route('/car')
@login_required
def car_management():
    """목록 (base/account/list.html 패턴)"""
    lang = session.get('language', 'en')
    company_options = _load_company_options()
    filters = _filters_from_request(request.args, company_options)
    form_filters = _filters_for_form(filters)
    vehicles = _vehicles_for_ui(lang)
    items = []
    try:
        items = _localize_car_items(_load_car_list(filters), lang)
    except Exception as e:
        current_app.logger.exception('car request list failed: %s', e)
        flash('car_list_load_failed', 'warning')

    return render_template(
        'other/car/list.html',
        items=items,
        filters=form_filters,
        vehicles=vehicles,
        company_options=company_options,
    )


@other.route('/car/schedule')
@login_required
def car_schedule():
    """월별 차량 사용 일정 달력"""
    lang = session.get('language', 'en')
    year, month = _parse_schedule_year_month()
    try:
        items = _localize_car_items(_load_car_schedule_items(year, month), lang)
        cal_data = _build_schedule_calendar(year, month, items, lang)
    except Exception as e:
        current_app.logger.exception('car schedule load failed: %s', e)
        flash('car_list_load_failed', 'warning')
        cal_data = _build_schedule_calendar(year, month, [], lang)

    return render_template(
        'other/car/schedule.html',
        cal=cal_data,
        weekday_labels=_schedule_weekday_labels(lang),
    )


@other.route('/car/excel')
@login_required
def car_excel():
    """목록과 동일한 조회 결과 Excel 다운로드"""
    lang = session.get('language', 'en')
    company_options = _load_company_options()
    filters = _filters_from_request(request.args, company_options)
    try:
        items = _localize_car_items(_load_car_list(filters), lang)
    except Exception as e:
        current_app.logger.exception('car excel export failed: %s', e)
        flash('car_list_load_failed', 'warning')
        return redirect(url_for('other.car_management'))

    rows = []
    for row in items:
        rows.append({
            _t('number', lang): row.get('ID'),
            _t('car_submitted_at', lang): _fmt_datetime(row.get('SubmittedAt')),
            _t('car_use_date', lang): _fmt_date(row.get('UseDate')),
            _t('car_use_date_to', lang): _fmt_date(row.get('usedateto')),
            _t('car_all_day', lang): _t('car_all_day', lang) if _is_allday(row.get('is_allday')) else '',
            _t('car_time_from', lang): _fmt_time(row.get('TimeFrom')),
            _t('car_time_to', lang): _fmt_time(row.get('TimeTo')),
            _t('company', lang): row.get('Company') or '',
            _t('car_vehicle_select', lang): row.get('VehicleLabel') or '',
            _t('car_requester', lang): row.get('UserName') or '',
            _t('car_driver', lang): row.get('DriverName') or '',
            _t('car_location', lang): row.get('Location') or '',
            _t('car_remark', lang): row.get('Remark') or '',
            _t('car_approved', lang): row.get('Approved') or '',
        })

    df = pd.DataFrame(rows)
    output = BytesIO()
    sheet_name = (_t('car_list_title', lang) or 'Car')[:31]
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        worksheet = writer.sheets[sheet_name]
        for idx, col in enumerate(df.columns):
            if df.empty:
                worksheet.set_column(idx, idx, len(str(col)) + 2)
            else:
                max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
                worksheet.set_column(idx, idx, min(max_length + 2, 48))
    output.seek(0)
    filename = f"car_use_{datetime.now().strftime('%Y%m%d')}.xlsx"
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename,
    )


@other.route('/car/report/<int:req_id>')
@login_required
def car_report(req_id):
    """선택한 신청 1건 인쇄용 리포트"""
    lang = session.get('language', 'en')
    try:
        conn = pyodbc.connect(_conn_str())
        cur = conn.cursor()
        item = _fetch_request_by_id(cur, req_id)
        cur.close()
        conn.close()
    except Exception as e:
        current_app.logger.exception('car report load failed: %s', e)
        flash('car_list_load_failed', 'warning')
        return redirect(url_for('other.car_management'))

    if not item:
        flash('car_report_not_found', 'warning')
        return redirect(url_for('other.car_management'))

    item = _localize_car_item(item, lang)
    vehicle = _vehicle_by_code(item.get('VehicleCode') or '')
    vehicle_image = vehicle['image'] if vehicle else None
    return render_template(
        'other/car/report.html',
        item=item,
        vehicle_image=vehicle_image,
    )


@other.route('/car/new', methods=['GET', 'POST'])
@login_required
def car_new():
    """신규 등록 (base/account/add.html 패턴)"""
    lang = session.get('language', 'en')
    vehicles = _vehicles_for_ui(lang)
    company_options = _load_company_options()

    if request.method == 'POST':
        use_date = _parse_date(request.form.get('use_date'))
        use_date_to = _parse_date(request.form.get('use_date_to'))
        is_allday = request.form.get('is_allday') in ('1', 'on', 'true')
        time_from = _parse_time(request.form.get('time_from'))
        time_to = _parse_time(request.form.get('time_to'))
        vehicle_code = (request.form.get('vehicle_code') or '').strip()
        requester = _current_username()
        driver_name = (request.form.get('driver_name') or '').strip() or requester
        location = (request.form.get('location') or '').strip()
        remark = (request.form.get('remark') or '').strip()
        company = (request.form.get('company') or '').strip()

        if use_date_to and use_date and use_date_to < use_date:
            use_date_to = use_date

        if is_allday:
            time_from = time(0, 0)
            time_to = time(23, 59)
        elif not time_from or not time_to:
            time_from = time_to = None

        vehicle = _vehicle_by_code(vehicle_code)
        if not all([use_date, vehicle, requester, driver_name, location, company]):
            flash('car_form_validation_error', 'error')
            return _render_car_new_form(request.form, vehicles, company_options)
        if not is_allday and not (time_from and time_to):
            flash('car_form_validation_error', 'error')
            return _render_car_new_form(request.form, vehicles, company_options)
        if (
            not is_allday
            and _is_same_use_day(use_date, use_date_to)
            and _car_time_range_invalid(time_from, time_to)
        ):
            flash('car_time_range_error', 'error')
            return _render_car_new_form(request.form, vehicles, company_options)

        vehicle_label = _vehicle_label(vehicle, lang)
        created_by = getattr(current_user, 'username', None) or str(
            getattr(current_user, 'id', '')
        )

        try:
            conn = pyodbc.connect(_conn_str())
            cur = conn.cursor()
            conflict = _find_car_schedule_conflict(
                cur, vehicle_code, use_date, use_date_to,
                is_allday, time_from, time_to,
            )
            if conflict:
                cur.close()
                conn.close()
                flash('car_schedule_conflict', 'error')
                return _render_car_new_form(request.form, vehicles, company_options)

            cur.execute(
                """
                INSERT INTO dbo.Car_Use_Request
                    (SubmittedAt, UseDate, usedateto, is_allday, TimeFrom, TimeTo,
                     VehicleCode, VehicleLabel, UserName, DriverName, Company,
                     [Location], Remark, CreatedBy)
                VALUES (SYSDATETIME(), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    use_date,
                    use_date_to,
                    1 if is_allday else 0,
                    time_from,
                    time_to,
                    vehicle_code,
                    vehicle_label,
                    requester,
                    driver_name,
                    company,
                    location,
                    remark or None,
                    created_by,
                ),
            )
            conn.commit()
            cur.close()
            conn.close()
            flash('car_form_saved', 'success')
            return redirect(url_for('other.car_management'))
        except Exception as e:
            current_app.logger.exception('car request save failed: %s', e)
            flash('car_form_save_failed', 'error')
            return _render_car_new_form(request.form, vehicles, company_options)

    today = date.today().isoformat()
    username = _current_username()
    return render_template(
        'other/car/new.html',
        vehicles=vehicles,
        company_options=company_options,
        form=_default_car_form(),
        default_use_date=today,
        default_user_name=username,
        default_driver_name=username,
    )
