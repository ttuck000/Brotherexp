from flask import Blueprint, jsonify, current_app
import pyodbc
from datetime import datetime
from flask_login import login_required

dashboard = Blueprint('dashboard', __name__, url_prefix='/api/dashboard')

def get_conn():
    return pyodbc.connect(current_app.config['PYODBC_CONN_STR'])

@dashboard.route('/purchase')
def dashboard_purchase():
    conn = get_conn()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    month_str = datetime.now().strftime('%Y-%m')
    # 오늘 매입
    cursor.execute("SELECT SUM(total_amount) FROM purchase_master WHERE CONVERT(date, purchase_date) = ?", (today_str,))
    today = cursor.fetchone()[0] or 0
    # 이번달 매입
    cursor.execute("SELECT SUM(total_amount) FROM purchase_master WHERE FORMAT(purchase_date, 'yyyy-MM') = ?", (month_str,))
    month = cursor.fetchone()[0] or 0
    # 미결제 매입
    cursor.execute("SELECT SUM(total_amount) FROM purchase_master WHERE status != 'COMPLETED'")
    pending = cursor.fetchone()[0] or 0
    # 총 매입
    year_str = datetime.now().strftime('%Y')
    cursor.execute("SELECT SUM(total_amount) FROM purchase_master WHERE FORMAT(purchase_date, 'yyyy') = ?", (year_str,))
    total = cursor.fetchone()[0] or 0
    conn.close()
    return jsonify({"today": today, "month": month, "pending": pending, "total": total})

@dashboard.route('/sales')
def dashboard_sales():
    conn = get_conn()
    cursor = conn.cursor()
    today_str = datetime.now().strftime('%Y-%m-%d')
    month_str = datetime.now().strftime('%Y-%m')
    # 오늘 매출
    cursor.execute("SELECT SUM(total_amount) FROM sales_master WHERE CONVERT(date, sales_date) = ?", (today_str,))
    today = cursor.fetchone()[0] or 0
    # 이번달 매출
    cursor.execute("SELECT SUM(total_amount) FROM sales_master WHERE FORMAT(sales_date, 'yyyy-MM') = ?", (month_str,))
    month = cursor.fetchone()[0] or 0
    # 미결제 매출
    cursor.execute("SELECT SUM(total_amount) FROM sales_master WHERE status != 'COMPLETED'")
    pending = cursor.fetchone()[0] or 0
    # 총 매출
    year_str = datetime.now().strftime('%Y')
    cursor.execute("SELECT SUM(total_amount) FROM sales_master WHERE FORMAT(sales_date, 'yyyy') = ?", (year_str,))
    total = cursor.fetchone()[0] or 0
    conn.close()
    return jsonify({"today": today, "month": month, "pending": pending, "total": total})

