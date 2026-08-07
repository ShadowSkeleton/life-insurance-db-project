-- Jingrui Feng (jf4446) - database systems project part 3 - application data loader
-- Load APPLICATION after Contract and RATE_VERSION. The CSV omits the IDENTITY
-- key. LoadRow preserves file order so application IDs 1..60,000 correspond to
-- bound contracts 1..60,000 before Contract.ApplicationID is backfilled.
SET NOCOUNT ON;
GO

CREATE TABLE #ApplicationStage (
    CustomerIDRaw VARCHAR(30) NULL,
    ProductIDRaw VARCHAR(30) NULL,
    ApplicationDateRaw VARCHAR(30) NULL,
    ApplicantAgeRaw VARCHAR(30) NULL,
    GenderRaw VARCHAR(30) NULL,
    SmokingStatusRaw VARCHAR(30) NULL,
    DiabetesStatusRaw VARCHAR(30) NULL,
    BMIValueRaw VARCHAR(30) NULL,
    AgeBandRaw VARCHAR(30) NULL,
    BMIBandRaw VARCHAR(30) NULL,
    FaceAmountRaw VARCHAR(30) NULL,
    QuotedRateVersionIDRaw VARCHAR(30) NULL,
    QuotedPremiumRaw VARCHAR(30) NULL,
    StatusRaw VARCHAR(30) NULL,
    LoadRow INT IDENTITY(1,1) NOT NULL
);

BULK INSERT #ApplicationStage FROM '/data/APPLICATION.csv'
WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/application_stage.fmt', TABLOCK, KEEPNULLS);

IF (SELECT COUNT(*) FROM #ApplicationStage) <> 90000
    THROW 51020, 'APPLICATION CSV row count mismatch.', 1;

SET IDENTITY_INSERT dbo.APPLICATION ON;
INSERT dbo.APPLICATION (
    ApplicationID, Customer_CustomerID, ProductID, ApplicationDate, ApplicantAge,
    Gender, SmokingStatus, DiabetesStatus, BMIValue, AgeBand, BMIBand,
    FaceAmount, QuotedRateVersionID, QuotedPremium, Status
)
SELECT
    LoadRow,
    TRY_CONVERT(INT, NULLIF(RTRIM(CustomerIDRaw), '')),
    TRY_CONVERT(INT, NULLIF(RTRIM(ProductIDRaw), '')),
    TRY_CONVERT(DATE, NULLIF(RTRIM(ApplicationDateRaw), '')),
    TRY_CONVERT(INT, NULLIF(RTRIM(ApplicantAgeRaw), '')),
    NULLIF(RTRIM(GenderRaw), ''),
    NULLIF(RTRIM(SmokingStatusRaw), ''),
    NULLIF(RTRIM(DiabetesStatusRaw), ''),
    TRY_CONVERT(NUMERIC(5,2), NULLIF(RTRIM(BMIValueRaw), '')),
    NULLIF(RTRIM(AgeBandRaw), ''),
    NULLIF(RTRIM(BMIBandRaw), ''),
    TRY_CONVERT(NUMERIC(12,2), NULLIF(RTRIM(FaceAmountRaw), '')),
    TRY_CONVERT(INT, NULLIF(RTRIM(QuotedRateVersionIDRaw), '')),
    TRY_CONVERT(NUMERIC(12,2), NULLIF(RTRIM(QuotedPremiumRaw), '')),
    NULLIF(RTRIM(StatusRaw), '')
FROM #ApplicationStage;
SET IDENTITY_INSERT dbo.APPLICATION OFF;
DBCC CHECKIDENT ('dbo.APPLICATION', RESEED, 90000) WITH NO_INFOMSGS;

IF (SELECT COUNT(*) FROM dbo.APPLICATION) <> 90000
   OR (SELECT MIN(ApplicationID) FROM dbo.APPLICATION) <> 1
   OR (SELECT MAX(ApplicationID) FROM dbo.APPLICATION) <> 90000
    THROW 51021, 'APPLICATION identity range mismatch.', 1;

UPDATE dbo.Contract
SET ApplicationID = ContractID
WHERE ContractID BETWEEN 1 AND 60000
  AND ApplicationID IS NULL;

IF (SELECT COUNT(*) FROM dbo.Contract WHERE ApplicationID IS NOT NULL) <> 60000
    THROW 51022, 'Contract application backfill mismatch.', 1;
GO
