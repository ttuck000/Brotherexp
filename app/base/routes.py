from app.base import bp as base
from flask import render_template, request, jsonify, redirect, url_for, flash, send_file, current_app
# NOTE: import style changed to absolute per project guidelines (Copilot Instructions)
from app.auth.routes import login_required
from app.utils.db_helper import get_db_connection
import pandas as pd
import pyodbc
from io import BytesIO
from datetime import datetime


# 품목코드 관리
@base.route('/item_code')
@login_required
def item_code():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM ItemMaster")
    items = cursor.fetchall()
    return render_template('base/item_code/list.html', items=items)

@base.route('/item_code/add', methods=['GET', 'POST'])
@login_required
def item_code_add():
    if request.method == 'POST':
        item_code = request.form['item_code']
        item_name = request.form['item_name']
        item_spec = request.form['item_spec']
        item_unit = request.form['item_unit']
        item_price = request.form['item_price']
        
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("INSERT INTO ItemMaster (item_code, item_name, item_spec, item_unit, item_price) VALUES (?, ?, ?, ?, ?)",
                      (item_code, item_name, item_spec, item_unit, item_price))
        conn.commit()
        
        flash('Item added successfully')
        return redirect(url_for('base.item_code'))
    
    return render_template('base/item_code/new.html')

@base.route('/item_code/new', methods=['GET'])
@login_required
def item_code_new():
    return render_template('base/item_code/new.html')

@base.route('/item_code/edit/<code>', methods=['GET'])
@login_required
def item_code_edit(code):
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT ItemCode, ItemName, Spec, unit, purchasePrice, salesprice, usage, remarks FROM ItemMaster WHERE ItemCode = ?", (code,))
        row = cursor.fetchone()
        
        if not row:
            cursor.close()
            conn.close()
            return render_template('errors/404.html'), 404
            
        item = {
            "code": row.ItemCode,
            "name": row.ItemName,
            "spec": row.Spec,
            "unit": row.unit,
            "purchasePrice": row.purchasePrice,
            "salesPrice": row.salesprice,
            "usage": row.usage,
            "remarks": row.remarks
        }
        
        cursor.close()
        conn.close()
        return render_template('base/item_code/edit.html', item=item)
        
    except Exception as e:
        # 에러 발생 시 연결 정리
        try:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()
        except:
            pass
        
        # 로그 기록 및 에러 페이지 반환
        from flask import current_app
        current_app.logger.error(f"Error in item_code_edit: {str(e)}")
        return render_template('errors/500.html'), 500

@base.route('/item/options')
@login_required
def item_options():
    try:
        conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT ItemCode, ItemName FROM ItemMaster WHERE usage = 'Y' ORDER BY ItemCode")
        rows = cursor.fetchall()
        return jsonify([{'code': r.ItemCode, 'name': r.ItemName} for r in rows])
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

# 창고정보 관리
@base.route('/warehouse')
@login_required
def warehouse():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM code_warehouse")
    warehouses = cursor.fetchall()
    return render_template('base/warehouse/list.html', warehouses=warehouses)

@base.route('/warehouse/search')
@login_required
def warehouse_search():
    code = request.args.get('warehouseCode', '').strip()
    name = request.args.get('warehouseName', '').strip()
    
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    query = "SELECT * FROM code_warehouse WHERE 1=1"
    params = []
    
    if code:
        query += " AND WH_CODE LIKE ?"
        params.append(f"%{code}%")
    if name:
        query += " AND WH_NAME LIKE ?"
        params.append(f"%{name}%")
    
    cursor.execute(query, params)
    warehouses = cursor.fetchall()
    return render_template('base/warehouse/list.html', warehouses=warehouses)