@dashboard.route('/inventory')
@login_required
def dashboard_inventory():
    conn   = pyodbc.connect('DRIVER={ODBC Driver 17 for SQL Server};SERVER=118.67.132.208;DATABASE=BIGBOY;UID=brother;PWD=jobgate@m1n;')
    cursor = conn.cursor()

    # 아이템별 최신 BalanceQty (WarehouseCode별 최신 트랜잭션)
    cursor.execute("""
        WITH LatestBalance AS (
            SELECT
                WarehouseCode,
                ItemCode,
                BalanceQty,
                ROW_NUMBER() OVER (
                    PARTITION BY WarehouseCode, ItemCode
                    ORDER BY TransDate DESC, TransId DESC
                ) AS rn
            FROM Inventory_Transaction
        ),
        CurrentStock AS (
            SELECT WarehouseCode, ItemCode, BalanceQty
            FROM LatestBalance
            WHERE rn = 1
        ),
        Categorized AS (
            SELECT
                cs.ItemCode,
                cs.BalanceQty,
                COALESCE(im.purchasePrice, 0) AS purchasePrice,
                CASE
                    WHEN UPPER(cs.WarehouseCode) LIKE '%SCRAP%'    THEN 'scrap'
                    WHEN UPPER(cs.WarehouseCode) LIKE '%COMPOUND%' THEN 'compound'
                    WHEN UPPER(cs.WarehouseCode) LIKE '%PART%'     THEN 'part'
                    ELSE 'other'
                END AS category
            FROM CurrentStock cs
            LEFT JOIN ItemMaster im ON cs.ItemCode = im.ItemCode
        )
        SELECT
            category,
            COUNT(DISTINCT ItemCode)                          AS total_items,
            COALESCE(SUM(BalanceQty), 0)                     AS total_qty,
            COALESCE(SUM(CASE WHEN BalanceQty > 0 AND BalanceQty <= 10 THEN 1 ELSE 0 END), 0) AS low_stock,
            COALESCE(SUM(CASE WHEN BalanceQty <= 0 THEN 1 ELSE 0 END), 0) AS out_of_stock,
            COALESCE(SUM(BalanceQty * purchasePrice), 0)     AS total_value
        FROM Categorized
        GROUP BY category
    """)
    rows = cursor.fetchall()
    conn.close()

    # 카테고리별 딕셔너리 생성
    cat_map = {}
    for r in rows:
        cat_map[r[0]] = {
            'total_items':  int(r[1]),
            'total_qty':    float(r[2]),
            'low_stock':    int(r[3]),
            'out_of_stock': int(r[4]),
            'total_value':  float(r[5])
        }

    def get_cat(key):
        return cat_map.get(key, {'total_items': 0, 'total_qty': 0, 'low_stock': 0, 'out_of_stock': 0, 'total_value': 0})

    part     = get_cat('part')
    scrap    = get_cat('scrap')
    compound = get_cat('compound')

    # 전체 합산
    all_cats = list(cat_map.values())
    return jsonify({
        'total_items':  sum(c['total_items']  for c in all_cats),
        'total_qty':    sum(c['total_qty']    for c in all_cats),
        'low_stock':    sum(c['low_stock']    for c in all_cats),
        'out_of_stock': sum(c['out_of_stock'] for c in all_cats),
        'total_value':  sum(c['total_value']  for c in all_cats),
        'part':     part,
        'scrap':    scrap,
        'compound': compound,
    })

@dashboard.route('/financial')
def dashboard_financial():
    conn = get_conn()
    cursor = conn.cursor()
    now = datetime.now()
    month_str = now.strftime('%Y-%m')
    year_str = now.strftime('%Y')
    # 월 매출
    cursor.execute("SELECT SUM(total_amount) FROM sales_master WHERE FORMAT(sales_date, 'yyyy-MM') = ?", (month_str,))
    monthly_revenue = cursor.fetchone()[0] or 0
    # 월 지출
    cursor.execute("SELECT SUM(total_amount) FROM purchase_master WHERE FORMAT(purchase_date, 'yyyy-MM') = ?", (month_str,))
    monthly_expense = cursor.fetchone()[0] or 0
    # 월 이익
    monthly_profit = monthly_revenue - monthly_expense
    # 연간 이익
    cursor.execute("SELECT SUM(total_amount) FROM sales_master WHERE FORMAT(sales_date, 'yyyy') = ?", (year_str,))
    yearly_sales = cursor.fetchone()[0] or 0
    cursor.execute("SELECT SUM(total_amount) FROM purchase_master WHERE FORMAT(purchase_date, 'yyyy') = ?", (year_str,))
    yearly_purchase = cursor.fetchone()[0] or 0
    yearly_profit = yearly_sales - yearly_purchase
    conn.close()
    return jsonify({"monthlyRevenue": monthly_revenue, "monthlyExpense": monthly_expense, "monthlyProfit": monthly_profit, "yearlyProfit": yearly_profit})

@dashboard.route('/sales/daily')
def dashboard_sales_daily():
    # 일별 매출 추이 (최근 30일)
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT sales_date as day, SUM(total_amount) FROM sales_master WHERE sales_date >= DATEADD(day, -30, GETDATE()) GROUP BY sales_date ORDER BY day")
    rows = cursor.fetchall()
    data = [{"date": str(row[0]), "amount": float(row[1]) if row[1] is not None else 0} for row in rows]
    conn.close()
    return jsonify(data)

@dashboard.route('/purchase/daily')
def dashboard_purchase_daily():
    # 일별 매입 추이 (최근 30일)
    conn = get_conn()
    cursor = conn.cursor()
    cursor.execute("SELECT purchase_date as day, SUM(total_amount) FROM purchase_master WHERE purchase_date >= DATEADD(day, -30, GETDATE()) GROUP BY purchase_date ORDER BY day")
    rows = cursor.fetchall()
    data = [{"date": str(row[0]), "amount": float(row[1]) if row[1] is not None else 0} for row in rows]
    conn.close()
    return jsonify(data)