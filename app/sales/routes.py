from flask import Blueprint, render_template, request, jsonify, redirect, url_for, flash, send_file, session, current_app
from app.auth.routes import login_required
from flask_login import current_user
import pyodbc
from datetime import datetime
import pandas as pd
import io
import openpyxl
from openpyxl.styles import Alignment, Font, Border, Side, PatternFill
from openpyxl.drawing.image import Image as XLImage
import os
import numpy as np
import re

# sales = Blueprint('sales', __name__, url_prefix='/sales')
from app.sales import bp as sales

# 매출관리
@sales.route('/sales_list')
@login_required
def sales_list():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    # Get sales list
    cursor.execute("""
        SELECT
            s.sales_no,
            s.sales_date,
            s.customer_code,
            c.vd_name AS customer_name,
            s.warehouse_code,
            s.currency_code,
            s.exchange_rate,
            s.payment_method,
            s.payment_due_date,
            s.status,
            s.sales_status,
            COALESCE(SUM(d.quantity), 0) AS total_quantity,
            COALESCE(SUM(d.amount), 0) AS total_amount,
            COALESCE(SUM(d.amount), 0) * 0.07 AS total_vat,
            COALESCE(SUM(d.amount), 0) * 1.07 AS total_sum_amount
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        LEFT JOIN code_vendor c ON s.customer_code = c.vd_code
        GROUP BY
            s.sales_no, s.sales_date, s.customer_code, c.vd_name,
            s.warehouse_code, s.currency_code, s.exchange_rate,
            s.payment_method, s.payment_due_date, s.status, s.sales_status
        ORDER BY s.sales_date DESC
    """)
    columns = [column[0] for column in cursor.description]
    sales_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    return render_template('sales/list.html', sales_list=sales_list)

# 매출관리
@sales.route('/sales_list2')
@login_required
def sales_list2():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    # Get sales list
    cursor.execute("""
        SELECT
            s.sales_no,
            s.sales_date,
            s.customer_code,
            c.vd_name AS customer_name,
            s.warehouse_code,
            s.currency_code,
            s.exchange_rate,
            s.payment_method,
            s.payment_due_date,
            s.status,
            s.sales_status,
            COALESCE(SUM(d.quantity), 0) AS total_quantity,
            COALESCE(SUM(d.amount), 0) AS total_amount,
            COALESCE(SUM(d.amount), 0) * 0.07 AS total_vat,
            COALESCE(SUM(d.amount), 0) * 1.07 AS total_sum_amount
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        LEFT JOIN code_vendor c ON s.customer_code = c.vd_code
        GROUP BY
            s.sales_no, s.sales_date, s.customer_code, c.vd_name,
            s.warehouse_code, s.currency_code, s.exchange_rate,
            s.payment_method, s.payment_due_date, s.status, s.sales_status
        ORDER BY s.sales_date DESC
    """)
    columns = [column[0] for column in cursor.description]
    sales_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    return render_template('sales/list2.html', sales_list=sales_list)

# 출고(매출INVOICE)관리
@sales.route('/sales_detail/<sales_no>')
@login_required
def sales_detail(sales_no):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    # Get sales details
    cursor.execute("""
        SELECT sd.item_code, i.itemname, i.spec, i.unit,
               sd.quantity, sd.unit_price, sd.amount
        FROM sales_detail sd
        JOIN itemmaster i ON sd.item_code = i.itemcode
        WHERE sd.sales_no = ?
    """, (sales_no,))
    details = cursor.fetchall()
    
    return render_template('sales/detail.html', sales_no=sales_no, details=details)

# 수금관리
@sales.route('/sales_payment', methods=['GET', 'POST'])
@login_required
def sales_payment():
    if request.method == 'POST':
        sales_no = request.form['sales_no']
        payment_date = request.form['payment_date']
        payment_amount = request.form['payment_amount']
        payment_method = request.form['payment_method']
        
        conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
        cursor = conn.cursor()
        
        # Record payment
        cursor.execute("""
            INSERT INTO sales_payment (sales_no, payment_date, amount, payment_method)
            VALUES (?, ?, ?, ?)
        """, (sales_no, payment_date, payment_amount, payment_method))
        
        # Update sales payment status
        cursor.execute("""
            UPDATE sales_master
            SET status = CASE
            WHEN (total_amount + total_vat) <= (SELECT SUM(transfer_amount) FROM sales_payment WHERE sales_no = ?)
                THEN 'COMPLETED'
                ELSE 'PARTIAL'
            END
            WHERE sales_no = ?
        """, (sales_no, sales_no))
        
        conn.commit()
        flash('Payment recorded successfully')
        return redirect(url_for('sales.sales_payment'))
    
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    # Get unpaid sales
    cursor.execute("""
        SELECT s.sales_no, s.sales_date, s.customer_code, c.vd_name AS customer_name,
               s.po_no,
               s.total_amount, s.status, s.payment_due_date,
               s.total_amount - COALESCE(SUM(sp.amount), 0) as remaining_amount
        FROM sales_master s
        JOIN code_vendor c ON s.customer_code = c.vd_code
        LEFT JOIN sales_payment sp ON s.sales_no = sp.sales_no
        WHERE s.status != 'COMPLETED'
        GROUP BY s.sales_no, s.sales_date, s.customer_code, c.vd_name,
                 s.po_no,
                 s.total_amount, s.status, s.payment_due_date
    """)
    columns = [column[0] for column in cursor.description]
    sales_list = [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    return render_template('sales/sales_payment/list.html', sales_list=sales_list)

# 수금현황집계
@sales.route('/sales_payment_summary')
@login_required
def sales_payment_summary():
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    customer_code = request.args.get('customer_code')
    
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    query = """
        SELECT s.sales_no, s.sales_date, s.customer_code, c.vd_name AS customer_name,
               s.total_amount, s.status, s.payment_due_date, 
               COALESCE(SUM(sp.amount), 0) as paid_amount,
               s.total_amount - COALESCE(SUM(sp.amount), 0) as remaining_amount
        FROM sales_master s
        JOIN code_vendor c ON s.customer_code = c.vd_code
        LEFT JOIN sales_payment sp ON s.sales_no = sp.sales_no
        WHERE 1=1
    """
    params = []
    
    if start_date:
        query += " AND s.sales_date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND s.sales_date <= ?"
        params.append(end_date)
    if customer_code:
        query += " AND s.customer_code = ?"
        params.append(customer_code)
    
    query += """
        GROUP BY s.sales_no, s.sales_date, s.customer_code, c.vd_name,
                 s.total_amount, s.status, s.payment_due_date
        ORDER BY s.sales_date DESC
    """
    
    cursor.execute(query, params)
    summary = cursor.fetchall()
    
    return render_template('sales/sales_payment/summary.html', summary=summary)

@sales.route('/sales_payment_summary_nopay')
@login_required
def sales_payment_summary_nopay():
    return render_template('sales/sales_payment/summary_nopay.html')

@sales.route('/api/sales/search')
@login_required
def api_sales_search():
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    customer_code = request.args.get('customerCode')
    warehouse_code = request.args.get('warehouseCode')
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 20))

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    query = '''
        SELECT
            s.sales_no,
            s.sales_date,
            s.customer_code,
            v.vd_name AS customer_name,
            s.po_no,
            s.currency_code,
            s.exchange_rate,
            s.payment_method,
            s.payment_due_date,
            s.status,
            s.sales_status,
            COALESCE(SUM(d.quantity), 0) AS total_quantity,
            COALESCE(SUM(d.amount), 0) AS total_amount,
            COALESCE(SUM(d.amount), 0) * 0.07 AS total_vat,
            COALESCE(SUM(d.amount), 0) * 1.07 AS total_sum_amount
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        WHERE 1=1
    '''
    params = []
    if start_date:
        query += ' AND s.sales_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND s.sales_date <= ?'
        params.append(end_date)
    if customer_code:
        query += ' AND s.customer_code = ?'
        params.append(customer_code)
    if warehouse_code:
        query += ' AND s.warehouse_code = ?'
        params.append(warehouse_code)
    po_no = request.args.get('poNo')
    remarks = request.args.get('remarks')
    if po_no:
        query += ' AND s.po_no LIKE ?'
        params.append(f"%{po_no}%")
    if remarks:
        query += ' AND s.remarks LIKE ?'
        params.append(f"%{remarks}%")
    query += '''
        GROUP BY
            s.sales_no, s.sales_date, s.customer_code, v.vd_name,
            s.po_no, s.currency_code, s.exchange_rate,
            s.payment_method, s.payment_due_date, s.status, s.sales_status
        ORDER BY s.sales_date DESC, s.sales_no DESC
    '''

    # 페이징
    offset = (page - 1) * per_page
    query += ' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY'
    params.extend([offset, per_page])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    # 전체 카운트
    count_query = 'SELECT COUNT(*) FROM sales_master s WHERE 1=1'
    count_params = []
    if start_date:
        count_query += ' AND s.sales_date >= ?'
        count_params.append(start_date)
    if end_date:
        count_query += ' AND s.sales_date <= ?'
        count_params.append(end_date)
    if customer_code:
        count_query += ' AND s.customer_code = ?'
        count_params.append(customer_code)
    if warehouse_code:
        count_query += ' AND s.warehouse_code = ?'
        count_params.append(warehouseCode)
    if po_no:
        count_query += ' AND s.po_no LIKE ?'
        count_params.append(f"%{po_no}%")
    if remarks:
        count_query += ' AND s.remarks LIKE ?'
        count_params.append(f"%{remarks}%")
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page

    items = []
    for row in rows:
        items.append({
            'salesNo': row.sales_no,
            'salesDate': row.sales_date.strftime('%Y-%m-%d') if row.sales_date else '',
            'customerName': row.customer_name or '',
            'poNo': row.po_no or '',
            'currency': row.currency_code or '',
            'exchangeRate': float(row.exchange_rate) if row.exchange_rate else 0,
            'totalQuantity': float(row.total_quantity) if hasattr(row, 'total_quantity') else 0,
            'unitPrice': '',
            'totalAmount': float(row.total_amount) if hasattr(row, 'total_amount') else 0,
            'totalVat': float(row.total_vat) if hasattr(row, 'total_vat') else 0,
            'totalSumAmount': float(row.total_sum_amount) if hasattr(row, 'total_sum_amount') else 0,
            'paymentMethod': row.payment_method or '',
            'paymentDueDate': row.payment_due_date.strftime('%Y-%m-%d') if row.payment_due_date else '',
            'status': row.status or '',
            'salesStatus': row.sales_status or ''
        })

    return jsonify({
        'items': items,
        'pagination': {
            'current_page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': total_pages,
            'start_page': max(1, page - 2),
            'end_page': min(total_pages, page + 2)
        }
    })

