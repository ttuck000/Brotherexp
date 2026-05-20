-- Car_Use_Request: 사업부(company) — code_Account.company 와 동일 값
USE BRO_EXPENSE;
GO

IF COL_LENGTH('dbo.Car_Use_Request', 'Company') IS NULL
BEGIN
    ALTER TABLE dbo.Car_Use_Request
        ADD Company NVARCHAR(100) NULL;
END
GO