@base.route('/warehouse/add', methods=['GET', 'POST'])
@login_required
def warehouse_add():
    if request.method == 'POST':
        warehouse_code = request.form['warehouse_code']
        warehouse_name = request.form['warehouse_name']
        location = request.form['location']
        manager = request.form['manager']
        phone = request.form['phone']
        usage = request.form.get('usage', 'Y')
        remarks = request.form.get('remarks', '')
        
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO code_warehouse 
            (WH_CODE, WH_NAME, WH_LOCATION, WH_MANAGER, WH_PHONE, usage, remarks, createuser, createdate) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, GETDATE())""",
            (warehouse_code, warehouse_name, location, manager, phone, usage, remarks, 'SYSTEM'))
        conn.commit()
        
        flash('Warehouse added successfully')
        return redirect(url_for('base.warehouse'))
    
    return render_template('base/warehouse/add.html')

@base.route('/warehouse/edit/<code>', methods=['GET', 'POST'])
@login_required
def warehouse_edit(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    if request.method == 'POST':
        warehouse_name = request.form['warehouse_name']
        location = request.form['location']
        manager = request.form['manager']
        phone = request.form['phone']
        usage = request.form.get('usage', 'Y')
        remarks = request.form.get('remarks', '')
        
        cursor.execute("""
            UPDATE code_warehouse 
            SET WH_NAME=?, WH_LOCATION=?, WH_MANAGER=?, WH_PHONE=?, usage=?, remarks=?, updateuser='SYSTEM', updatedate=GETDATE()
            WHERE WH_CODE=?""",
            (warehouse_name, location, manager, phone, usage, remarks, code))
        conn.commit()
        
        flash('Warehouse updated successfully')
        return redirect(url_for('base.warehouse'))
    
    cursor.execute("SELECT * FROM code_warehouse WHERE WH_CODE = ?", (code,))
    warehouse = cursor.fetchone()
    if not warehouse:
        return render_template('errors/404.html'), 404
        
    return render_template('base/warehouse/edit.html', warehouse=warehouse)

@base.route('/check_warehouse_code/<code>')
@login_required
def check_warehouse_code(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM code_warehouse WHERE WH_CODE = ?", (code,))
    result = cursor.fetchone()
    return jsonify({'available': result.count == 0})

@base.route('/warehouse/delete', methods=['POST'])
@login_required
def warehouse_delete():
    data = request.get_json()
    codes = data.get('codes', [])
    if not codes:
        return jsonify({"success": False, "error": "No codes provided"})
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        query = f"DELETE FROM code_warehouse WHERE WH_CODE IN ({','.join(['?']*len(codes))})"
        cursor.execute(query, codes)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@base.route('/warehouse/excel')
@login_required
def warehouse_excel():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT WH_CODE, WH_NAME, WH_LOCATION, WH_MANAGER, WH_PHONE, usage, remarks FROM code_warehouse")
    rows = cursor.fetchall()
    items = []
    for row in rows:
        items.append({
            "창고코드": row.WH_CODE,
            "창고명": row.WH_NAME,
            "위치": row.WH_LOCATION,
            "관리자": row.WH_MANAGER,
            "전화번호": row.WH_PHONE,
            "사용여부": row.usage,
            "비고": row.remarks
        })
    df = pd.DataFrame(items)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='창고목록')
        worksheet = writer.sheets['창고목록']
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            worksheet.set_column(idx, idx, max_length + 2)
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='warehouse_list.xlsx'
    )

# 거래처정보 관리
@base.route('/customer')
@login_required
def customer_redirect():
    return redirect(url_for('base.customer_code'))

@base.route('/customer_code')
@login_required
def customer_code():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    code = request.args.get('customerCode', '').strip()
    name = request.args.get('customerName', '').strip()

    query = "SELECT * FROM dbo.CODE_VENDOR WHERE 1=1"
    params = []

    if code:
        query += " AND vd_code LIKE ?"
        params.append(f"%{code}%")
    if name:
        query += " AND vd_name LIKE ?"
        params.append(f"%{name}%")

    cursor.execute(query, params)
    vendors = cursor.fetchall()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        result = []
        for vendor in vendors:
            result.append({
                'vd_code': vendor.vd_code.strip(),
                'vd_name': vendor.vd_name.strip(),
                'vd_biz_number': vendor.vd_biz_number.strip() if vendor.vd_biz_number else '',
                'vd_tax_id': vendor.vd_tax_id.strip() if vendor.vd_tax_id else '',
                'vd_president': vendor.vd_president.strip() if vendor.vd_president else '',
                'vd_kind': vendor.vd_kind.strip() if vendor.vd_kind else '',
                'vd_item': vendor.vd_item.strip() if vendor.vd_item else '',
                'vd_phone': vendor.vd_phone.strip() if vendor.vd_phone else '',
                'vd_address': vendor.vd_address.strip() if vendor.vd_address else '',
                'vd_charger': vendor.vd_charger.strip() if vendor.vd_charger else '',
                'vd_charger_phone': vendor.vd_charger_phone.strip() if vendor.vd_charger_phone else '',
                'usage': vendor.usage.strip() if vendor.usage else 'Y',
                'vd_division': getattr(vendor, 'vd_division', '') if hasattr(vendor, 'vd_division') else '',
                'vd_website': getattr(vendor, 'vd_website', '') if hasattr(vendor, 'vd_website') else '',
                'vd_remarks': getattr(vendor, 'vd_remarks', '') if hasattr(vendor, 'vd_remarks') else ''
            })
        return jsonify(result)
    
    return render_template('base/customer_code/list.html')

@base.route('/customer_code/new')
@login_required
def customer_code_new():
    return render_template('base/customer_code/new.html')

@base.route('/customer_code/add')
@login_required
def customer_code_add():
    return render_template('base/customer_code/new.html')

@base.route('/customer_code/check/<code>')
@login_required
def check_customer_code(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM dbo.CODE_VENDOR WHERE vd_code = ?", (code,))
    exists = cursor.fetchone()[0] > 0
    
    return jsonify({'exists': exists})

@base.route('/customer_code/detail/<code>')
@login_required
def customer_code_detail(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM dbo.CODE_VENDOR WHERE vd_code = ?", (code,))
    vendor = cursor.fetchone()
    
    if vendor:
        result = {
            'vd_code': vendor.vd_code.strip(),
            'vd_name': vendor.vd_name.strip(),
            'vd_biz_number': vendor.vd_biz_number.strip() if vendor.vd_biz_number else '',
            'vd_tax_id': vendor.vd_tax_id.strip() if vendor.vd_tax_id else '',
            'vd_president': vendor.vd_president.strip() if vendor.vd_president else '',
            'vd_kind': vendor.vd_kind.strip() if vendor.vd_kind else '',
            'vd_item': vendor.vd_item.strip() if vendor.vd_item else '',
            'vd_phone': vendor.vd_phone.strip() if vendor.vd_phone else '',
            'vd_address': vendor.vd_address.strip() if vendor.vd_address else '',
            'vd_charger': vendor.vd_charger.strip() if vendor.vd_charger else '',
            'vd_charger_phone': vendor.vd_charger_phone.strip() if vendor.vd_charger_phone else '',
            'usage': vendor.usage.strip() if vendor.usage else 'Y',
            'vd_division': getattr(vendor, 'vd_division', '') if hasattr(vendor, 'vd_division') else '',
            'vd_website': getattr(vendor, 'vd_website', '') if hasattr(vendor, 'vd_website') else '',
            'vd_remarks': getattr(vendor, 'vd_remarks', '') if hasattr(vendor, 'vd_remarks') else ''
        }
        return jsonify(result)
    
    return jsonify({'error': 'Vendor not found'}), 404

@base.route('/customer_code/edit/<code>')
@login_required
def customer_code_edit(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM dbo.CODE_VENDOR WHERE vd_code = ?", (code,))
    vendor = cursor.fetchone()
    
    if not vendor:
        return render_template('errors/404.html'), 404
        
    return render_template('base/customer_code/edit.html')

@base.route('/customer_code/save', methods=['POST'])
@login_required
def save_customer_code():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    data = request.get_json()
    
    try:
        cursor.execute("""
            INSERT INTO dbo.CODE_VENDOR (
                vd_code, vd_name, vd_biz_number, vd_tax_id, vd_president, vd_kind, 
                vd_item, vd_phone, vd_address, vd_charger, vd_charger_phone, 
                usage, vd_division, vd_website, vd_remarks, createuser, createdate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYSTEM', GETDATE())
        """, (
            data['vd_code'], data['vd_name'], data['vd_biz_number'], data.get('vd_tax_id', ''), data['vd_president'],
            data['vd_kind'], data['vd_item'], data['vd_phone'], data['vd_address'],
            data['vd_charger'], data['vd_charger_phone'], data['usage'],
            data.get('vd_division', ''), data.get('vd_website', ''), data.get('vd_remarks', '')
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

@base.route('/customer_code/update', methods=['POST'])
@login_required
def update_customer_code():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    data = request.get_json()
    
    try:
        cursor.execute("""
            UPDATE dbo.CODE_VENDOR SET
                vd_name = ?, vd_biz_number = ?, vd_tax_id = ?, vd_president = ?, vd_kind = ?,
                vd_item = ?, vd_phone = ?, vd_address = ?, vd_charger = ?,
                vd_charger_phone = ?, usage = ?, vd_division = ?, vd_website = ?, vd_remarks = ?,
                updateuser = 'SYSTEM', updatedate = GETDATE()
            WHERE vd_code = ?
        """, (
            data['vd_name'], data['vd_biz_number'], data.get('vd_tax_id', ''), data['vd_president'], data['vd_kind'],
            data['vd_item'], data['vd_phone'], data['vd_address'], data['vd_charger'],
            data['vd_charger_phone'], data['usage'], data.get('vd_division', ''), data.get('vd_website', ''), data.get('vd_remarks', ''),
            data['vd_code']
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

@base.route('/customer_code/delete', methods=['POST'])
@login_required
def delete_customer_code():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    data = request.get_json()
    codes = data.get('codes', [])
    
    try:
        for code in codes:
            cursor.execute("DELETE FROM dbo.CODE_VENDOR WHERE vd_code = ?", (code,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

# 거래처 재무정보 관리
@base.route('/customer_code/financial/<vendor_code>')
@login_required
def customer_financial(vendor_code):
    """거래처별 재무정보 관리 페이지"""
    return render_template('base/customer_code/financial.html', vendor_code=vendor_code)

@base.route('/api/customer_code/financial/<vendor_code>')
@login_required
def get_customer_financial(vendor_code):
    """거래처별 재무정보 조회"""
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, vd_code, fiscal_year, capital, sales_revenue, operating_profit, remarks
            FROM dbo.VENDOR_FINANCIAL
            WHERE vd_code = ?
            ORDER BY fiscal_year DESC
        """, (vendor_code,))
        
        rows = cursor.fetchall()
        result = []
        for row in rows:
            result.append({
                'id': row.id,
                'vd_code': row.vd_code,
                'fiscal_year': row.fiscal_year,
                'capital': float(row.capital) if row.capital else 0,
                'sales_revenue': float(row.sales_revenue) if row.sales_revenue else 0,
                'operating_profit': float(row.operating_profit) if row.operating_profit else 0,
                'remarks': row.remarks if row.remarks else ''
            })
        
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@base.route('/api/customer_code/financial/save', methods=['POST'])
@login_required
def save_customer_financial():
    """거래처 재무정보 저장"""
    try:
        data = request.get_json()
        vendor_code = data.get('vendor_code')
        fiscal_year = data.get('fiscal_year')
        
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        # 중복 체크
        cursor.execute("""
            SELECT id FROM dbo.VENDOR_FINANCIAL 
            WHERE vd_code = ? AND fiscal_year = ?
        """, (vendor_code, fiscal_year))
        
        existing = cursor.fetchone()
        
        if existing:
            # 업데이트
            cursor.execute("""
                UPDATE dbo.VENDOR_FINANCIAL SET
                    capital = ?, sales_revenue = ?, operating_profit = ?, 
                    remarks = ?, updateuser = 'SYSTEM', updatedate = GETDATE()
                WHERE id = ?
            """, (
                data.get('capital'),
                data.get('sales_revenue'),
                data.get('operating_profit'),
                data.get('remarks'),
                existing.id
            ))
        else:
            # 신규 등록
            cursor.execute("""
                INSERT INTO dbo.VENDOR_FINANCIAL 
                (vd_code, fiscal_year, capital, sales_revenue, operating_profit, remarks, createuser, createdate)
                VALUES (?, ?, ?, ?, ?, ?, 'SYSTEM', GETDATE())
            """, (
                vendor_code,
                fiscal_year,
                data.get('capital'),
                data.get('sales_revenue'),
                data.get('operating_profit'),
                data.get('remarks')
            ))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

@base.route('/api/customer_code/financial/delete/<int:financial_id>', methods=['POST'])
@login_required
def delete_customer_financial(financial_id):
    """거래처 재무정보 삭제"""
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        cursor.execute("DELETE FROM dbo.VENDOR_FINANCIAL WHERE id = ?", (financial_id,))
        conn.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})

# 통화관리
@base.route('/currency')
@login_required
def currency():
    return render_template('base/currency_code/list.html')

@base.route('/currency_code')
@login_required
def currency_code():
    return render_template('base/currency_code/list.html')

@base.route('/currency_code/new')
@login_required
def currency_code_new():
    return render_template('base/currency_code/new.html')

