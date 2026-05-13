import pyodbc
from config import config

def create_financial_close_table():
    """financial_close 테이블 생성"""
    try:
        conn = pyodbc.connect(config['development'].PYODBC_CONN_STR)
        cursor = conn.cursor()
        
        # 테이블 존재 여부 확인
        cursor.execute("SELECT COUNT(*) FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME = 'financial_close'")
        exists = cursor.fetchone()[0] > 0
        
        if not exists:
            # 테이블 생성
            create_table_sql = """
            CREATE TABLE financial_close (
                id INT IDENTITY(1,1) PRIMARY KEY,
                close_date DATE NOT NULL,
                total_purchase DECIMAL(18,2) DEFAULT 0,
                total_purchase_payment DECIMAL(18,2) DEFAULT 0,
                total_sales DECIMAL(18,2) DEFAULT 0,
                total_sales_payment DECIMAL(18,2) DEFAULT 0,
                closed_by VARCHAR(100),
                closed_at DATETIME DEFAULT GETDATE(),
                created_at DATETIME DEFAULT GETDATE(),
                updated_at DATETIME DEFAULT GETDATE()
            )
            """
            cursor.execute(create_table_sql)
            
            # 인덱스 생성
            cursor.execute("CREATE INDEX IX_financial_close_date ON financial_close(close_date)")
            cursor.execute("CREATE INDEX IX_financial_close_closed_at ON financial_close(closed_at)")
            
            conn.commit()
            print("✅ financial_close 테이블이 성공적으로 생성되었습니다.")
        else:
            print("ℹ️ financial_close 테이블이 이미 존재합니다.")
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"❌ 테이블 생성 실패: {e}")

if __name__ == "__main__":
    create_financial_close_table() 