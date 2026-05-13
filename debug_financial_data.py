import pyodbc
from datetime import datetime, date
from calendar import monthrange
from config import config

def test_database_connection():
    """데이터베이스 연결 테스트"""
    try:
        conn = pyodbc.connect(config['development'].PYODBC_CONN_STR)
        print("✅ 데이터베이스 연결 성공")
        return conn
    except Exception as e:
        print(f"❌ 데이터베이스 연결 실패: {e}")
        return None

def check_table_exists(conn, table_name):
    """테이블 존재 여부 확인"""
    try:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = '{table_name}'")
        exists = cursor.fetchone()[0] > 0
        print(f"{'✅' if exists else '❌'} {table_name} 테이블: {'존재함' if exists else '존재하지 않음'}")
        return exists
    except Exception as e:
        print(f"❌ {table_name} 테이블 확인 실패: {e}")
        return False

def check_table_data(conn, table_name, date_column):
    """테이블 데이터 확인"""
    try:
        cursor = conn.cursor()
        
        # 전체 데이터 수 확인
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        total_count = cursor.fetchone()[0]
        print(f"📊 {table_name} 전체 데이터 수: {total_count}")
        
        if total_count > 0:
            # 최근 데이터 5개 확인
            cursor.execute(f"SELECT TOP 5 * FROM {table_name} ORDER BY {date_column} DESC")
            recent_data = cursor.fetchall()
            print(f"📅 {table_name} 최근 데이터:")
            for row in recent_data:
                print(f"   {row}")
        
        return total_count
    except Exception as e:
        print(f"❌ {table_name} 데이터 확인 실패: {e}")
        return 0

def test_financial_queries(conn):
    """재무 쿼리 테스트"""
    try:
        cursor = conn.cursor()
        
        # 기본값 설정: 당월 1일부터 마지막일까지
        today = date.today()
        first_day = date(today.year, today.month, 1)
        last_day = date(today.year, today.month, monthrange(today.year, today.month)[1])
        
        start_date = first_day.strftime('%Y-%m-%d')
        end_date = last_day.strftime('%Y-%m-%d')
        
        print(f"\n🔍 조회 기간: {start_date} ~ {end_date}")
        
        # 매입 데이터 쿼리
        purchase_query = """
            SELECT 
                SUM(p.total_amount) as total_purchase,
                SUM(COALESCE(pp.amount, 0)) as total_purchase_payment
            FROM purchase_master p
            LEFT JOIN purchase_payment pp ON p.purchase_no = pp.purchase_no
            WHERE p.purchase_date >= ? AND p.purchase_date <= ?
        """
        
        cursor.execute(purchase_query, (start_date, end_date))
        purchase_summary = cursor.fetchone()
        print(f"💰 매입 집계: {purchase_summary}")
        
        # 매출 데이터 쿼리
        sales_query = """
            SELECT 
                SUM(s.total_amount) as total_sales,
                SUM(COALESCE(sp.amount, 0)) as total_sales_payment
            FROM sales_master s
            LEFT JOIN sales_payment sp ON s.sales_no = sp.sales_no
            WHERE s.sales_date >= ? AND s.sales_date <= ?
        """
        
        cursor.execute(sales_query, (start_date, end_date))
        sales_summary = cursor.fetchone()
        print(f"💰 매출 집계: {sales_summary}")
        
        # 전체 기간 데이터 확인
        print(f"\n🔍 전체 기간 데이터 확인:")
        
        cursor.execute("SELECT MIN(purchase_date), MAX(purchase_date) FROM purchase_master")
        purchase_date_range = cursor.fetchone()
        print(f"📅 매입 데이터 기간: {purchase_date_range}")
        
        cursor.execute("SELECT MIN(sales_date), MAX(sales_date) FROM sales_master")
        sales_date_range = cursor.fetchone()
        print(f"📅 매출 데이터 기간: {sales_date_range}")
        
    except Exception as e:
        print(f"❌ 재무 쿼리 테스트 실패: {e}")

def main():
    print("🔧 재무 데이터 디버깅 시작")
    print("=" * 50)
    
    # 데이터베이스 연결
    conn = test_database_connection()
    if not conn:
        return
    
    try:
        # 테이블 존재 여부 확인
        print("\n📋 테이블 존재 여부 확인:")
        tables_to_check = [
            ('purchase_master', 'purchase_date'),
            ('purchase_payment', 'payment_date'),
            ('sales_master', 'sales_date'),
            ('sales_payment', 'payment_date'),
            ('financial_close', 'close_date')
        ]
        
        for table_name, date_column in tables_to_check:
            check_table_exists(conn, table_name)
        
        # 데이터 확인
        print("\n📊 테이블 데이터 확인:")
        for table_name, date_column in tables_to_check:
            check_table_data(conn, table_name, date_column)
        
        # 재무 쿼리 테스트
        print("\n💰 재무 쿼리 테스트:")
        test_financial_queries(conn)
        
    finally:
        conn.close()
        print("\n🔧 디버깅 완료")

if __name__ == "__main__":
    main() 