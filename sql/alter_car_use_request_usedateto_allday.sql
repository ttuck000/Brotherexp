-- Car_Use_Request: 사용 종료일, 종일 여부
USE BRO_EXPENSE;
GO

IF COL_LENGTH('dbo.Car_Use_Request', 'usedateto') IS NULL
BEGIN
    ALTER TABLE dbo.Car_Use_Request
    ADD usedateto DATE NULL;
END
GO

IF COL_LENGTH('dbo.Car_Use_Request', 'is_allday') IS NULL
BEGIN
    ALTER TABLE dbo.Car_Use_Request
    ADD is_allday BIT NOT NULL CONSTRAINT DF_Car_Use_Request_is_allday DEFAULT 0;
END
GO
