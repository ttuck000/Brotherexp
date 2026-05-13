-- Financial Close 테이블 생성
IF NOT EXISTS (SELECT * FROM sysobjects WHERE name='financial_close' AND xtype='U')
BEGIN
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
    
    -- 인덱스 생성
    CREATE INDEX IX_financial_close_date ON financial_close(close_date)
    CREATE INDEX IX_financial_close_closed_at ON financial_close(closed_at)
    
    PRINT 'financial_close 테이블이 성공적으로 생성되었습니다.'
END
ELSE
BEGIN
    PRINT 'financial_close 테이블이 이미 존재합니다.'
END 