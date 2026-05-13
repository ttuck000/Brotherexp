import pyodbc
from config import config

def check_table_structure():
    """테이블 구조 확인"""
    try:
        conn = pyodbc.connect(config['development'].PYODBC_CONN_STR)
        cursor = conn.cursor()
        
        # purchase_payment 테이블 구조 확인
        print("📋 purchase_payment 테이블 구조:")
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'purchase_payment' ORDER BY ORDINAL_POSITION")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   {col[0]}: {col[1]}")
        
        print("\n📋 sales_payment 테이블 구조:")
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sales_payment' ORDER BY ORDINAL_POSITION")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   {col[0]}: {col[1]}")
        
        print("\n📋 purchase_master 테이블 구조:")
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'purchase_master' ORDER BY ORDINAL_POSITION")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   {col[0]}: {col[1]}")
        
        print("\n📋 sales_master 테이블 구조:")
        cursor.execute("SELECT COLUMN_NAME, DATA_TYPE FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_NAME = 'sales_master' ORDER BY ORDINAL_POSITION")
        columns = cursor.fetchall()
        for col in columns:
            print(f"   {col[0]}: {col[1]}")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 테이블 구조 확인 실패: {e}")

if __name__ == "__main__":
    check_table_structure() 