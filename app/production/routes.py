from app.production import bp as production
from flask import render_template, request, jsonify
from flask_login import current_user
from app.auth.routes import login_required
import pyodbc
from datetime import datetime

DB = 'DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;'

@production.route('/production')
@login_required
def production_page():
    return render_template('production/list.html')

@production.route('/production/list')
@login_required
def production_list():
    date_from    = request.args.get('date_from', '')
    date_to      = request.args.get('date_to', '')
    company_code = request.args.get('company_code', '')
    process      = request.args.get('process', '')
    product_line = request.args.get('product_line', '')
    item_code    = request.args.get('item_code', '')
    try:
        conn   = pyodbc.connect(DB)
        cursor = conn.cursor()
        query  = """SELECT ProductionID, ProductionDate, Productionstart, Productionto,
                           CompanyCode, Process, ProductLine, ItemCode,
                           PlannedQty, ProducedQty, DefectQty, InputItem, Worker, Remark
                    FROM dbo.production_log WHERE 1=1"""
        params = []
        if date_from:    query += " AND ProductionDate >= ?"; params.append(date_from)
        if date_to:      query += " AND ProductionDate <= ?"; params.append(date_to)
        if company_code: query += " AND CompanyCode = ?";     params.append(company_code)
        if process:      query += " AND Process = ?";         params.append(process)
        if product_line: query += " AND ProductLine = ?";     params.append(product_line)
        if item_code:    query += " AND ItemCode = ?";        params.append(item_code)
        query += " ORDER BY ProductionDate DESC, ProductionID DESC"
        cursor.execute(query, params)
        rows   = cursor.fetchall()
        result = []
        for r in rows:
            start_str = str(r.Productionstart)[:5] if r.Productionstart is not None else ''
            to_str    = str(r.Productionto)[:5]    if r.Productionto    is not None else ''
            result.append({
                'ProductionID'   : r.ProductionID,
                'ProductionDate' : str(r.ProductionDate)[:10] if r.ProductionDate else '',
                'Productionstart': start_str,
                'Productionto'   : to_str,
                'CompanyCode'    : r.CompanyCode or '',
                'Process'        : r.Process     or '',
                'ProductLine'    : r.ProductLine or '',
                'ItemCode'       : r.ItemCode    or '',
                'PlannedQty'     : r.PlannedQty,
                'ProducedQty'    : r.ProducedQty,
                'DefectQty'      : r.DefectQty,
                'InputItem'      : r.InputItem   or '',
                'Worker'         : r.Worker      or '',
                'Remark'         : r.Remark      or ''
            })
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@production.route('/production/detail/<int:prod_id>')
@login_required
def production_detail(prod_id):
    try:
        conn   = pyodbc.connect(DB)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM dbo.production_log WHERE ProductionID = ?", (prod_id,))
        r = cursor.fetchone()
        if not r: return jsonify({'error': 'Not found'}), 404
        start_str = str(r.Productionstart)[:5] if r.Productionstart is not None else ''
        to_str    = str(r.Productionto)[:5]    if r.Productionto    is not None else ''
        return jsonify({
            'ProductionID'   : r.ProductionID,
            'ProductionDate' : str(r.ProductionDate)[:10] if r.ProductionDate else '',
            'Productionstart': start_str,
            'Productionto'   : to_str,
            'CompanyCode'    : r.CompanyCode or '',
            'Process'        : r.Process     or '',
            'ProductLine'    : r.ProductLine or '',
            'ItemCode'       : r.ItemCode    or '',
            'PlannedQty'     : r.PlannedQty,
            'ProducedQty'    : r.ProducedQty,
            'DefectQty'      : r.DefectQty,
            'InputItem'      : r.InputItem   or '',
            'Worker'         : r.Worker      or '',
            'Remark'         : r.Remark      or ''
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        try: cursor.close(); conn.close()
        except: pass

@production.route('/production/save', methods=['POST'])
@login_required
def production_save():
    data = request.get_json()
    try:
        conn        = pyodbc.connect(DB)
        cursor      = conn.cursor()
        create_user = current_user.username if hasattr(current_user, 'username') else 'system'
        create_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        planned_qty  = data.get('PlannedQty')
        produced_qty = data.get('ProducedQty')
        defect_qty   = data.get('DefectQty')
        input_item   = data.get('InputItem') or None

        # ── production_log INSERT → OUTPUT INSERTED 로 ProductionID 취득 ─────
        cursor.execute("""
            INSERT INTO dbo.production_log
            (ProductionDate, Productionstart, Productionto,
             CompanyCode, Process, ProductLine, ItemCode,
             PlannedQty, ProducedQty, DefectQty, InputItem, Worker, Remark)
            OUTPUT INSERTED.ProductionID
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (data.get('ProductionDate'),
              data.get('Productionstart'), data.get('Productionto'),
              data.get('CompanyCode'), data.get('Process'),
              data.get('ProductLine'), data.get('ItemCode'),
              planned_qty, produced_qty, defect_qty,
              input_item, data.get('Worker'), data.get('Remark')))

        row           = cursor.fetchone()
        production_id = int(row[0]) if (row and row[0] is not None) else None

        item_code = (data.get('ItemCode') or '').strip()

        # ── SC / CO 분기: 재고 트랜잭션 2건 자동 생성 ────────────────────────
        is_sc = item_code.upper().startswith('SC')
        is_co = item_code.upper().startswith('CO')

        if (is_sc or is_co) and production_id:
            qty       = float(produced_qty or 0)
            prod_date = data.get('ProductionDate')
            ref_no    = str(production_id)
            in_item   = (input_item or '').strip()

            # SC: 출고=A_Part  / 입고=B_Scrap
            # CO: 출고=B_Scrap / 입고=C_Compound
            out_warehouse = 'A_Part'      if is_sc else 'B_Scrap'
            in_warehouse  = 'B_Scrap'     if is_sc else 'C_Compound'

            # 1) 생산출고 : OUT / O22 / ItemCode = InputItem
            cursor.execute(
                'SELECT TOP 1 BalanceQty FROM Inventory_Transaction '
                'WHERE ItemCode = ? AND WarehouseCode = ? ORDER BY TransId DESC',
                (in_item, out_warehouse)
            )
            r_out       = cursor.fetchone()
            bal_out     = float(r_out.BalanceQty) if (r_out and r_out.BalanceQty is not None) else 0.0
            new_bal_out = bal_out - qty

            cursor.execute("""
                INSERT INTO Inventory_Transaction
                (TransDate, WarehouseCode, ItemCode, LotNo, TransType, TransType2,
                 RefNo, InQty, OutQty, BalanceQty, Remarks, CreateUser, CreateDate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prod_date, out_warehouse, in_item, '', 'OUT', 'O22',
                  ref_no, 0, qty, new_bal_out, 'Production', create_user, create_date))

            # 2) 생산입고 : IN / I11 / ItemCode = ItemCode (SC or CO 품목)
            cursor.execute(
                'SELECT TOP 1 BalanceQty FROM Inventory_Transaction '
                'WHERE ItemCode = ? AND WarehouseCode = ? ORDER BY TransId DESC',
                (item_code, in_warehouse)
            )
            r_in       = cursor.fetchone()
            bal_in     = float(r_in.BalanceQty) if (r_in and r_in.BalanceQty is not None) else 0.0
            new_bal_in = bal_in + qty

            cursor.execute("""
                INSERT INTO Inventory_Transaction
                (TransDate, WarehouseCode, ItemCode, LotNo, TransType, TransType2,
                 RefNo, InQty, OutQty, BalanceQty, Remarks, CreateUser, CreateDate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (prod_date, in_warehouse, item_code, '', 'IN', 'I11',
                  ref_no, qty, 0, new_bal_in, 'Production', create_user, create_date))
        # ──────────────────────────────────────────────────────────────────────

        conn.commit()
        return jsonify({'success': True, 'production_id': production_id})
    except Exception as e:
        try: conn.rollback()
        except: pass
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try: cursor.close(); conn.close()
        except: pass

@production.route('/production/update', methods=['POST'])
@login_required
def production_update():
    data = request.get_json()
    try:
        conn   = pyodbc.connect(DB)
        cursor = conn.cursor()

        planned_qty  = data.get('PlannedQty')
        produced_qty = data.get('ProducedQty')
        defect_qty   = data.get('DefectQty')
        input_item   = data.get('InputItem') or None

        cursor.execute("""
            UPDATE dbo.production_log
            SET ProductionDate=?, Productionstart=?, Productionto=?,
                CompanyCode=?, Process=?, ProductLine=?, ItemCode=?,
                PlannedQty=?, ProducedQty=?, DefectQty=?, InputItem=?, Worker=?, Remark=?
            WHERE ProductionID=?
        """, (data.get('ProductionDate'),
              data.get('Productionstart'), data.get('Productionto'),
              data.get('CompanyCode'), data.get('Process'),
              data.get('ProductLine'), data.get('ItemCode'),
              planned_qty, produced_qty, defect_qty,
              input_item, data.get('Worker'), data.get('Remark'), data.get('id')))
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try: cursor.close(); conn.close()
        except: pass

@production.route('/production/delete', methods=['POST'])
@login_required
def production_delete():
    data = request.get_json()
    ids  = data.get('ids', [])
    if not ids: return jsonify({'success': False, 'error': 'No ids'})
    try:
        conn   = pyodbc.connect(DB)
        cursor = conn.cursor()
        placeholders = ','.join(['?'] * len(ids))
        cursor.execute(f"DELETE FROM dbo.production_log WHERE ProductionID IN ({placeholders})", ids)
        conn.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})
    finally:
        try: cursor.close(); conn.close()
        except: pass