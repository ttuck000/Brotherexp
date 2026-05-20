-- BRO_EXPENSE: 차량 사용 신청 (5대는 앱 CAR_VEHICLES 리스트, DB 마스터 없음)
USE BRO_EXPENSE;
GO

IF OBJECT_ID(N'dbo.Car_Use_Request', N'U') IS NULL
BEGIN
    CREATE TABLE dbo.Car_Use_Request (
        ID            INT IDENTITY(1,1) NOT NULL,
        SubmittedAt   DATETIME2(0)      NOT NULL
            CONSTRAINT DF_CarUse_SubmittedAt DEFAULT SYSDATETIME(),
        UseDate       DATE              NOT NULL,
        usedateto     DATE              NULL,
        is_allday     BIT               NOT NULL CONSTRAINT DF_Car_Use_Request_is_allday DEFAULT 0,
        TimeFrom      TIME(0)           NOT NULL,
        TimeTo        TIME(0)           NOT NULL,
        VehicleCode   NVARCHAR(50)      NOT NULL,
        VehicleLabel  NVARCHAR(500)     NOT NULL,
        UserName      NVARCHAR(200)     NOT NULL,
        DriverName    NVARCHAR(200)     NULL,
        Company       NVARCHAR(100)     NULL,
        [Location]    NVARCHAR(500)     NOT NULL,
        Remark        NVARCHAR(MAX)     NULL,
        Approved      NVARCHAR(100)     NULL,
        CreatedBy     NVARCHAR(100)     NULL,
        CONSTRAINT PK_Car_Use_Request PRIMARY KEY CLUSTERED (ID)
    );
END
GO