@base.route('/currency_code/edit/<code>')
@login_required
def currency_code_edit(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dbo.code_currency WHERE currency_code = ?", (code,))
    currency = cursor.fetchone()
    if not currency:
        return render_template('errors/404.html'), 404
    return render_template('base/currency_code/edit.html', code=code, currency=currency)

@base.route('/currency/list')
@login_required
def currency_list():
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.code_currency")
        currencies = cursor.fetchall()
        
        result = []
        for currency in currencies:
            result.append({
                'code': currency.currency_code.strip() if currency.currency_code else '',
                'name': currency.currency_name.strip() if currency.currency_name else '',
                'exchangeRate': float(currency.ex_price) if currency.ex_price else 0,
                'baseYn': currency.base_yn.strip() if currency.base_yn else 'N',
                'usage': currency.usage.strip() if currency.usage else 'Y'
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@base.route('/currency/search')
@login_required
def currency_search():
    code = request.args.get('code', '').strip()
    name = request.args.get('name', '').strip()
    
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    query = "SELECT * FROM dbo.code_currency WHERE 1=1"
    params = []
    
    if code:
        query += " AND currency_code LIKE ?"
        params.append(f"%{code}%")
    if name:
        query += " AND currency_name LIKE ?"
        params.append(f"%{name}%")
    
    cursor.execute(query, params)
    currencies = cursor.fetchall()
    
    result = []
    for currency in currencies:
        result.append({
            'code': currency.currency_code.strip() if currency.currency_code else '',
            'name': currency.currency_name.strip() if currency.currency_name else '',
            'exchangeRate': float(currency.ex_price) if currency.ex_price else 0,
            'baseYn': currency.base_yn.strip() if currency.base_yn else 'N',
            'usage': currency.usage.strip() if currency.usage else 'Y'
        })
    return jsonify(result)

@base.route('/currency/new')
@login_required
def currency_new():
    return render_template('base/currency_code/new.html')

@base.route('/currency/edit/<code>')
@login_required
def currency_edit(code):
    return render_template('base/currency_code/edit.html', code=code)

@base.route('/currency/detail/<code>')
@login_required
def currency_detail(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dbo.code_currency WHERE currency_code = ?", (code,))
    currency = cursor.fetchone()
    
    if not currency:
        return jsonify({"error": "Currency not found"}), 404
    
    result = {
        'code': currency.currency_code.strip() if currency.currency_code else '',
        'name': currency.currency_name.strip() if currency.currency_name else '',
        'exchangeRate': float(currency.ex_price) if currency.ex_price else 0,
        'baseYn': currency.base_yn.strip() if currency.base_yn else 'N',
        'usage': currency.usage.strip() if currency.usage else 'Y'
    }
    return jsonify(result)

@base.route('/currency/save', methods=['POST'])
@login_required
def currency_save():
    data = request.get_json()
    
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO dbo.code_currency (
                currency_code, currency_name, ex_price, base_yn, usage,
                createuser, createdate
            ) VALUES (?, ?, ?, ?, ?, 'SYSTEM', GETDATE())
        """, (
            data['code'], data['name'], data['exchangeRate'],
            data['baseYn'], data['usage']
        ))
        conn.commit()
        return jsonify({'success': True, 'redirect': url_for('base.currency_code')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@base.route('/currency/update', methods=['POST'])
@login_required
def currency_update():
    data = request.get_json()
    
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE dbo.code_currency SET
                currency_name = ?, ex_price = ?, base_yn = ?, usage = ?,
                updateuser = 'SYSTEM', updatedate = GETDATE()
            WHERE currency_code = ?
        """, (
            data['name'], data['exchangeRate'], data['baseYn'],
            data['usage'], data['code']
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@base.route('/currency/delete', methods=['POST'])
@login_required
def currency_delete():
    data = request.get_json()
    codes = data.get('codes', [])
    
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        for code in codes:
            cursor.execute("DELETE FROM dbo.code_currency WHERE currency_code = ?", (code,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@base.route('/api/currencies')
@login_required
def api_currencies():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM dbo.code_currency WHERE usage = 'Y'")
    currencies = cursor.fetchall()
    
    result = []
    for currency in currencies:
        result.append({
            'code': currency.currency_code.strip() if currency.currency_code else '',
            'name': currency.currency_name.strip() if currency.currency_name else '',
            'exchangeRate': float(currency.ex_price) if currency.ex_price else 0
        })
    return jsonify(result)

# 단위정보 관리
@base.route('/unit')
@login_required
def unit():
    return redirect(url_for('base.unit_code'))

@base.route('/unit/options')
@login_required
def unit_options():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT unit_code, unit_name FROM dbo.code_unit WHERE usage = 'Y'")
    rows = cursor.fetchall()
    units = []
    for row in rows:
        units.append({
            "code": row.unit_code.strip() if row.unit_code else '',
            "name": row.unit_name.strip() if row.unit_name else ''
        })
    return jsonify(units)

@base.route('/unit_code')
@login_required
def unit_code():
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.code_unit")
        units = cursor.fetchall()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            result = []
            for unit in units:
                result.append({
                    'code': unit.unit_code.strip() if unit.unit_code else '',
                    'name': unit.unit_name.strip() if unit.unit_name else '',
                    'usage': unit.usage.strip() if unit.usage else 'Y',
                    'remark': unit.remark.strip() if unit.remark else ''
                })
            return jsonify(result)
        
        return render_template('base/unit_code/list.html')
    except Exception as e:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'error': str(e)}), 500
        return render_template('errors/500.html'), 500

@base.route('/unit_code/search')
@login_required
def unit_code_search():
    code = request.args.get('code', '').strip()
    name = request.args.get('name', '').strip()
    
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        query = "SELECT * FROM dbo.code_unit WHERE 1=1"
        params = []
        
        if code:
            query += " AND unit_code LIKE ?"
            params.append(f"%{code}%")
        if name:
            query += " AND unit_name LIKE ?"
            params.append(f"%{name}%")
        
        cursor.execute(query, params)
        units = cursor.fetchall()
        
        result = []
        for unit in units:
            result.append({
                'code': unit.unit_code.strip() if unit.unit_code else '',
                'name': unit.unit_name.strip() if unit.unit_name else '',
                'usage': unit.usage.strip() if unit.usage else 'Y',
                'remark': unit.remark.strip() if unit.remark else ''
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@base.route('/unit_code/new')
@login_required
def unit_code_new():
    return render_template('base/unit_code/new.html')

@base.route('/unit_code/edit/<code>')
@login_required
def unit_code_edit(code):
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.code_unit WHERE unit_code = ?", (code,))
        unit = cursor.fetchone()
        
        if not unit:
            return render_template('errors/404.html'), 404
            
        return render_template('base/unit_code/edit.html', code=code)
    except Exception as e:
        return render_template('errors/500.html'), 500
    finally:
        if 'conn' in locals():
            conn.close()

@base.route('/unit_code/list')
@login_required
def unit_code_list():
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.code_unit")
        units = cursor.fetchall()
        
        result = []
        for unit in units:
            result.append({
                'code': unit.unit_code.strip() if unit.unit_code else '',
                'name': unit.unit_name.strip() if unit.unit_name else '',
                'usage': unit.usage.strip() if unit.usage else 'Y',
                'remark': unit.remark.strip() if unit.remark else ''
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@base.route('/unit_code/detail/<code>')
@login_required
def unit_code_detail(code):
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.code_unit WHERE unit_code = ?", (code,))
        unit = cursor.fetchone()
        
        if not unit:
            return jsonify({"error": "Unit not found"}), 404
        
        result = {
            'code': unit.unit_code.strip() if unit.unit_code else '',
            'name': unit.unit_name.strip() if unit.unit_name else '',
            'usage': unit.usage.strip() if unit.usage else 'Y',
            'remark': unit.remark.strip() if unit.remark else ''
        }
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@base.route('/unit_code/save', methods=['POST'])
@login_required
def unit_code_save():
    data = request.get_json()
    
    try:
        # 필수 필드 검증
        if not data.get('code') or not data.get('name'):
            return jsonify({'success': False, 'error': 'Required fields are missing'}), 400

        # 데이터 정제
        code = data['code'].strip()
        name = data['name'].strip()
        usage = data.get('usage', 'Y').strip()
        remark = data.get('remark', '').strip()

        # 중복 체크
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM dbo.code_unit WHERE unit_code = ?", (code,))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'error': 'Unit code already exists'}), 400
        
        # 데이터 저장
        cursor.execute("""
            INSERT INTO dbo.code_unit (
                unit_code, unit_name, usage, remark,
                createuser, createdate
            ) VALUES (?, ?, ?, ?, 'SYSTEM', GETDATE())
        """, (code, name, usage, remark))
        
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@base.route('/unit_code/update', methods=['POST'])
@login_required
def unit_code_update():
    try:
        data = request.get_json()
        
        if not data or not data.get('code') or not data.get('name'):
            return jsonify({'success': False, 'error': 'Required fields are missing'}), 400
            
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        cursor.execute("""
            UPDATE dbo.code_unit SET
                unit_name = ?,
                usage = ?,
                remark = ?,
                updateuser = 'SYSTEM',
                updatedate = GETDATE()
            WHERE unit_code = ?
        """, (
            data['name'].strip(),
            data.get('usage', 'Y').strip(),
            data.get('remark', '').strip(),
            data['code'].strip()
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        if 'conn' in locals():
            conn.close()

@base.route('/unit_code/delete', methods=['POST'])
@login_required
def unit_code_delete():
    data = request.get_json()
    codes = data.get('codes', [])
    
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        for code in codes:
            cursor.execute("DELETE FROM dbo.code_unit WHERE unit_code = ?", (code,))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@base.route('/unit_code/check/<code>')
@login_required
def check_unit_code(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM dbo.code_unit WHERE unit_code = ?", (code,))
    exists = cursor.fetchone()[0] > 0
    
    return jsonify({'exists': exists})

@base.route('/transaction_type')
@login_required
def transaction_type():
    code = request.args.get('transactionCode', '').strip()
    name = request.args.get('transactionName', '').strip()
    
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    query = "SELECT TR_CODE, TR_NAME, TR_DIV, USAGE, REMARKS FROM CODE_TRANSACTION WHERE 1=1"
    params = []
    
    if code:
        query += " AND TR_CODE LIKE ?"
        params.append(f"%{code}%")
    if name:
        query += " AND TR_NAME LIKE ?"
        params.append(f"%{name}%")
    
    cursor.execute(query, params)
    transaction_types = cursor.fetchall()
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        result = []
        for row in transaction_types:
            result.append({
                'TR_CODE': row.TR_CODE.strip() if row.TR_CODE else '',
                'TR_NAME': row.TR_NAME.strip() if row.TR_NAME else '',
                'TR_DIV': row.TR_DIV.strip() if row.TR_DIV else '',
                'USAGE': row.USAGE.strip() if row.USAGE else 'Y',
                'REMARKS': row.REMARKS.strip() if row.REMARKS else ''
            })
        return jsonify(result)
    
    return render_template('base/transaction_code/list.html', transaction_types=transaction_types)

@base.route('/transaction_type/add', methods=['GET', 'POST'])
@login_required
def transaction_type_add():
    if request.method == 'POST':
        data = request.get_json()
        tr_code = data.get('tr_code')
        tr_name = data.get('tr_name')
        tr_div = data.get('tr_div')
        usage = data.get('usage', 'Y')
        remarks = data.get('remarks', '')
        
        # 필수 필드 검증
        if not tr_code or not tr_name:
            return jsonify({"success": False, "error": "Required fields are missing"}), 400
            
        try:
            conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
            cursor = conn.cursor()
            
            # 중복 체크
            cursor.execute("SELECT COUNT(*) as count FROM CODE_TRANSACTION WHERE TR_CODE = ?", (tr_code,))
            if cursor.fetchone().count > 0:
                return jsonify({"success": False, "error": "Transaction code already exists"}), 400
            
            cursor.execute("""
                INSERT INTO CODE_TRANSACTION 
                (TR_CODE, TR_NAME, TR_DIV, USAGE, REMARKS, CREATEUSER, CREATEDATE) 
                VALUES (?, ?, ?, ?, ?, ?, GETDATE())""",
                (tr_code, tr_name, tr_div, usage, remarks, 'SYSTEM'))
            conn.commit()
            
            return jsonify({"success": True})
        except Exception as e:
            return jsonify({"success": False, "error": str(e)}), 500
    
    return render_template('base/transaction_code/new.html')

@base.route('/transaction_type/edit/<code>', methods=['GET', 'POST'])
@login_required
def transaction_type_edit(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        tr_name = request.form['name']
        tr_div = request.form['division']
        usage = request.form.get('usage', 'Y')
        remarks = request.form.get('remarks', '')
        
        cursor.execute("""
            UPDATE CODE_TRANSACTION 
            SET TR_NAME=?, TR_DIV=?, USAGE=?, REMARKS=?, UPDATEUSER='SYSTEM', UPDATEDATE=GETDATE()
            WHERE TR_CODE=?""",
            (tr_name, tr_div, usage, remarks, code))
        conn.commit()
        
        flash('Transaction type updated successfully')
        return redirect(url_for('base.transaction_type'))
    
    cursor.execute("SELECT TR_CODE, TR_NAME, TR_DIV, USAGE, REMARKS FROM CODE_TRANSACTION WHERE TR_CODE = ?", (code,))
    transaction_type = cursor.fetchone()
    if not transaction_type:
        return render_template('errors/404.html'), 404
        
    return render_template('base/transaction_code/edit.html', 
                         transaction_type=transaction_type,
                         transaction_code=code)

@base.route('/transaction_type/detail/<code>')
@login_required
def transaction_type_detail(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT TR_CODE, TR_NAME, TR_DIV, USAGE, REMARKS FROM CODE_TRANSACTION WHERE TR_CODE = ?", (code,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    
    transaction = {
        "code": row.TR_CODE.strip(),
        "name": row.TR_NAME.strip() if row.TR_NAME else '',
        "division": row.TR_DIV.strip() if row.TR_DIV else '',
        "usage": row.USAGE.strip() if row.USAGE else 'Y',
        "remarks": row.REMARKS.strip() if row.REMARKS else ''
    }
    return jsonify(transaction)

@base.route('/transaction_type/update', methods=['POST'])
@login_required
def transaction_type_update():
    data = request.get_json()
    code = data.get('code')
    name = data.get('name')
    division = data.get('division')
    usage = data.get('usage', 'Y')
    remarks = data.get('remarks', '')

    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE CODE_TRANSACTION 
            SET TR_NAME=?, TR_DIV=?, USAGE=?, REMARKS=?, UPDATEUSER='SYSTEM', UPDATEDATE=GETDATE()
            WHERE TR_CODE=?""",
            (name, division, usage, remarks, code))
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@base.route('/check_transaction_type_code/<code>')
@login_required
def check_transaction_type_code(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) as count FROM CODE_TRANSACTION WHERE TR_CODE = ?", (code,))
    result = cursor.fetchone()
    return jsonify({'available': result.count == 0})

@base.route('/transaction_type/delete', methods=['POST'])
@login_required
def transaction_type_delete():
    data = request.get_json()
    codes = data.get('codes', [])
    if not codes:
        return jsonify({"success": False, "error": "No codes provided"})
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        query = f"DELETE FROM CODE_TRANSACTION WHERE TR_CODE IN ({','.join(['?']*len(codes))})"
        cursor.execute(query, codes)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@base.route('/transaction_type/excel')
@login_required
def transaction_type_excel():
    import pandas as pd
    from io import BytesIO
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT TR_CODE, TR_NAME, TR_DIV, USAGE, REMARKS FROM CODE_TRANSACTION")
    rows = cursor.fetchall()
    items = []
    for row in rows:
        items.append({
            "수불코드": row.TR_CODE,
            "수불명": row.TR_NAME,
            "구분": row.TR_DIV,
            "사용여부": row.USAGE,
            "비고": row.REMARKS
        })
    df = pd.DataFrame(items)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='수불코드')
        worksheet = writer.sheets['수불코드']
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            worksheet.set_column(idx, idx, max_length + 2)
    output.seek(0)
    from flask import send_file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='transaction_code_list.xlsx'
    )

@base.route('/item/list')
@login_required
def item_list():
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ItemCode, ItemName, Spec, unit, purchasePrice, salesprice, usage, remarks FROM ItemMaster")
            rows = cursor.fetchall()
            items = []
            for row in rows:
                items.append({
                    "code": row.ItemCode if row.ItemCode else "",
                    "name": row.ItemName if row.ItemName else "",
                    "spec": row.Spec if row.Spec else "",
                    "unit": row.unit if row.unit else "",
                    "purchasePrice": float(row.purchasePrice) if row.purchasePrice else 0,
                    "salesPrice": float(row.salesprice) if row.salesprice else 0,
                    "usage": row.usage if row.usage else "Y",
                    "remarks": row.remarks if row.remarks else ""
                })
            cursor.close()
            return jsonify(items)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Error in item_list: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@base.route('/item/save', methods=['POST'])
@login_required
def item_save():
    data = request.get_json()
    code = data.get('code')
    name = data.get('name')
    spec = data.get('spec')
    unit = data.get('unit')
    purchasePrice = data.get('purchasePrice')
    salesPrice = data.get('salesPrice')
    usage = data.get('usage')
    remarks = data.get('remarks')

    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO ItemMaster (ItemCode, ItemName, Spec, unit, purchasePrice, salesprice, usage, remarks) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (code, name, spec, unit, purchasePrice, salesPrice, usage, remarks)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@base.route('/item/check-duplicate')
@login_required
def item_check_duplicate():
    code = request.args.get('code')
    if not code:
        return jsonify({"isDuplicate": False})
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM ItemMaster WHERE ItemCode = ?", (code,))
    count = cursor.fetchone()[0]
    return jsonify({"isDuplicate": count > 0})

@base.route('/item/search')
@login_required
def item_search():
    code = request.args.get('code', '').strip()
    name = request.args.get('name', '').strip()
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    query = "SELECT ItemCode, ItemName, Spec, unit, purchasePrice, salesprice, usage, remarks FROM ItemMaster WHERE 1=1"
    params = []
    if code:
        query += " AND ItemCode LIKE ?"
        params.append(f"%{code}%")
    if name:
        query += " AND ItemName LIKE ?"
        params.append(f"%{name}%")
    cursor.execute(query, params)
    rows = cursor.fetchall()
    items = []
    for row in rows:
        items.append({
            "code": row.ItemCode,
            "name": row.ItemName,
            "spec": row.Spec,
            "unit": row.unit,
            "purchasePrice": row.purchasePrice,
            "salesPrice": row.salesprice,
            "usage": row.usage,
            "remarks": row.remarks
        })
    return jsonify(items)

@base.route('/item/delete', methods=['POST'])
@login_required
def item_delete():
    data = request.get_json()
    codes = data.get('codes', [])
    if not codes:
        return jsonify({"success": False, "error": "No codes provided"})
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        query = f"DELETE FROM ItemMaster WHERE ItemCode IN ({','.join(['?']*len(codes))})"
        cursor.execute(query, codes)
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@base.route('/item/detail/<code>')
@login_required
def item_detail(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT ItemCode, ItemName, Spec, unit, purchasePrice, salesprice, usage, remarks FROM ItemMaster WHERE ItemCode = ?", (code,))
    row = cursor.fetchone()
    if not row:
        return jsonify({"error": "Not found"}), 404
    item = {
        "code": row.ItemCode,
        "name": row.ItemName,
        "spec": row.Spec,
        "unit": row.unit,
        "purchasePrice": row.purchasePrice,
        "salesPrice": row.salesprice,
        "usage": row.usage,
        "remarks": row.remarks
    }
    return jsonify(item)

@base.route('/item/update', methods=['POST'])
@login_required
def item_update():
    data = request.get_json()
    code = data.get('code')
    name = data.get('name')
    spec = data.get('spec')
    unit = data.get('unit')
    purchasePrice = data.get('purchasePrice')
    salesPrice = data.get('salesPrice')
    usage = data.get('usage')
    remarks = data.get('remarks')

    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE ItemMaster SET ItemName=?, Spec=?, unit=?, purchasePrice=?, salesprice=?, usage=?, remarks=? WHERE ItemCode=?",
            (name, spec, unit, purchasePrice, salesPrice, usage, remarks, code)
        )
        conn.commit()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@base.route('/item/excel')
@login_required
def item_excel():
    import pandas as pd
    from io import BytesIO
    from flask import send_file, session  # ← session 추가

    # 엑셀은 영어로 고정
    lang = 'en'
    
    # 언어별 컬럼 헤더 정의
    headers = {
        'ko': {
            'ItemCode': '품목코드',
            'ItemName': '품목명',
            'Spec': '규격',
            'unit': '단위',
            'purchasePrice': '매입단가',
            'salesprice': '매출단가',
            'usage': '사용여부',
            'remarks': '비고'
        },
        'en': {
            'ItemCode': 'Item Code',
            'ItemName': 'Item Name',
            'Spec': 'Specification',
            'unit': 'Unit',
            'purchasePrice': 'Purchase Price',
            'salesprice': 'Sales Price',
            'usage': 'Usage',
            'remarks': 'Remarks'
        },
        'th': {
            'ItemCode': 'รหัสสินค้า',
            'ItemName': 'ชื่อสินค้า',
            'Spec': 'รายละเอียด',
            'unit': 'หน่วย',
            'purchasePrice': 'ราคาซื้อ',
            'salesprice': 'ราคาขาย',
            'usage': 'การใช้งาน',
            'remarks': 'หมายเหตุ'
        }
    }
    
    # 기본값은 한글
    h = headers.get(lang, headers['ko'])
    
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT ItemCode, ItemName, Spec, unit, purchasePrice, salesprice, usage, remarks FROM ItemMaster ORDER BY ItemCode")
        rows = cursor.fetchall()
        
        items = []
        for row in rows:
            items.append({
                h['ItemCode']: row.ItemCode or '',
                h['ItemName']: row.ItemName or '',
                h['Spec']: row.Spec or '',
                h['unit']: row.unit or '',
                h['purchasePrice']: row.purchasePrice or 0,
                h['salesprice']: row.salesprice or 0,
                h['usage']: row.usage or 'Y',
                h['remarks']: row.remarks or ''
            })
        
        cursor.close()
        conn.close()
        
        # 데이터가 없을 때 처리
        if not items:
            items = [{h[k]: '' for k in ['ItemCode', 'ItemName', 'Spec', 'unit', 'purchasePrice', 'salesprice', 'usage', 'remarks']}]
        
        df = pd.DataFrame(items)
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            sheet_name = h['ItemCode'][:31]  # Excel 시트명 최대 31자 제한
            df.to_excel(writer, index=False, sheet_name=sheet_name)
            
            workbook = writer.book
            worksheet = writer.sheets[sheet_name]
            
            # 헤더 포맷
            header_format = workbook.add_format({
                'bold': True,
                'bg_color': '#F0F0F0',
                'border': 1,
                'align': 'center',
                'valign': 'vcenter'
            })
            
            # 숫자 포맷
            num_format = workbook.add_format({
                'num_format': '#,##0.00',
                'border': 1
            })
            
            # 텍스트 포맷
            text_format = workbook.add_format({
                'border': 1
            })
            
            # 컬럼 너비 자동 조정
            for idx, col in enumerate(df.columns):
                series = df[col]
                max_len = max(
                    series.astype(str).map(len).max(),
                    len(str(col))
                ) + 2
                worksheet.set_column(idx, idx, max_len)
                
                # 헤더 포맷 적용
                worksheet.write(0, idx, col, header_format)
                
                # 숫자 컬럼에 포맷 적용
                if col in [h['purchasePrice'], h['salesprice']]:
                    for row_idx in range(1, len(df) + 1):
                        worksheet.write(row_idx, idx, df.iloc[row_idx-1, idx], num_format)
        
        output.seek(0)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'item_code_list_{timestamp}.xlsx'
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
        
    except Exception as e:
        current_app.logger.error(f"Item excel export failed: {e}")
        return jsonify({'error': 'Excel export failed'}), 500

@base.route('/customer_code/excel')
@login_required
def customer_code_excel():
    import pandas as pd
    from io import BytesIO
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT vd_code, vd_name, vd_biz_number, vd_tax_id, vd_president, vd_kind, vd_item, vd_phone, vd_address, vd_charger, vd_charger_phone, usage, createuser, createdate, updateuser, updatedate FROM code_vendor")
    rows = cursor.fetchall()
    items = []
    for row in rows:
        items.append({
            "거래처코드": row.vd_code,
            "거래처명": row.vd_name,
            "사업자번호": row.vd_biz_number,
            "사업자등록번호": row.vd_tax_id,
            "대표자": row.vd_president,
            "업태": row.vd_kind,
            "종목": row.vd_item,
            "전화번호": row.vd_phone,
            "주소": row.vd_address,
            "담당자": row.vd_charger,
            "담당자연락처": row.vd_charger_phone,
            "사용여부": row.usage,
            "등록자": row.createuser,
            "등록일": row.createdate,
            "수정자": row.updateuser,
            "수정일": row.updatedate
        })
    df = pd.DataFrame(items)
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='거래처코드')
        worksheet = writer.sheets['거래처코드']
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            worksheet.set_column(idx, idx, max_length + 2)
    output.seek(0)
    from flask import send_file
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='customer_code_list.xlsx'
    )
    
@base.route('/account_list')
@login_required
def account_list():
    company_filter = (request.args.get('company') or '').strip()
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    sql = """
        SELECT id, company, name_en, name_th, name_ko, account_code
        FROM dbo.code_Account
        WHERE 1=1
    """
    params = []
    if company_filter:
        sql += " AND LTRIM(RTRIM(ISNULL(company, N''))) = ?"
        params.append(company_filter)
    sql += " ORDER BY company, account_code"
    cursor.execute(sql, params)
    accounts = cursor.fetchall()

    cursor.execute("""
        SELECT DISTINCT company
        FROM dbo.code_Account
        WHERE company IS NOT NULL AND LTRIM(RTRIM(company)) <> ''
        ORDER BY company
    """)
    company_options = [
        {'value': (r[0] or '').strip(), 'label': (r[0] or '').strip()}
        for r in cursor.fetchall()
        if (r[0] or '').strip()
    ]
    if company_filter and company_filter not in {o['value'] for o in company_options}:
        company_filter = ''

    cursor.close()
    conn.close()
    return render_template(
        'base/account/list.html',
        accounts=accounts,
        company_options=company_options,
        filters={'company': company_filter},
    )


@base.route('/account_add', methods=['GET', 'POST'])
@login_required
def account_add():
    if request.method == 'GET':
        return render_template('base/account/add.html')

    account_code = (request.form.get('account_code') or '').strip()
    company = (request.form.get('company') or '').strip()
    name_en = (request.form.get('name_en') or '').strip()
    name_th = (request.form.get('name_th') or '').strip()
    name_ko = (request.form.get('name_ko') or '').strip()

    if not account_code or not company or not name_en:
        flash('Account Code, Company, Name(EN) are required.', 'error')
        return render_template('base/account/add.html'), 400

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(1) FROM dbo.code_Account WHERE account_code = ?", (account_code,))
    exists = cursor.fetchone()[0] > 0
    if exists:
        cursor.close()
        conn.close()
        flash('Account code already exists.', 'error')
        return render_template('base/account/add.html'), 409

    cursor.execute(
        """
        INSERT INTO dbo.code_Account (company, name_en, name_th, name_ko, account_code)
        VALUES (?, ?, ?, ?, ?)
        """,
        (company, name_en, name_th, name_ko, account_code)
    )
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('base.account_list'))


@base.route('/check_account_code/<account_code>')
@login_required
def check_account_code(account_code):
    code = (account_code or '').strip()
    if not code:
        return jsonify({'available': False})

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(1) FROM dbo.code_Account WHERE account_code = ?", (code,))
    exists = cursor.fetchone()[0] > 0
    cursor.close()
    conn.close()
    return jsonify({'available': not exists})

@base.route('/account/hierarchy')
@login_required
def account_hierarchy_api():
    """Return account hierarchy as JSON for the account picker.

    When building node labels choose the language-specific name field based on
    session['language']:
      - 'ko' -> NAME_KO
      - 'en' -> NAME_EN
      - 'th' -> NAME_TH
    Falls back to other available name fields if the preferred one is empty.
    """
    try:
        from flask import session, current_app
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        # parent_account_code 컬럼이 제거되어 계층은 현재 flat 목록으로 반환
        cursor.execute("""
            SELECT account_code, name_ko, name_en, name_th
            FROM dbo.code_Account
            ORDER BY account_code
        """)
        rows = cursor.fetchall()

        lang = (session.get('language') or 'ko').lower()

        def pick_name(row):
            # row: (account_code, name_ko, name_en, name_th)
            name_ko = row[1] or ''
            name_en = row[2] or ''
            name_th = row[3] or ''
            if lang == 'ko':
                return name_ko or name_en or name_th or ''
            if lang == 'en':
                return name_en or name_ko or name_th or ''
            if lang == 'th':
                return name_th or name_en or name_ko or ''
            # default fallback
            return name_en or name_ko or name_th or ''

        # build nodes dict (flat: parent 없음)
        nodes = {}
        for r in rows:
            code = r[0]
            name = pick_name(r)
            nodes[code] = {'code': code, 'name': name, 'parent': None, 'children': []}

        # flat 목록을 roots로 사용
        roots = list(nodes.values())

        cursor.close()
        conn.close()
        return jsonify(roots)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to build account hierarchy: {e}")
        return jsonify([]), 500


@base.route('/account/company-options')
@login_required
def account_company_options():
    """Return distinct company values for account add form."""
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT company
            FROM dbo.code_Account
            WHERE company IS NOT NULL AND LTRIM(RTRIM(company)) <> ''
            ORDER BY company
        """)
        companies = [row[0] for row in cursor.fetchall()]
        cursor.close()
        conn.close()
        return jsonify(companies)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to load account company options: {e}")
        return jsonify([]), 500


# --- Customer Code Expense routes (aliases that reuse existing handlers) ---
@base.route('/customer_code_expense')
@login_required
def customer_code_expense():
    from flask import current_app
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    code = request.args.get('customerCode', '').strip()
    name = request.args.get('customerName', '').strip()

    query = "SELECT * FROM dbo.CODE_VENDOR_expense WHERE 1=1"
    params = []

    if code:
        query += " AND vd_code LIKE ?"
        params.append(f"%{code}%")
    if name:
        query += " AND vd_name LIKE ?"
        params.append(f"%{name}%")

    # add ordering to ensure consistent ascending vendor list
    query += " ORDER BY vd_code ASC"

    # 🔍 디버깅 로그 추가
    current_app.logger.info(f"🔍 VENDOR_EXPENSE QUERY: {query}")
    current_app.logger.info(f"🔍 PARAMS: {params}")
    current_app.logger.info(f"🔍 IS_AJAX: {request.headers.get('X-Requested-With')}")
    
    cursor.execute(query, params)
    vendors = cursor.fetchall()
    
    current_app.logger.info(f"🔍 VENDORS_COUNT: {len(vendors)}")
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        result = []
        for vendor in vendors:
            result.append({
                'vd_code': vendor.vd_code.strip(),
                'vd_name': vendor.vd_name.strip(),
                'vd_biz_number': vendor.vd_biz_number.strip() if vendor.vd_biz_number else '',
                'vd_tax_id': vendor.vd_tax_id.strip() if vendor.vd_tax_id else '',
                'vd_president': vendor.vd_president.strip() if vendor.vd_president else '',
                'vd_kind': vendor.vd_kind.strip() if vendor.vd_kind else '',
                'vd_item': vendor.vd_item.strip() if vendor.vd_item else '',
                'vd_phone': vendor.vd_phone.strip() if vendor.vd_phone else '',
                'vd_address': vendor.vd_address.strip() if vendor.vd_address else '',
                'vd_charger': vendor.vd_charger.strip() if vendor.vd_charger else '',
                'vd_charger_phone': vendor.vd_charger_phone.strip() if vendor.vd_charger_phone else '',
                'usage': vendor.usage.strip() if vendor.usage else 'Y',
                'vd_division': getattr(vendor, 'vd_division', '') if hasattr(vendor, 'vd_division') else '',
                'vd_website': getattr(vendor, 'vd_website', '') if hasattr(vendor, 'vd_website') else '',
                'vd_remarks': getattr(vendor, 'vd_remarks', '') if hasattr(vendor, 'vd_remarks') else ''
            })
        current_app.logger.info(f"🔍 RETURNING JSON: {len(result)} items")
        return jsonify(result)
    
    current_app.logger.info("🔍 RETURNING HTML TEMPLATE")
    return render_template('base/customer_code_expense/list.html')

@base.route('/customer_code_expense/new')
@base.route('/customer_code_expense/add')
@login_required
def customer_code_expense_new():
    return render_template('base/customer_code_expense/new.html')

# --- expense 전용 체크 (CODE_VENDOR_expense 체크) ---
@base.route('/customer_code_expense/check/<code>')
@login_required
def check_customer_code_expense(code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM dbo.CODE_VENDOR_expense WHERE vd_code = ?", (code,))
    exists = cursor.fetchone()[0] > 0
    cursor.close()
    conn.close()
    return jsonify({'exists': exists})

@base.route('/customer_code_expense/detail/<code>')
@login_required
def customer_code_expense_detail(code):
    return customer_code_detail(code)

@base.route('/customer_code_expense/edit/<code>')
@login_required
def customer_code_expense_edit(code):
    # 원본에서 vendor 존재 체크 후 edit 템플릿 렌더하는 로직이 있으므로 동일하게 처리
    conn = None
    try:
        # 재사용: 기존 edit 핸들러는 render_template('base/customer_code/edit.html')
        # 여기서는 expense 전용 템플릿을 사용하기 위해 DB 쿼리만 재사용
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.CODE_VENDOR WHERE vd_code = ?", (code,))
        vendor = cursor.fetchone()
        if not vendor:
            return render_template('errors/404.html'), 404
        return render_template('base/customer_code_expense/edit.html')
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn:
            conn.close()

@base.route('/customer_code_expense/save', methods=['POST'])
@login_required
def save_customer_code_expense():
    data = request.get_json()
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO dbo.CODE_VENDOR_expense (
                vd_code, vd_name, vd_biz_number, vd_tax_id, vd_president, vd_kind,
                vd_item, vd_phone, vd_address, vd_charger, vd_charger_phone,
                usage, vd_division, vd_website, vd_remarks, createuser, createdate
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'SYSTEM', GETDATE())
        """, (
            data.get('vd_code'),
            data.get('vd_name'),
            data.get('vd_biz_number'),
            data.get('vd_tax_id', ''),
            data.get('vd_president'),
            data.get('vd_kind'),
            data.get('vd_item'),
            data.get('vd_phone'),
            data.get('vd_address'),
            data.get('vd_charger'),
            data.get('vd_charger_phone'),
            data.get('usage', 'Y'),
            data.get('vd_division', ''),
            data.get('vd_website', ''),
            data.get('vd_remarks', '')
        ))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try:
            cursor.close()
            conn.close()
        except:
            pass

@base.route('/customer_code_expense/update', methods=['POST'])
@login_required
def update_customer_code_expense():
    return update_customer_code()

@base.route('/customer_code_expense/delete', methods=['POST'])
@login_required
def delete_customer_code_expense():
    return delete_customer_code()

@base.route('/customer_code_expense/financial/<vendor_code>')
@login_required
def customer_financial_expense(vendor_code):
    return render_template('base/customer_code_expense/financial.html', vendor_code=vendor_code)

@base.route('/api/customer_code_expense/financial/<vendor_code>')
@login_required
def get_customer_financial_expense(vendor_code):
    return get_customer_financial(vendor_code)

@base.route('/api/customer_code_expense/financial/save', methods=['POST'])
@login_required
def save_customer_financial_expense():
    return save_customer_financial()

@base.route('/api/customer_code_expense/financial/delete/<int:financial_id>', methods=['POST'])
@login_required
def delete_customer_financial_expense(financial_id):
    return delete_customer_financial(financial_id)

# --- vendor expense account APIs ---
@base.route('/api/customer_code_expense/accounts/<vd_code>')
@login_required
def api_get_vendor_expense_accounts(vd_code):
    """Return accounts for given vd_code from dbo.code_vendor_expense_acc"""
    try:
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute("SELECT bank, vd_account, is_master, remark FROM dbo.code_vendor_expense_acc WHERE vd_code = ?", (vd_code,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                'vd_account': r.vd_account.strip() if getattr(r, 'vd_account', None) else '',
                'is_master': r.is_master,
                'remark': r.remark if getattr(r, 'remark', None) else '',
                'bank': r.bank.strip() if getattr(r, 'bank', None) else ''
            })
        cursor.close()
        conn.close()
        return jsonify(result)
    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"Failed to load vendor expense accounts for {vd_code}: {e}")
        return jsonify({'error': str(e)}), 500

@base.route('/api/customer_code_expense/accounts/save', methods=['POST'])
@login_required
def api_save_vendor_expense_accounts():
    """Save accounts for given vd_code using upsert + delete-missing strategy.
    Avoid referencing an 'id' column that may not exist in the target table.
    """
    data = request.get_json() or {}
    vd_code = data.get('vd_code')
    accounts = data.get('accounts', [])
    if not vd_code:
        return jsonify({'success': False, 'error': 'vd_code required'}), 400

    try:
        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;'
        )
        cursor = conn.cursor()

        # Load existing accounts for this vendor (only vd_account; do NOT assume 'id' exists)
        cursor.execute("SELECT vd_account FROM dbo.code_vendor_expense_acc WHERE vd_code = ?", (vd_code,))
        rows = cursor.fetchall()
        existing = {}
        for r in rows:
            acc_num = getattr(r, 'vd_account', None)
            if acc_num is not None:
                existing[str(acc_num).strip()] = True

        incoming_set = set()
        # Process incoming accounts: upsert (update if exists, insert if not)
        for acc in accounts:
            vd_account = (acc.get('vd_account') or '').strip()
            if not vd_account:
                continue
            incoming_set.add(vd_account)
            bank = (acc.get('bank') or acc.get('vd_bank') or acc.get('vdbank') or '').strip()
            is_master = 'Y' if acc.get('is_master') in ('Y', '1', True) else 'N'
            remark = (acc.get('remark') or '').strip()

            if vd_account in existing:
                # update existing row
                cursor.execute("""
                    UPDATE dbo.code_vendor_expense_acc
                    SET bank = ?, is_master = ?, remark = ?, updateuser = 'SYSTEM', updatedate = GETDATE()
                    WHERE vd_code = ? AND vd_account = ?
                """, (bank, is_master, remark, vd_code, vd_account))
            else:
                # insert new row
                cursor.execute("""
                    INSERT INTO dbo.code_vendor_expense_acc
                    (vd_code, bank, vd_account, is_master, remark, createuser, createdate)
                    VALUES (?, ?, ?, ?, ?, 'SYSTEM', GETDATE())
                """, (vd_code, bank, vd_account, is_master, remark))

        # Delete DB rows that are not present in incoming payload
        to_delete = [acc_num for acc_num in existing.keys() if acc_num not in incoming_set]
        if to_delete:
            placeholders = ",".join(["?"] * len(to_delete))
            params = [vd_code] + to_delete
            cursor.execute(f"DELETE FROM dbo.code_vendor_expense_acc WHERE vd_code = ? AND vd_account IN ({placeholders})", params)

        conn.commit()
        cursor.close()
        conn.close()
        return jsonify({'success': True})
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        from flask import current_app
        current_app.logger.error(f"Failed to save vendor expense accounts for {vd_code}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@base.route('/customer_code_expense/excel')
@login_required
def customer_code_expense_excel():
    """엑셀 다운로드 - Customer Code Expense (BusinessCost 데이터를 포함)"""
    import pandas as pd
    from io import BytesIO
    from flask import send_file, session, current_app

    try:
        part = request.args.get('part', '').strip()
        vendor = request.args.get('vendor', '').strip()

        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;'
        )
        cursor = conn.cursor()

        query = """
            SELECT m.id, m.customer_id, v.vd_name, m.part_name, m.scrap, m.crush_fee,
                   m.melting, m.melting_color, m.create_by, m.creation_date
            FROM dbo.MaterialCost m
            LEFT JOIN dbo.CODE_VENDOR v ON m.customer_id = v.vd_code
            WHERE 1=1
        """
        params = []
        if part:
            query += " AND m.part_name LIKE ?"
            params.append(f"%{part}%")
        if vendor:
            query += " AND m.customer_id = ?"
            params.append(vendor)
        query += " ORDER BY m.id"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        items = []
        for r in rows:
            creation_date = getattr(r, 'creation_date', None)
            items.append({
                "ID": getattr(r, 'id', '') or '',
                "Vendor Code": getattr(r, 'customer_id', '') or '',
                "Vendor Name": getattr(r, 'vd_name', '') or '',
                "Part Name": getattr(r, 'part_name', '') or '',
                "Scrap": getattr(r, 'scrap', '') if getattr(r, 'scrap', None) is not None else '',
                "Crush Fee": getattr(r, 'crush_fee', '') if getattr(r, 'crush_fee', None) is not None else '',
                "Melting": getattr(r, 'melting', '') if getattr(r, 'melting', None) is not None else '',
                "Melting Color": getattr(r, 'melting_color', '') or '',
                "Create By": getattr(r, 'create_by', '') or '',
                "Creation Date": creation_date.strftime('%Y-%m-%d %H:%M:%S') if creation_date else ''
            })

        df = pd.DataFrame(items)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='BusinessCost')
            worksheet = writer.sheets['BusinessCost']
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
                worksheet.set_column(idx, idx, max_length + 2)
        output.seek(0)
        cursor.close()
        conn.close()

        filename = f"business_cost_list_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.exception("Failed to export business_cost excel")
        return jsonify({'error': 'Excel download failed', 'detail': str(e)}), 500

@base.route('/business_cost')
@login_required
def business_cost_list_page():
    return render_template('base/business_cost/list.html')

@base.route('/business_cost/list')
@login_required
def business_cost_list():
    from flask import current_app
    try:
        part = request.args.get('part','').strip()
        vendor = request.args.get('vendor','').strip()

        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;'
        )
        cursor = conn.cursor()

        query = """
            SELECT m.id, m.customer_id, v.vd_name, m.part_name, m.scrap, m.crush_fee,
                   m.melting, m.melting_color, m.create_by, m.creation_date
            FROM dbo.MaterialCost m
            LEFT JOIN dbo.CODE_VENDOR v ON m.customer_id = v.vd_code
            WHERE 1=1
        """
        params = []
        if part:
            query += " AND part_name LIKE ?"
            params.append(f"%{part}%")
        if vendor:
            query += " AND customer_id = ?"
            params.append(vendor)
        query += " ORDER BY id"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        result = []
        for r in rows:
            result.append({
                'id': r[0],
                'customer_id': r[1],
                'vd_name': r[2] if r[2] else '',          # vd_name 컬럼이 아니라 사진의 순서상 vd_name 자리에 part_name이 보이므로 JS와 일치시키려면 vd_name 대신 part_name 매핑 고려
                'part_name': r[3] or '',
                'scrap': r[4],
                'crush_fee': r[5],
                'melting': r[6],
                'melting_color': r[7] or '',
                'create_by': r[8] or '',
                'creation_date': r[9].isoformat() if hasattr(r[9], 'isoformat') else (str(r[9]) if r[8] is not None else '')
            })

        cursor.close()
        conn.close()
        return jsonify(result)
    except Exception as e:
        current_app.logger.exception('Failed to load business cost list')
        return jsonify({'error': str(e)}), 500

@base.route('/business_cost/excel')
@login_required
def business_cost_excel():
    from flask import current_app
    try:
        part = request.args.get('part', '').strip()
        vendor = request.args.get('vendor', '').strip()

        conn = pyodbc.connect(
            'DRIVER={ODBC Driver 17 for SQL Server};'
            'SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;'
        )
        cursor = conn.cursor()

        query = """
            SELECT m.id, m.customer_id, v.vd_name, m.part_name, m.scrap, m.crush_fee,
                   m.melting, m.melting_color, m.create_by, m.creation_date
            FROM dbo.MaterialCost m
            LEFT JOIN dbo.CODE_VENDOR v ON m.customer_id = v.vd_code
            WHERE 1=1
        """
        params = []
        if part:
            query += " AND m.part_name LIKE ?"
            params.append(f"%{part}%")
        if vendor:
            query += " AND m.customer_id = ?"
            params.append(vendor)
        query += " ORDER BY m.id"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        items = []
        for r in rows:
            # 안전하게 컬럼값 추출
            def gv(idx, name=None):
                return getattr(r, name, None) if name and hasattr(r, name) else (r[idx] if idx < len(r) else None)

            creation_date = gv(9, 'creation_date')
            items.append({
                "ID": gv(0, 'id') or '',
                "Vendor Code": gv(1, 'customer_id') or '',
                "Vendor Name": gv(2, 'vd_name') or '',
                "Part Name": gv(3, 'part_name') or '',
                "Scrap": gv(4, 'scrap') if gv(4, 'scrap') is not None else '',
                "Crush Fee": gv(5, 'crush_fee') if gv(5, 'crush_fee') is not None else '',
                "Melting": gv(6, 'melting') if gv(6, 'melting') is not None else '',
                "Melting Color": gv(7, 'melting_color') or '',
                "Create By": gv(8, 'create_by') or '',
                "Creation Date": creation_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(creation_date, 'strftime') else (str(creation_date) if creation_date is not None else '')
            })

        df = pd.DataFrame(items)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False, sheet_name='BusinessCost')
            worksheet = writer.sheets['BusinessCost']
            for idx, col in enumerate(df.columns):
                max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
                worksheet.set_column(idx, idx, min(max_length + 3, 50))
        output.seek(0)

        cursor.close()
        conn.close()

        filename = f"business_cost_list_{pd.Timestamp.now().strftime('%Y%m%d')}.xlsx"
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        current_app.logger.exception("Failed to export business_cost excel")
        return jsonify({'error': 'Excel download failed', 'detail': str(e)}), 500


# ══════════════════════════════════════════════════════
#  Process Line Management
#  Table: dbo.code_product_line
# ══════════════════════════════════════════════════════

@base.route('/process_line')
@login_required
def process_line_page():
    return render_template('base/process_line/list.html')

# ↓ 이 라우트 추가
@base.route('/process_line/new')
@login_required
def process_line_new():
    return render_template('base/process_line/new.html')

@base.route('/process_line/edit/<int:row_id>')
@login_required
def process_line_edit(row_id):
    return render_template('base/process_line/edit.html', row_id=row_id)

@base.route('/process_line/list')
@login_required
def process_line_list():
    company_code = request.args.get('company_code', '').strip()
    process      = request.args.get('process',      '').strip()
    product_line = request.args.get('product_line', '').strip()

    try:
        conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()

        query  = """SELECT id, company_code, process, product_line,
                           setup_date, product_startdate, remark,
                           created_by, creation_date, updated_by, update_date
                    FROM dbo.code_product_line WHERE 1=1"""
        params = []
        if company_code:
            query += " AND company_code LIKE ?"
            params.append(f"%{company_code}%")
        if process:
            query += " AND process LIKE ?"
            params.append(f"%{process}%")
        if product_line:
            query += " AND product_line LIKE ?"
            params.append(f"%{product_line}%")
        query += " ORDER BY id ASC"

        cursor.execute(query, params)
        rows = cursor.fetchall()

        result = []
        for r in rows:
            result.append({
                'id'              : r.id,
                'company_code'    : r.company_code    or '',
                'process'         : r.process         or '',
                'product_line'    : r.product_line    or '',
                'setup_date'      : str(r.setup_date)[:10]         if r.setup_date         else '',
                'product_startdate': str(r.product_startdate)[:10] if r.product_startdate  else '',
                'remark'          : r.remark          or '',
                'created_by'      : r.created_by      or '',
                'creation_date'   : str(r.creation_date)[:10]      if r.creation_date      else '',
                'updated_by'      : r.updated_by      or '',
                'update_date'     : str(r.update_date)[:10]        if r.update_date        else ''
            })
        return jsonify(result)

    except Exception as e:
        from flask import current_app
        current_app.logger.error(f"process_line_list error: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass


@base.route('/process_line/detail/<int:row_id>')
@login_required
def process_line_detail(row_id):
    try:
        conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, company_code, process, product_line,
                      setup_date, product_startdate, remark
               FROM dbo.code_product_line WHERE id = ?""", (row_id,)
        )
        r = cursor.fetchone()
        if not r:
            return jsonify({'error': 'Not found'}), 404
        return jsonify({
            'id'              : r.id,
            'company_code'    : r.company_code    or '',
            'process'         : r.process         or '',
            'product_line'    : r.product_line    or '',
            'setup_date'      : str(r.setup_date)[:10]          if r.setup_date         else '',
            'product_startdate': str(r.product_startdate)[:10]  if r.product_startdate  else '',
            'remark'          : r.remark          or ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass


@base.route('/process_line/save', methods=['POST'])
@login_required
def process_line_save():
    data = request.get_json()
    try:
        conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute(
            """INSERT INTO dbo.code_product_line
               (company_code, process, product_line, setup_date, product_startdate, remark,
                created_by, creation_date)
               VALUES (?, ?, ?, ?, ?, ?, SYSTEM_USER, GETDATE())""",
            (
                data.get('company_code'),
                data.get('process'),
                data.get('product_line'),
                data.get('setup_date')         or None,
                data.get('product_startdate')  or None,
                data.get('remark', '')
            )
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try: cursor.close(); conn.close()
        except: pass


@base.route('/process_line/update', methods=['POST'])
@login_required
def process_line_update():
    data   = request.get_json()
    row_id = data.get('id')
    try:
        conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        cursor.execute(
            """UPDATE dbo.code_product_line
               SET company_code=?, process=?, product_line=?,
                   setup_date=?, product_startdate=?, remark=?,
                   updated_by=SYSTEM_USER, update_date=GETDATE()
               WHERE id=?""",
            (
                data.get('company_code'),
                data.get('process'),
                data.get('product_line'),
                data.get('setup_date')        or None,
                data.get('product_startdate') or None,
                data.get('remark', ''),
                row_id
            )
        )
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try: cursor.close(); conn.close()
        except: pass


@base.route('/process_line/delete', methods=['POST'])
@login_required
def process_line_delete():
    data = request.get_json()
    ids  = data.get('ids', [])
    if not ids:
        return jsonify({'success': False, 'error': 'No ids provided'})
    try:
        conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BRO_EXPENSE;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(ids))
        cursor.execute(f"DELETE FROM dbo.code_product_line WHERE id IN ({placeholders})", ids)
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try: cursor.close(); conn.close()
        except: pass
