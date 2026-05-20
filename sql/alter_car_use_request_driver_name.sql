-- Car_Use_Request: 운전자 (DriverName) — UserName = 신청자(Requester)
USE BRO_EXPENSE;
GO

IF COL_LENGTH('dbo.Car_Use_Request', 'DriverName') IS NULL
BEGIN
    ALTER TABLE dbo.Car_Use_Request
        ADD DriverName NVARCHAR(200) NULL;
END
GO

-- 기존 데이터: 운전자 미입력 시 신청자와 동일하게
UPDATE dbo.Car_Use_Request
SET DriverName = UserName
WHERE DriverName IS NULL OR LTRIM(RTRIM(DriverName)) = '';
GO