@sales.route('/new')
@login_required
def sales_new():
    return render_template('sales/sales_new.html')

@sales.route('/new2')
@login_required
def sales_new2():
    return render_template('sales/sales_new2.html')

@sales.route('/api/vendor/options')
@sales.route('/api/customer/options')   # 추가: 프론트엔드의 /sales/api/customer/options 호출을 허용
@login_required
def sales_vendor_options():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute('SELECT vd_code, vd_name FROM code_vendor ORDER BY vd_name')
    rows = cursor.fetchall()
    return jsonify([{'code': r.vd_code, 'name': r.vd_name} for r in rows])

@sales.route('/api/warehouse/options')
@login_required
def warehouse_options():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute('SELECT WH_CODE, WH_NAME FROM code_warehouse ORDER BY WH_NAME')
    rows = cursor.fetchall()
    return jsonify([{'code': r.WH_CODE, 'name': r.WH_NAME} for r in rows])

@sales.route('/api/currencies')
@login_required
def currency_options():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute('SELECT currency_code, currency_name FROM code_currency ORDER BY currency_code')
    rows = cursor.fetchall()
    return jsonify([{'code': r.currency_code, 'name': r.currency_name} for r in rows])

@sales.route('/api/sales/item/options')
@login_required
def sales_item_options():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute('SELECT ItemCode, ItemName FROM ItemMaster ORDER BY ItemCode')
    rows = cursor.fetchall()
    return jsonify([{'item_code': r.ItemCode, 'item_name': r.ItemName} for r in rows])

@sales.route('/api/sales/item/detail/<item_code>')
@login_required
def sales_item_detail(item_code):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute('SELECT ItemCode, ItemName, Spec, unit, salesprice FROM ItemMaster WHERE ItemCode = ?', (item_code,))
    row = cursor.fetchone()
    if row:
        return jsonify({
            'item_code': row.ItemCode,
            'item_name': row.ItemName,
            'item_spec': row.Spec,
            'item_unit': row.unit,
            'unit_price': float(row.salesprice) if row.salesprice else 0
        })
    else:
        return jsonify({}), 404

@sales.route('/api/sales/generate-no')
@login_required
def generate_sales_no():
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    today = datetime.now().strftime('%Y%m%d')
    
    # 오늘 날짜의 기존 매출번호 중 가장 큰 번호 찾기
    cursor.execute('SELECT sales_no FROM sales_master WHERE sales_no LIKE ? ORDER BY sales_no DESC', (f'SO{today}%',))
    existing_sales = cursor.fetchall()
    
    if existing_sales:
        # 가장 큰 번호에서 순번 추출
        last_sales_no = existing_sales[0][0]
        last_sequence = int(last_sales_no[-4:])  # 마지막 4자리
        next_sequence = last_sequence + 1
    else:
        next_sequence = 1
    
    sales_no = f'SO{today}{next_sequence:04d}'
    
    # 생성된 번호가 이미 존재하는지 한 번 더 확인
    cursor.execute('SELECT COUNT(*) FROM sales_master WHERE sales_no = ?', (sales_no,))
    if cursor.fetchone()[0] > 0:
        # 중복이면 다음 번호로
        next_sequence += 1
        sales_no = f'SO{today}{next_sequence:04d}'
    
    return jsonify({'salesNo': sales_no})

@sales.route('/api/transaction-codes')
@login_required
def get_transaction_codes():
    types = request.args.get('types', '')
    type_list = [t.strip() for t in types.split(',') if t.strip()]
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    if type_list:
        placeholders = ','.join(['?'] * len(type_list))
        cursor.execute(f"SELECT tr_code, tr_name FROM code_transaction WHERE TR_DIV = 'OUT' AND tr_code IN ({placeholders}) ORDER BY tr_code", type_list)
    else:
        cursor.execute("SELECT tr_code, tr_name FROM code_transaction WHERE TR_DIV = 'OUT' ORDER BY tr_code")
    rows = cursor.fetchall()
    return jsonify([{'tr_code': r.tr_code, 'tr_name': r.tr_name} for r in rows])

@sales.route('/api/sales/register', methods=['POST'])
@login_required
def register_sales():
    data = request.get_json()
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    try:
        # 매출번호 중복 체크
        cursor.execute('SELECT COUNT(*) FROM sales_master WHERE sales_no = ?', (data['salesNo'],))
        if cursor.fetchone()[0] > 0:
            return jsonify({'success': False, 'message': f'매출번호 {data["salesNo"]}가 이미 존재합니다. 새로운 매출번호를 생성해주세요.'})

        # sales_master 저장
        now = datetime.now()
        cursor.execute('''
            INSERT INTO sales_master (sales_no, sales_date, customer_code, currency_code, exchange_rate, payment_method, payment_due_date, status, created_at, updated_at, remarks, total_amount, total_vat, total_sum_amount, po_no, sales_status, tr_code)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            data['salesNo'], data['salesDate'], data['customerCode'],
            data['currencyCode'], data['exchangeRate'], data['paymentMethod'], data['paymentDueDate'],
            'UNPAID', now, now, data.get('remarks', ''), data['total_amount'], data['total_vat'], data['total_sum_amount'], data.get('poNo', ''), data.get('salesStatus', 'PROCESS'), data.get('trCode', None)
        ))

        # 재고 처리 여부 플래그 확인 (True이면 재고/수불 처리 건너뜀)
        skip_inventory = data.get('skipInventory', False)

        # sales_detail 저장
        for item in data['items']:
            cursor.execute('''
                INSERT INTO sales_detail (sales_no, item_code, quantity, unit_price, amount, warehouse_code, createuser)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                data['salesNo'], item['itemCode'], round(float(item['quantity'] or 0), 2), round(float(item['unitPrice'] or 0), 2), round(float(item['amount'] or 0), 2), item.get('warehouseCode', ''), current_user.username
            ))

            # === 수불/재고 로직 (skipInventory=True 이면 건너뜀) ===
            if not skip_inventory:
                # 1. 재고 차감
                cursor.execute('''
                    SELECT InventoryId, CurrentStock FROM Inventory WHERE WarehouseCode = ? AND ItemCode = ?
                ''', (item.get('warehouseCode', ''), item['itemCode']))
                inv = cursor.fetchone()
                out_qty = round(float(item['quantity'] or 0), 2)
                if inv:
                    new_stock = float(inv.CurrentStock) - out_qty
                    cursor.execute('''
                        UPDATE Inventory SET CurrentStock = ? WHERE InventoryId = ?
                    ''', (new_stock, inv.InventoryId))
                else:
                    new_stock = 0 - out_qty
                    print("INSERT Inventory:", item.get('warehouseCode', ''), item['itemCode'], new_stock)
                    try:
                        cursor.execute('''
                            INSERT INTO Inventory (WarehouseCode, ItemCode, CurrentStock, SafetyStock, MaxStock, remarks)
                            VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            item.get('warehouseCode', ''),
                            item['itemCode'],
                            new_stock,
                            None,
                            None,
                            f"매출출고로 생성 - {data['salesNo']}"
                        ))
                    except Exception as e:
                        print("Inventory INSERT ERROR:", e)
                # 2. 수불이력 기록
                cursor.execute('''
                    INSERT INTO Inventory_Transaction (
                        TransDate, WarehouseCode, ItemCode, LotNo, TransType, RefNo,
                        InQty, OutQty, BalanceQty, Remarks, CreateUser, CreateDate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['salesDate'],
                    item.get('warehouseCode', ''),
                    item['itemCode'],
                    None,
                    'OUT',
                    data['salesNo'],
                    0.0,
                    out_qty,
                    new_stock,
                    f"매출출고 - {data['salesNo']}",
                    current_user.username,
                    now
                ))

        conn.commit()
        return jsonify({'success': True, 'message': '매출(출고) 등록이 완료되었습니다.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})

@sales.route('/api/sales/excel')
@login_required
def sales_excel_download():
    start_date = request.args.get('startDate')
    end_date = request.args.get('endDate')
    customer_code = request.args.get('customerCode')
    po_no = request.args.get('poNo')
    remarks = request.args.get('remarks')

    lang = session.get('language', 'ko')
    if lang == 'th':
        excel_title = 'รายการขาย'
        filename = f'รายการขาย_{datetime.now().strftime("%Y%m%d")}.xlsx'
    else:
        excel_title = '매출 목록'
        filename = f'매출_목록_{datetime.now().strftime("%Y%m%d")}.xlsx'

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    query = '''
        SELECT
            s.sales_no,
            s.po_no,
            s.sales_date,
            v.vd_name AS customer_name,
            w.WH_NAME AS warehouse_name,
            s.currency_code,
            s.exchange_rate,
            COALESCE(SUM(d.quantity), 0) AS total_quantity,
            ROUND(COALESCE(SUM(d.amount), 0), 2) AS total_amount,
            ROUND(COALESCE(SUM(d.amount), 0) * 0.07, 2) AS total_vat,
            ROUND(COALESCE(SUM(d.amount), 0) * 1.07, 2) AS total_sum_amount,
            s.payment_method,
            s.payment_due_date,
            s.status,
            s.remarks
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        WHERE 1=1
    '''
    params = []
    if start_date:
        query += ' AND s.sales_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND s.sales_date <= ?'
        params.append(end_date)
    if customer_code:
        query += ' AND s.customer_code = ?'
        params.append(customer_code)
    if po_no:
        query += ' AND s.po_no LIKE ?'
        params.append(f'%{po_no}%')
    if remarks:
        query += ' AND s.remarks LIKE ?'
        params.append(f'%{remarks}%')
    query += '''
        GROUP BY
            s.sales_no, s.sales_date, v.vd_name, w.WH_NAME,
            s.currency_code, s.exchange_rate, s.payment_method, s.payment_due_date, s.status, s.po_no, s.remarks
        ORDER BY s.sales_date DESC, s.sales_no DESC
    '''
    cursor.execute(query, params)
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame([dict(zip(columns, row)) for row in rows])

    # 다국어 컬럼명 매핑
    if lang == 'th':
        columns_map = [
            ('sales_no', 'เลขที่ขาย'),
             ('po_no', 'PO.Number'),  

            ('sales_date', 'วันที่ขาย'),
            ('customer_name', 'ชื่อลูกค้า'),
            ('warehouse_name', 'คลังสินค้า'),
            ('currency_code', 'สกุลเงิน'),
            ('exchange_rate', 'อัตราแลกเปลี่ยน'),
            ('total_quantity', 'จำนวน'),
            ('total_amount', 'มูลค่ารวม'),
            ('total_vat', 'ภาษีมูลค่าเพิ่ม'),
            ('total_sum_amount', 'ยอดรวมสุทธิ'),
            ('payment_method', 'วิธีชำระเงิน'),
            ('payment_due_date', 'วันครบกำหนดชำระ'),
            ('status', 'สถานะ'),
                     ('remarks', 'หมายเหตุ')
        ]
    else:
        # 안전하게 get_text 함수 가져오기
        try:
            get_text = current_app.jinja_env.globals.get('get_text')
            if get_text is None:
                # get_text가 없으면 기본 한글 컬럼명 사용
                columns_map = [
                    ('sales_no', '매출번호'),
                    ('po_no', 'PO.Number'),
                    ('sales_date', '매출일자'),
                    ('customer_name', '고객명'),
                    ('warehouse_name', '창고'),
                    ('currency_code', '통화'),
                    ('exchange_rate', '환율'),
                    ('total_quantity', '수량'),
                    ('total_amount', '공급가액'),
                    ('total_vat', '부가세'),
                    ('total_sum_amount', '합계금액'),
                    ('payment_method', '결제방법'),
                    ('payment_due_date', '결제예정일'),
                    ('status', '상태'),
                    ('po_no', 'PO.Number'),
                    ('remarks', '비고')
                ]
            else:
                columns_map = [
                    ('sales_no', get_text('sales_no')),
                      ('po_no', 'PO.Number'),
                    ('sales_date', get_text('sales_date')),
                    ('customer_name', get_text('customer')),
                    ('warehouse_name', get_text('warehouse')),
                    ('currency_code', get_text('currency')),
                    ('exchange_rate', get_text('exchange_rate')),
                    ('total_quantity', get_text('total_quantity')),
                    ('total_amount', get_text('total_amount')),
                    ('total_vat', get_text('vat')),
                    ('total_sum_amount', get_text('total_sum_amount')),
                    ('payment_method', get_text('payment_method')),
                    ('payment_due_date', get_text('payment_due_date')),
                    ('status', get_text('status')),
                    ('po_no', 'PO.Number'),
                    ('remarks', get_text('remark'))
                ]
        except:
            # 예외 발생 시 기본 한글 컬럼명 사용
            columns_map = [
                ('sales_no', '매출번호'),
                     ('po_no', 'PO.Number'),
                ('sales_date', '매출일자'),
                ('customer_name', '고객명'),
                ('warehouse_name', '창고'),
                ('currency_code', '통화'),
                ('exchange_rate', '환율'),
                ('total_quantity', '수량'),
                ('total_amount', '공급가액'),
                ('total_vat', '부가세'),
                ('total_sum_amount', '합계금액'),
                ('payment_method', '결제방법'),
                ('payment_due_date', '결제예정일'),
                ('status', '상태'),
                ('po_no', 'PO.Number'),
                ('remarks', '비고')
            ]
    
    # DataFrame 컬럼명 변경
    column_mapping = dict(columns_map)
    df = df.rename(columns=column_mapping)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=excel_title)
        worksheet = writer.sheets[excel_title]
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            worksheet.set_column(idx, idx, max_length + 2)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@sales.route('/edit/<sales_no>')
@login_required
def sales_edit(sales_no):
    return render_template('sales/edit.html', sales_no=sales_no)

@sales.route('/api/sales/detail/<sales_no>')
@login_required
def api_sales_detail(sales_no):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    
    # Get master data
    cursor.execute("""
        SELECT 
            s.sales_no as salesNo,
            s.sales_date as salesDate,
            s.customer_code as customerCode,
            s.currency_code as currencyCode,
            s.exchange_rate as exchangeRate,
            s.payment_method as paymentMethod,
            s.payment_due_date as paymentDueDate,
            s.sales_status as salesStatus,
            s.remarks,
            s.po_no as poNo,
            s.tr_code as trCode
        FROM sales_master s
        WHERE s.sales_no = ?
    """, (sales_no,))
    master = cursor.fetchone()
    master_columns = [column[0] for column in cursor.description]
    if not master:
        return jsonify({'error': 'Sales not found'}), 404
    # Get detail data
    cursor.execute("""
        SELECT 
            d.item_code as itemCode,
            i.ItemName as itemName,
            i.Spec as itemSpec,
            d.quantity,
            d.unit_price as unitPrice,
            d.amount,
            d.warehouse_code as warehouseCode
        FROM sales_detail d
        JOIN ItemMaster i ON d.item_code = i.ItemCode
        WHERE d.sales_no = ?
    """, (sales_no,))
    details = cursor.fetchall()
    def safe_float2(val):
        try:
            return round(float(val), 2)
        except (TypeError, ValueError):
            return 0.0
    return jsonify({
        'master': dict(zip(master_columns, master)),
        'details': [
            {
                'itemCode': d[0],
                'itemName': d[1],
                'itemSpec': d[2],
                'quantity': safe_float2(d[3]),
                'unitPrice': safe_float2(d[4]),
                'amount': safe_float2(d[5]),
                'warehouseCode': d[6]
            } for d in details
        ]
    })

@sales.route('/api/sales/payment/exist/<sales_no>')
@login_required
def sales_payment_exist(sales_no):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    cursor.execute('SELECT COUNT(*) FROM sales_payment WHERE sales_no = ?', (sales_no,))
    count = cursor.fetchone()[0]
    return jsonify({'exists': count > 0})

@sales.route('/api/sales/update', methods=['POST'])
@login_required
def update_sales():
    data = request.get_json()
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    try:
        # 1. sales_master 수정 (tr_code 포함)
        now = datetime.now()
        cursor.execute('''
            UPDATE sales_master
            SET sales_date=?, customer_code=?, currency_code=?, exchange_rate=?, payment_method=?, payment_due_date=?, sales_status=?, remarks=?, total_amount=?, total_vat=?, total_sum_amount=?, updated_at=?, po_no=?, tr_code=?
            WHERE sales_no=?
        ''', (
            data['master']['salesDate'], data['master']['customerCode'],
            data['master']['currencyCode'], data['master']['exchangeRate'], data['master']['paymentMethod'],
            data['master']['paymentDueDate'], data['master'].get('salesStatus', 'PROCESS'),
            data['master'].get('remarks', ''),
            data['master']['total_amount'], data['master']['total_vat'], data['master']['total_sum_amount'],
            now, data['master'].get('poNo', ''), data['master'].get('trCode', None), data['master']['salesNo']
        ))

        # 2. 기존 sales_detail, 수불이력, 재고 정보 조회
        sales_no = data['master']['salesNo']
        cursor.execute('SELECT item_code, warehouse_code, quantity FROM sales_detail WHERE sales_no=?', (sales_no,))
        old_details = cursor.fetchall()
        old_dict = {}
        for row in old_details:
            key = f"{row.item_code.strip()}_{row.warehouse_code.strip()}"
            old_dict[key] = float(row.quantity)
        new_dict = {}
        for item in data['details']:
            key = f"{item['itemCode'].strip()}_{item['warehouseCode'].strip()}"
            new_dict[key] = float(item['quantity'])

        # 3. 변경사항 분석 및 재고/수불 동기화
        # 3-1. 삭제된 품목(기존에만 있는 key)
        for key in old_dict:
            if key not in new_dict:
                item_code, warehouse_code = key.split('_', 1)
                qty = old_dict[key]
                # 수불이력 삭제
                cursor.execute('DELETE FROM Inventory_Transaction WHERE RefNo=? AND ItemCode=? AND WarehouseCode=? AND TransType=?', (sales_no, item_code, warehouse_code, 'OUT'))
                # 재고 복원(OUT → +수량)
                cursor.execute('SELECT InventoryId, CurrentStock FROM Inventory WHERE WarehouseCode=? AND ItemCode=?', (warehouse_code, item_code))
                inv = cursor.fetchone()
                if inv:
                    new_stock = float(inv.CurrentStock) + qty
                    cursor.execute('UPDATE Inventory SET CurrentStock=? WHERE InventoryId=?', (new_stock, inv.InventoryId))
                else:
                    new_stock = 0 - qty
                    cursor.execute('INSERT INTO Inventory (WarehouseCode, ItemCode, CurrentStock, SafetyStock, MaxStock, remarks) VALUES (?, ?, ?, ?, ?, ?)', (warehouse_code, item_code, new_stock, None, None, f"매출수정 생성 - {sales_no}"))
        # 3-2. 변경/추가된 품목
        for item in data['details']:
            item_code = item['itemCode'].strip()
            warehouse_code = item['warehouseCode'].strip()
            qty = float(item['quantity'])
            key = f"{item_code}_{warehouse_code}"
            # 기존에 있던 품목이면 수량 변경 여부 확인
            if key in old_dict:
                old_qty = old_dict[key]
                if abs(qty - old_qty) > 0.001:
                    # 기존 수불이력 삭제
                    cursor.execute('DELETE FROM Inventory_Transaction WHERE RefNo=? AND ItemCode=? AND WarehouseCode=? AND TransType=?', (sales_no, item_code, warehouse_code, 'OUT'))
                    # 재고 복원(OUT → +기존수량)
                    cursor.execute('SELECT InventoryId, CurrentStock FROM Inventory WHERE WarehouseCode=? AND ItemCode=?', (warehouse_code, item_code))
                    inv = cursor.fetchone()
                    if inv:
                        stock_restore = float(inv.CurrentStock) + old_qty
                        cursor.execute('UPDATE Inventory SET CurrentStock=? WHERE InventoryId=?', (stock_restore, inv.InventoryId))
                    # 재고 차감(OUT → -신규수량)
                    cursor.execute('SELECT InventoryId, CurrentStock FROM Inventory WHERE WarehouseCode=? AND ItemCode=?', (warehouse_code, item_code))
                    inv = cursor.fetchone()
                    if inv:
                        new_stock = float(inv.CurrentStock) - qty
                        cursor.execute('UPDATE Inventory SET CurrentStock=? WHERE InventoryId=?', (new_stock, inv.InventoryId))
                    else:
                        new_stock = 0 - qty
                        cursor.execute('INSERT INTO Inventory (WarehouseCode, ItemCode, CurrentStock, SafetyStock, MaxStock, remarks) VALUES (?, ?, ?, ?, ?, ?)', (warehouse_code, item_code, new_stock, None, None, f"매출수정 생성 - {sales_no}"))
                    # 수불이력 재생성
                    cursor.execute('''
                        INSERT INTO Inventory_Transaction (TransDate, WarehouseCode, ItemCode, LotNo, TransType, RefNo, InQty, OutQty, BalanceQty, Remarks, CreateUser, CreateDate)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        data['master']['salesDate'], warehouse_code, item_code, None, 'OUT', sales_no, 0.0, qty, new_stock, f"매출수정 - {sales_no}", current_user.username, now
                    ))
            else:
                # 신규 품목
                # 재고 차감(OUT → -신규수량)
                cursor.execute('SELECT InventoryId, CurrentStock FROM Inventory WHERE WarehouseCode=? AND ItemCode=?', (warehouse_code, item_code))
                inv = cursor.fetchone()
                if inv:
                    new_stock = float(inv.CurrentStock) - qty
                    cursor.execute('UPDATE Inventory SET CurrentStock=? WHERE InventoryId=?', (new_stock, inv.InventoryId))
                else:
                    new_stock = 0 - qty
                    cursor.execute('INSERT INTO Inventory (WarehouseCode, ItemCode, CurrentStock, SafetyStock, MaxStock, remarks) VALUES (?, ?, ?, ?, ?, ?)', (warehouse_code, item_code, new_stock, None, None, f"매출수정 생성 - {sales_no}"))
                # 수불이력 생성
                cursor.execute('''
                    INSERT INTO Inventory_Transaction (TransDate, WarehouseCode, ItemCode, LotNo, TransType, RefNo, InQty, OutQty, BalanceQty, Remarks, CreateUser, CreateDate)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    data['master']['salesDate'], warehouse_code, item_code, None, 'OUT', sales_no, 0.0, qty, new_stock, f"매출수정 - {sales_no}", current_user.username, now
                ))

        # 4. sales_detail 삭제 후 재삽입
        cursor.execute('DELETE FROM sales_detail WHERE sales_no=?', (sales_no,))
        for item in data['details']:
            cursor.execute('''
                INSERT INTO sales_detail (sales_no, item_code, quantity, unit_price, amount, warehouse_code, createuser)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (
                sales_no, item['itemCode'], round(float(item['quantity'] or 0), 2), round(float(item['unitPrice'] or 0), 2), round(float(item['amount'] or 0), 2), item.get('warehouseCode', ''), current_user.username
            ))
        conn.commit()
        return jsonify({'success': True, 'message': '매출(출고) 수정이 완료되었습니다.'})
    except Exception as e:
        conn.rollback()
        return jsonify({'success': False, 'message': str(e)})

@sales.route('/invoice')
@login_required
def sales_invoice():
    sales_no = request.args.get('sales_no')
    return render_template('sales/invoice.html', sales_no=sales_no)

@sales.route('/api/sales/invoice/<sales_no>')
@login_required
def api_sales_invoice(sales_no):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    # 매출 마스터 + 거래처 정보 (컬럼명 실제 DB에 맞게 수정)
    cursor.execute("""
        SELECT s.sales_no, s.sales_date, s.customer_code, v.vd_name, v.vd_president, v.vd_biz_number, v.vd_address, v.vd_phone,
               s.warehouse_code, s.currency_code, s.exchange_rate, s.payment_method, s.payment_due_date, s.remarks,
               s.total_amount, s.total_vat, s.total_sum_amount
        FROM sales_master s
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        WHERE s.sales_no = ?
    """, (sales_no,))
    master = cursor.fetchone()
    if not master:
        return jsonify({'error': 'Sales not found'}), 404
    master_columns = [column[0] for column in cursor.description]
    master_dict = dict(zip(master_columns, master))
    master_dict['vd_email'] = ''
    cursor.execute("""
        SELECT d.item_code, i.ItemName, i.Spec, i.unit, d.quantity, d.unit_price, d.amount
        FROM sales_detail d
        JOIN ItemMaster i ON d.item_code = i.ItemCode
        WHERE d.sales_no = ?
    """, (sales_no,))
    details = [
        {
            'item_code': r[0],
            'item_name': r[1],
            'item_spec': r[2],
            'item_unit': r[3],
            'quantity': float(r[4]) if r[4] else 0,
            'unit_price': float(r[5]) if r[5] else 0,
            'amount': float(r[6]) if r[6] else 0
        }
        for r in cursor.fetchall()
    ]
    return jsonify({'master': master_dict, 'details': details})

@sales.route('/sales_list_detail/<sales_no>')
@login_required
def sales_list_detail(sales_no):
    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()
    # 마스터+거래처 정보
    cursor.execute("""
        SELECT s.sales_no, s.sales_date, s.customer_code, v.vd_name, v.vd_president, v.vd_biz_number, v.vd_address, v.vd_phone,
               s.warehouse_code, s.currency_code, s.exchange_rate, s.payment_method, s.payment_due_date, s.remarks,
               s.total_amount, s.total_vat, s.total_sum_amount
        FROM sales_master s
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        WHERE s.sales_no = ?
    """, (sales_no,))
    master = cursor.fetchone()
    master_columns = [column[0] for column in cursor.description]
    master_dict = dict(zip(master_columns, master)) if master else {}
    # 품목 상세
    cursor.execute("""
        SELECT d.item_code, i.ItemName, i.Spec, i.unit, d.quantity, d.unit_price, d.amount
        FROM sales_detail d
        JOIN ItemMaster i ON d.item_code = i.ItemCode
        WHERE d.sales_no = ?
    """, (sales_no,))
    details = [
        {
            'item_code': r[0],
            'item_name': r[1],
            'item_spec': r[2],
            'item_unit': r[3],
            'quantity': float(r[4]) if r[4] else 0,
            'unit_price': float(r[5]) if r[5] else 0,
            'amount': float(r[6]) if r[6] else 0
        }
        for r in cursor.fetchall()
    ]
    return render_template('sales/sales_list_detail.html', master=master_dict, details=details)

@sales.route('/api/sales/list-detail', methods=['POST'])
@login_required
def api_sales_list_detail():

    data = request.get_json()
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    customer_code = data.get('customerCode')
    warehouse_code = data.get('warehouseCode')
    sales_no = data.get('salesNo')  # ← 이 줄 추가
    page = int(data.get('page', 1))
    per_page = int(data.get('itemsPerPage', 15))
    po_no = data.get('poNo')

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    query = '''
        SELECT
            s.sales_date,
            s.sales_no,
            v.vd_name AS customer_name,
            s.po_no,
            COALESCE(w.WH_NAME, dw.WH_NAME) AS warehouse_name,
            d.item_code,
            i.ItemName AS item_name,
            i.Spec AS specification,
            i.unit AS unit,
            d.quantity,
            d.unit_price,
            d.amount,
            s.currency_code,
            s.exchange_rate,
            s.payment_method,
            s.payment_due_date,
            s.status,
            s.sales_status
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        LEFT JOIN code_warehouse dw ON d.warehouse_code = dw.WH_CODE
        LEFT JOIN ItemMaster i ON d.item_code = i.ItemCode
        WHERE 1=1
    '''
    params = []
    if start_date:
        query += ' AND s.sales_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND s.sales_date <= ?'
        params.append(end_date)
    if customer_code:
        query += ' AND s.customer_code = ?'
        params.append(customer_code)
    if warehouse_code:
        query += ' AND s.warehouse_code = ?'
        params.append(warehouse_code)
    if sales_no:  # ← 이 블록 추가
        query += ' AND s.sales_no = ?'
        params.append(sales_no)
    if po_no:
       query += ' AND s.po_no LIKE ?'
       params.append(f"%{po_no}%")

    query += ' ORDER BY s.sales_date DESC, s.sales_no DESC, d.item_code'

    # Pagination
    offset = (page - 1) * per_page
    query += ' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY'
    params.extend([offset, per_page])

    cursor.execute(query, params)
    rows = cursor.fetchall()

    items = []
    for row in rows:
        # sales_detail에서 금액 정보 집계 (매출관리와 동일하게)
        conn2 = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
        cursor2 = conn2.cursor()
        cursor2.execute('''
            SELECT
                COALESCE(SUM(d.amount), 0) AS total_amount,
                COALESCE(SUM(d.amount), 0) * 0.07 AS total_vat,
                COALESCE(SUM(d.amount), 0) * 1.07 AS total_sum_amount
            FROM sales_detail d
            WHERE d.sales_no = ?
        ''', (row.sales_no,))
        m = cursor2.fetchone()
        total_amount = float(m[0]) if m else 0
        total_vat = float(m[1]) if m else 0
        total_sum = float(m[2]) if m else 0
        # sales_payment에서 수금금액(transfer_amount 합계)
        cursor2.execute('SELECT COALESCE(SUM(transfer_amount),0) FROM sales_payment WHERE sales_no = ?', (row.sales_no,))
        paid_amount = float(cursor2.fetchone()[0])
        unpaid_amount = total_sum - paid_amount
        items.append({
            'salesNo': row.sales_no,
            'salesDate': row.sales_date.strftime('%Y-%m-%d') if row.sales_date else '',
            'customerName': row.customer_name or '',
            'poNo': row.po_no or '',
            'warehouseName': row.warehouse_name or '',
            'itemCode': row.item_code or '',
            'itemName': row.item_name or '',
            'specification': row.specification or '',
            'unit': row.unit or '',
            'quantity': float(row.quantity) if row.quantity is not None else 0,
            'unitPrice': float(row.unit_price) if row.unit_price is not None else 0,
            'amount': float(row.amount) if row.amount is not None else 0,
            'currency': row.currency_code or '',
            'exchangeRate': float(row.exchange_rate) if row.exchange_rate else 0,
            'paymentMethod': row.payment_method or '',
            'paymentDueDate': row.payment_due_date.strftime('%Y-%m-%d') if row.payment_due_date else '',
            'status': row.status or '',
            'salesStatus': row.sales_status or ''
        })
        conn2.close()

    # Get total count for pagination
    count_query = '''
        SELECT COUNT(*)
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        WHERE 1=1
    '''
    count_params = []
    if start_date:
        count_query += ' AND s.sales_date >= ?'
        count_params.append(start_date)
    if end_date:
        count_query += ' AND s.sales_date <= ?'
        count_params.append(end_date)
    if customer_code:
        count_query += ' AND s.customer_code = ?'
        count_params.append(customer_code)
    if warehouse_code:
        count_query += ' AND s.warehouse_code = ?'
        count_params.append(warehouseCode)
    if po_no:
        count_query += ' AND s.po_no LIKE ?'
        count_params.append(f"%{po_no}%")
    if remarks:
        count_query += ' AND s.remarks LIKE ?'
        count_params.append(f"%{remarks}%")
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page

    return jsonify({
        'status': 'success',
        'items': items,
        'pagination': {
            'current_page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': total_pages
        }
    })

@sales.route('/sales_list_detail')
@login_required
def sales_list_detail_page():
    return render_template('sales/sales_list_detail.html')

@sales.route('/api/sales/list-detail/excel', methods=['POST'])
@login_required
def api_sales_list_detail_excel():
    data = request.get_json()
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    customer_code = data.get('customerCode')
    warehouse_code = data.get('warehouseCode')
    sales_no = data.get('salesNo')
    po_no = data.get('poNo')

    lang = session.get('language', 'ko')
    if lang == 'th':
        excel_title = 'รายละเอียดการขาย'
        filename = f'รายละเอียดการขาย_{datetime.now().strftime("%Y%m%d")}.xlsx'
    else:
        excel_title = '매출 상세 목록'
        filename = f'매출_상세_목록_{datetime.now().strftime("%Y%m%d")}.xlsx'

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    query = '''
        SELECT
            s.sales_date,
            s.sales_no,
            v.vd_name AS customer_name,
            s.po_no,
            COALESCE(w.WH_NAME, dw.WH_NAME) AS warehouse_name,
            d.item_code,
            i.ItemName AS item_name,
            i.Spec AS specification,
            i.unit AS unit,
            d.quantity,
            d.unit_price,
            d.amount,
            s.currency_code,
            s.exchange_rate,
            s.payment_method,
            s.payment_due_date,
            s.status,
            s.sales_status
        FROM sales_master s
        LEFT JOIN sales_detail d ON s.sales_no = d.sales_no
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        LEFT JOIN code_warehouse dw ON d.warehouse_code = dw.WH_CODE
        LEFT JOIN ItemMaster i ON d.item_code = i.ItemCode
        WHERE 1=1
    '''
    params = []
    if start_date:
        query += ' AND s.sales_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND s.sales_date <= ?'
        params.append(end_date)
    if customer_code:
        query += ' AND s.customer_code = ?'
        params.append(customer_code)
    if warehouse_code:
        query += ' AND s.warehouse_code = ?'
        params.append(warehouse_code)
    if sales_no:
        query += ' AND s.sales_no LIKE ?'
        params.append(f'%{sales_no}%')
    if po_no:
        query += ' AND s.po_no LIKE ?'
        params.append(f'%{poNo}%')
        
    query += ' ORDER BY s.sales_date DESC, s.sales_no DESC, d.item_code'

    cursor.execute(query, params)
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    df = pd.DataFrame([dict(zip(columns, row)) for row in rows])

    # 다국어 컬럼명 매핑
    if lang == 'th':
        columns_map = [
            ('sales_date', 'วันที่ขาย'),
            ('sales_no', 'เลขที่ขาย'),
            ('customer_name', 'ชื่อลูกค้า'),
            ('po_no', 'PO.Number'),
            ('warehouse_name', 'คลังสินค้า'),
            ('item_code', 'รหัสสินค้า'),
            ('item_name', 'ชื่อสินค้า'),
            ('specification', 'รายละเอียด'),
            ('unit', 'หน่วย'),
            ('quantity', 'จำนวน'),
            ('unit_price', 'ราคาต่อหน่วย'),
            ('amount', 'จำนวนเงิน'),
            ('currency_code', 'สกุลเงิน'),
            ('exchange_rate', 'อัตราแลกเปลี่ยน'),
            ('payment_method', 'วิธีชำระเงิน'),
            ('sales_status', 'สถานะการขาย'),
            ('payment_due_date', 'วันครบกำหนดชำระ')
        ]
    else:
        # 안전하게 get_text 함수 가져오기
        try:
            get_text = current_app.jinja_env.globals.get('get_text')
            if get_text is None:
                # get_text가 없으면 기본 한글 컬럼명 사용
                columns_map = [
                    ('sales_date', '매출일자'),
                    ('sales_no', '매출번호'),
                    ('customer_name', '고객명'),
                    ('po_no', 'PO.Number'),
                    ('warehouse_name', '창고'),
                    ('item_code', '품목코드'),
                    ('item_name', '품목명'),
                    ('specification', '규격'),
                    ('unit', '단위'),
                    ('quantity', '수량'),
                    ('unit_price', '단가'),
                    ('amount', '금액'),
                    ('currency_code', '통화'),
                    ('exchange_rate', '환율'),
                    ('payment_method', '결제방법'),
                    ('payment_due_date', '결제예정일')
                ]
            else:
                columns_map = [
                    ('sales_date', get_text('sales_date')),
                    ('sales_no', get_text('sales_no')),
                    ('customer_name', get_text('customer')),
                    ('po_no', 'PO.Number'),
                    ('warehouse_name', get_text('warehouse')),
                    ('item_code', get_text('item_code')),
                    ('item_name', get_text('item_name')),
                    ('specification', get_text('specification')),
                    ('unit', get_text('unit')),
                    ('quantity', get_text('quantity')),
                    ('unit_price', get_text('unit_price')),
                    ('amount', get_text('amount')),
                    ('currency_code', get_text('currency')),
                    ('exchange_rate', get_text('exchange_rate')),
                    ('payment_method', get_text('payment_method')),
                    ('payment_due_date', get_text('payment_due_date')),
                    ('sales_status', get_text('sales_status')),
                    ('po_no', 'PO.Number'),
                    ('remarks', get_text('remark'))
                ]
        except:
            # 예외 발생 시 기본 한글 컬럼명 사용
            columns_map = [
                ('sales_date', '매출일자'),
                ('sales_no', '매출번호'),
                ('customer_name', '고객명'),
                ('po_no', 'PO.Number'),
                ('warehouse_name', '창고'),
                ('item_code', '품목코드'),
                ('item_name', '품목명'),
                ('specification', '규격'),
                ('unit', '단위'),
                ('quantity', '수량'),
                ('unit_price', '단가'),
                ('amount', '금액'),
                ('currency_code', '통화'),
                ('exchange_rate', '환율'),
                ('payment_method', '결제방법'),
                ('payment_due_date', '결제예정일')
            ]
    
    # DataFrame 컬럼명 변경
    column_mapping = dict(columns_map)
    df = df.rename(columns=column_mapping)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name=excel_title)
        worksheet = writer.sheets[excel_title]
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            worksheet.set_column(idx, idx, max_length + 2)
    output.seek(0)
    return send_file(output, as_attachment=True, download_name=filename, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

@sales.route('/api/sales/payment/list', methods=['POST'])
@login_required
def sales_api_sales_payment_list():
    data = request.get_json()
    start_date = data.get('startDate')
    end_date = data.get('endDate')
    customer_code = data.get('customerCode')
    status = data.get('status')
    sales_no = data.get('salesNo')
    po_no = data.get('poNo')
    page = int(data.get('page', 1))
    per_page = int(data.get('itemsPerPage', 15))

    conn = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    # 첫 SELECT 조건 - 수금된 건들을 sales_no별로 집계
    select1 = '''
        SELECT
            MAX(p.payment_id) as payment_id,
            s.sales_no,
            s.sales_date,
            v.vd_name AS customer_name,
            s.po_no,
            s.warehouse_code,
            w.WH_NAME AS warehouse_name,
            s.currency_code,
            s.exchange_rate,
            s.payment_method,
            s.payment_due_date,
            p.payment_date,
            s.status,
            s.sales_status,
            SUM(p.amount) as amount,
            SUM(p.vat) as vat,
            MAX(p.payment_date) as payment_date,
            MAX(p.payment_method) AS payment_method_detail,
            MAX(p.remarks) as remarks,
            SUM(p.transfer_amount) as transfer_amount
        FROM sales_payment p
        LEFT JOIN sales_master s ON p.sales_no = s.sales_no
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        WHERE 1=1
'''
    params1 = []
    if start_date:
        select1 += ' AND s.sales_date >= ?'
        params1.append(start_date)
    if end_date:
        select1 += ' AND s.sales_date <= ?'
        params1.append(end_date)
    if customer_code:
        select1 += ' AND s.customer_code = ?'
        params1.append(customer_code)
    if status:
        select1 += ' AND s.status = ?'
        params1.append(status)
    if sales_no:
        select1 += ' AND s.sales_no = ?'
        params1.append(sales_no)
    if po_no:
        select1 += ' AND s.po_no LIKE ?'
        params1.append(f"%{po_no}%")
    
    # GROUP BY 절 추가
    select1 += '''
        GROUP BY s.sales_no, s.sales_date, v.vd_name, s.po_no, s.warehouse_code, 
                 w.WH_NAME, s.currency_code, s.exchange_rate, s.payment_method, 
                 s.payment_due_date, p.payment_date, s.status, s.sales_status
    '''
    
    # 두 번째 SELECT 조건
    select2 = '''
        SELECT
        NULL as payment_id,
        s.sales_no,
        s.sales_date,
        v.vd_name AS customer_name,
        s.po_no,
        s.warehouse_code,
        w.WH_NAME AS warehouse_name,
        s.currency_code,
        s.exchange_rate,
        s.payment_method,
        s.payment_due_date,
        p.payment_date,
        s.status,
        s.sales_status,               -- 추가 (select1과 맞춤)
        0 as amount,
        0 as vat,
        NULL as payment_date,
        NULL as payment_method_detail,
        NULL as remarks,
        0 as transfer_amount
        FROM sales_master s
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        LEFT JOIN sales_payment p ON s.sales_no = p.sales_no
        WHERE p.sales_no IS NULL
'''
    params2 = []
    if start_date:
        select2 += ' AND s.sales_date >= ?'
        params2.append(start_date)
    if end_date:
        select2 += ' AND s.sales_date <= ?'
        params2.append(end_date)
    if customer_code:
        select2 += ' AND s.customer_code = ?'
        params2.append(customer_code)
    if status:
        select2 += ' AND s.status = ?'
        params2.append(status)
    if sales_no:
        select2 += ' AND s.sales_no = ?'
        params2.append(sales_no)
    if po_no:
        select2 += ' AND s.po_no LIKE ?'
        params2.append(f"%{poNo}%")
    # 쿼리 합치기
    query = select1 + '\nUNION ALL\n' + select2 + '\nORDER BY sales_date DESC, sales_no DESC'
    # 페이징
    offset = (page - 1) * per_page
    query += ' OFFSET ? ROWS FETCH NEXT ? ROWS ONLY'
    params = params1 + params2 + [offset, per_page]
    cursor.execute(query, params)
    rows = cursor.fetchall()
    items = []
    for row in rows:
        # sales_detail에서 금액 정보 집계 (매출관리와 동일하게)
        conn2 = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
        cursor2 = conn2.cursor()
        cursor2.execute('''
            SELECT
                COALESCE(SUM(d.amount), 0) AS total_amount,
                COALESCE(SUM(d.amount), 0) * 0.07 AS total_vat,
                COALESCE(SUM(d.amount), 0) * 1.07 AS total_sum_amount
            FROM sales_detail d
            WHERE d.sales_no = ?
        ''', (row.sales_no,))
        m = cursor2.fetchone()
        total_amount = float(m[0]) if m else 0
        total_vat = float(m[1]) if m else 0
        total_sum = float(m[2]) if m else 0
        # sales_payment에서 수금금액(transfer_amount 합계)
        cursor2.execute('SELECT COALESCE(SUM(transfer_amount),0) FROM sales_payment WHERE sales_no = ?', (row.sales_no,))
        paid_amount = float(cursor2.fetchone()[0])
        unpaid_amount = total_sum - paid_amount
        items.append({
            'salesNo': row.sales_no,
            'salesDate': row.sales_date.strftime('%Y-%m-%d') if row.sales_date else '',
            'customerName': row.customer_name or '',
            'poNo': row.po_no or '',
            'warehouseName': row.warehouse_name or '',
            'amount': total_amount,  # 공급가액(총계)
            'vat': total_vat,        # 부가세
            'total': total_sum,      # 합계(공급가액+부가세)
            'currency': row.currency_code or '',
            'exchangeRate': float(row.exchange_rate) if row.exchange_rate else 0,
            'paymentMethod': row.payment_method or '',
            'paymentDueDate': row.payment_due_date.strftime('%Y-%m-%d') if row.payment_due_date else '',
            'status': row.status or '',
            'salesStatus': row.sales_status or '',
            'paidAmount': paid_amount,
            'unpaidAmount': unpaid_amount,
            'paymentDate': row.payment_date.strftime('%Y-%m-%d') if hasattr(row, 'payment_date') and row.payment_date else '',
            'paymentMethodDetail': row.payment_method_detail if hasattr(row, 'payment_method_detail') and row.payment_method_detail else '',
            'remarks': row.remarks if hasattr(row, 'remarks') and row.remarks else '',
            'transferAmount': float(row.transfer_amount) if hasattr(row, 'transfer_amount') and row.transfer_amount else 0
        })
        conn2.close()
    # 전체 카운트 (수금+미수금 합산)
    count_select1 = '''
        SELECT p.payment_id
        FROM sales_payment p
        LEFT JOIN sales_master s ON p.sales_no = s.sales_no
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        WHERE 1=1
'''
    count_params1 = []
    if start_date:
        count_select1 += ' AND s.sales_date >= ?'
        count_params1.append(start_date)
    if end_date:
        count_select1 += ' AND s.sales_date <= ?'
        count_params1.append(end_date)
    if customer_code:
        count_select1 += ' AND s.customer_code = ?'
        count_params1.append(customer_code)
    if status:
        count_select1 += ' AND s.status = ?'
        count_params1.append(status)
    if sales_no:
        count_select1 += ' AND s.sales_no = ?'
        count_params1.append(sales_no)
    count_select2 = '''
        SELECT NULL as payment_id
        FROM sales_master s
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN code_warehouse w ON s.warehouse_code = w.WH_CODE
        LEFT JOIN sales_payment p ON s.sales_no = p.sales_no
        WHERE p.sales_no IS NULL
'''
    count_params2 = []
    if start_date:
        count_select2 += ' AND s.sales_date >= ?'
        count_params2.append(start_date)
    if end_date:
        count_select2 += ' AND s.sales_date <= ?'
        count_params2.append(end_date)
    if customer_code:
        count_select2 += ' AND s.customer_code = ?'
        count_params2.append(customer_code)
    if status:
        count_select2 += ' AND s.status = ?'
        count_params2.append(status)
    if sales_no:
        count_select2 += ' AND s.sales_no = ?'
        count_params2.append(sales_no)
    count_query = 'SELECT COUNT(*) FROM ( ' + count_select1 + '\nUNION ALL\n' + count_select2 + ' ) t'
    count_params = count_params1 + count_params2
    cursor.execute(count_query, count_params)
    total_count = cursor.fetchone()[0]
    total_pages = (total_count + per_page - 1) // per_page

    return jsonify({
        'items': items,
        'pagination': {
            'current_page': page,
            'per_page': per_page,
            'total_count': total_count,
            'total_pages': total_pages
        }
    })

@sales.route('/api/sales/payment/summary', methods=['POST'])
@sales.route('/api/sales/payment/summary_nopay', methods=['POST'])
@login_required
def api_sales_payment_summary():
    data = request.get_json()
    start_date    = data.get('startDate')
    end_date      = data.get('endDate')
    customer_code = data.get('customerCode')
    currency      = data.get('currency')
    page          = int(data.get('page', 1))
    page_size     = int(data.get('pageSize', 20))

    conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    query = '''
        SELECT
            v.vd_name     AS customer_name,
            s.currency_code,
            SUM(COALESCE(d.total_amount, 0))        AS total_amount,
            SUM(COALESCE(d.total_amount, 0)) * 0.07 AS vat_amount,
            SUM(COALESCE(d.total_amount, 0)) * 1.07 AS sum_amount,
            SUM(COALESCE(p.paid_amount,   0))        AS paid_amount
        FROM sales_master s
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN (
            SELECT sales_no, SUM(amount) AS total_amount
            FROM sales_detail
            GROUP BY sales_no
        ) d ON s.sales_no = d.sales_no
        LEFT JOIN (
            SELECT sales_no, SUM(transfer_amount) AS paid_amount
            FROM sales_payment
            GROUP BY sales_no
        ) p ON s.sales_no = p.sales_no
        WHERE 1=1
    '''
    params = []
    if start_date:
        query += ' AND s.sales_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND s.sales_date <= ?'
        params.append(end_date)
    if customer_code:
        query += ' AND s.customer_code = ?'
        params.append(customer_code)
    if currency:
        query += ' AND s.currency_code = ?'
        params.append(currency)
    query += ' GROUP BY v.vd_name, s.currency_code ORDER BY v.vd_name, s.currency_code'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    items = []
    for row in rows:
        total_amount = float(row.total_amount) if row.total_amount else 0
        vat_amount   = float(row.vat_amount)   if row.vat_amount   else 0
        sum_amount   = float(row.sum_amount)   if row.sum_amount   else 0
        paid_amount  = float(row.paid_amount)  if row.paid_amount  else 0
        items.append({
            'customerName': row.customer_name or '',
            'currency':     row.currency_code or '',
            'exchangeRate': 0,
            'totalAmount':  total_amount,
            'vatAmount':    vat_amount,
            'sumAmount':    sum_amount,
            'paidAmount':   paid_amount,
            'unpaidAmount': sum_amount - paid_amount,
            'salesStatus':  'COMPLETED' if (sum_amount - paid_amount) <= 0 else 'ING'
        })

    total_count = len(items)
    total_pages = (total_count + page_size - 1) // page_size if page_size else 1
    paged_items = items[(page - 1) * page_size : page * page_size]

    return jsonify({
        'items': paged_items,
        'pagination': {
            'current_page': page,
            'per_page':     page_size,
            'total_count':  total_count,
            'total_pages':  total_pages
        }
    })

@sales.route('/api/sales/payment/summary/excel', methods=['POST'])
@sales.route('/api/sales/payment/summary_nopay/excel', methods=['POST'])
@login_required
def api_sales_payment_summary_excel():
    data = request.get_json()
    start_date    = data.get('startDate')
    end_date      = data.get('endDate')
    customer_code = data.get('customerCode')
    currency      = data.get('currency')

    lang = session.get('language', 'ko')
    if lang == 'th':
        excel_title = 'สรุปยอดรับชำระ'
        filename    = f'สรุปยอดรับชำระ_{datetime.now().strftime("%Y%m%d")}.xlsx'
    else:
        excel_title = '수금현황집계'
        filename    = f'수금현황집계_{datetime.now().strftime("%Y%m%d")}.xlsx'

    conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    query = '''
        SELECT
            v.vd_name     AS customer_name,
            s.currency_code,
            SUM(COALESCE(d.total_amount, 0))        AS total_amount,
            SUM(COALESCE(d.total_amount, 0)) * 0.07 AS vat_amount,
            SUM(COALESCE(d.total_amount, 0)) * 1.07 AS sum_amount,
            SUM(COALESCE(p.paid_amount,   0))        AS paid_amount
        FROM sales_master s
        LEFT JOIN code_vendor v ON s.customer_code = v.vd_code
        LEFT JOIN (
            SELECT sales_no, SUM(amount) AS total_amount
            FROM sales_detail
            GROUP BY sales_no
        ) d ON s.sales_no = d.sales_no
        LEFT JOIN (
            SELECT sales_no, SUM(transfer_amount) AS paid_amount
            FROM sales_payment
            GROUP BY sales_no
        ) p ON s.sales_no = p.sales_no
        WHERE 1=1
    '''
    params = []
    if start_date:
        query += ' AND s.sales_date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND s.sales_date <= ?'
        params.append(end_date)
    if customer_code:
        query += ' AND s.customer_code = ?'
        params.append(customer_code)
    if currency:
        query += ' AND s.currency_code = ?'
        params.append(currency)
    query += ' GROUP BY v.vd_name, s.currency_code ORDER BY v.vd_name, s.currency_code'

    cursor.execute(query, params)
    rows = cursor.fetchall()

    items = []
    for row in rows:
        total_amount = float(row.total_amount) if row.total_amount else 0
        vat_amount   = float(row.vat_amount)   if row.vat_amount   else 0
        sum_amount   = float(row.sum_amount)   if row.sum_amount   else 0
        paid_amount  = float(row.paid_amount)  if row.paid_amount  else 0
        items.append({
            'customerName': row.customer_name or '',
            'currency':     row.currency_code or '',
            'totalAmount':  total_amount,
            'vatAmount':    vat_amount,
            'sumAmount':    sum_amount,
            'paidAmount':   paid_amount,
            'unpaidAmount': sum_amount - paid_amount
        })

    df = pd.DataFrame(items)

    if lang == 'th':
        columns_map = [
            ('customerName', 'ชื่อลูกค้า'),
            ('currency',     'สกุลเงิน'),
            ('totalAmount',  'จำนวนเงินรวม'),
            ('vatAmount',    'ภาษีมูลค่าเพิ่ม'),
            ('sumAmount',    'ยอดรวมสุทธิ'),
            ('paidAmount',   'จำนวนเงินที่ชำระแล้ว'),
            ('unpaidAmount', 'จำนวนเงินที่ยังไม่ได้ชำระ'),
        ]
    else:
        columns_map = [
            ('customerName', '고객명'),
            ('currency',     '통화'),
            ('totalAmount',  '공급가액'),
            ('vatAmount',    '부가세'),
            ('sumAmount',    '합계금액'),
            ('paidAmount',   '수금액'),
            ('unpaidAmount', '미수금액'),
        ]

    column_mapping = dict(columns_map)
    df = df.rename(columns=column_mapping)

    if df.empty:
        df = pd.DataFrame(columns=list(column_mapping.values()))
    else:
        sums = df.select_dtypes(include=[np.number]).sum()
        sums_dict = {col: (sums[col] if col in sums else ('합계' if i == 0 else '')) for i, col in enumerate(df.columns)}
        df = pd.concat([df, pd.DataFrame([sums_dict])], ignore_index=True)

    filename = re.sub(r'[^a-zA-Z0-9_.가-힣]', '_', filename)

    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name=excel_title, index=False)
        worksheet = writer.sheets[excel_title]
        for idx, col in enumerate(df.columns):
            max_length = max(df[col].astype(str).apply(len).max(), len(str(col)))
            worksheet.set_column(idx, idx, max_length + 2)
    output.seek(0)
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )