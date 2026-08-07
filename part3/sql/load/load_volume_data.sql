-- Jingrui Feng (jf4446) - database systems project part 3 - volume csv bulk loader
-- Local SQL Server volume load. Run in LifeInsuranceP3 with sqlcmd.
-- The generated files contain no quoted fields. In this Linux container,
-- FORMAT='CSV' fails with provider error 7301, so plain BULK INSERT is safe
-- for base tables. Bridge loads use non-XML format files to omit database-
--generated identity columns, bulk into CSV-shaped raw-text staging tables,
--then set explicit 1..N identities from file order. This is set based and
--makes the documented child-key assumptions deterministic.
SET NOCOUNT ON;
GO

BULK INSERT dbo.Customer FROM '/data/Customer.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
BULK INSERT dbo.Product FROM '/data/Product.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
BULK INSERT dbo.BillingAccount FROM '/data/BillingAccount.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
BULK INSERT dbo.Account FROM '/data/Account.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPNULLS);
BULK INSERT dbo.AccountMember FROM '/data/AccountMember.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPNULLS);
BULK INSERT dbo.Relation_3 FROM '/data/Relation_3.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPNULLS);
GO

CREATE TABLE #RateVersionStage (EffectiveDateRaw VARCHAR(30) NULL, ExpiryDateRaw VARCHAR(30) NULL, StatusRaw VARCHAR(30) NULL, CreatedByRunIDRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #RateVersionStage FROM '/data/RATE_VERSION.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/rate_version_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.RATE_VERSION ON;
INSERT dbo.RATE_VERSION (RateVersionID, EffectiveDate, ExpiryDate, Status, CreatedByRunID)
SELECT LoadRow, TRY_CONVERT(DATE, NULLIF(RTRIM(EffectiveDateRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(ExpiryDateRaw), '')), NULLIF(RTRIM(StatusRaw), ''), TRY_CONVERT(INT, NULLIF(RTRIM(CreatedByRunIDRaw), '')) FROM #RateVersionStage;
SET IDENTITY_INSERT dbo.RATE_VERSION OFF;
DBCC CHECKIDENT ('dbo.RATE_VERSION', RESEED, 6) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.RATE_VERSION) <> 6 OR (SELECT MIN(RateVersionID) FROM dbo.RATE_VERSION) <> 1 OR (SELECT MAX(RateVersionID) FROM dbo.RATE_VERSION) <> 6 THROW 51001, 'RATE_VERSION identity range mismatch.', 1;
GO

BULK INSERT dbo.Contract FROM '/data/Contract.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPNULLS);
BULK INSERT dbo.Claim FROM '/data/Claim.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
BULK INSERT dbo.ContractParty FROM '/data/ContractParty.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
BULK INSERT dbo.Invoice FROM '/data/Invoice.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
GO

CREATE TABLE #WellnessProgramStage (ProgramNameRaw VARCHAR(100) NULL, PartnerGymRaw VARCHAR(100) NULL, DiscountMaxPctRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #WellnessProgramStage FROM '/data/WELLNESS_PROGRAM.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/wellness_program_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.WELLNESS_PROGRAM ON;
INSERT dbo.WELLNESS_PROGRAM (WellnessProgramID, ProgramName, PartnerGym, DiscountMaxPct)
SELECT LoadRow, NULLIF(RTRIM(ProgramNameRaw), ''), NULLIF(RTRIM(PartnerGymRaw), ''), TRY_CONVERT(NUMERIC(5,2), NULLIF(RTRIM(DiscountMaxPctRaw), '')) FROM #WellnessProgramStage;
SET IDENTITY_INSERT dbo.WELLNESS_PROGRAM OFF;
DBCC CHECKIDENT ('dbo.WELLNESS_PROGRAM', RESEED, 5) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.WELLNESS_PROGRAM) <> 5 OR (SELECT MIN(WellnessProgramID) FROM dbo.WELLNESS_PROGRAM) <> 1 OR (SELECT MAX(WellnessProgramID) FROM dbo.WELLNESS_PROGRAM) <> 5 THROW 51002, 'WELLNESS_PROGRAM identity range mismatch.', 1;
GO

CREATE TABLE #WellnessEnrollmentStage (ContractIDRaw VARCHAR(30) NULL, WellnessProgramIDRaw VARCHAR(30) NULL, EnrollDateRaw VARCHAR(30) NULL, StatusRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #WellnessEnrollmentStage FROM '/data/WELLNESS_ENROLLMENT.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/wellness_enrollment_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.WELLNESS_ENROLLMENT ON;
INSERT dbo.WELLNESS_ENROLLMENT (EnrollmentID, ContractID, WellnessProgramID, EnrollDate, Status)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(ContractIDRaw), '')), TRY_CONVERT(INT, NULLIF(RTRIM(WellnessProgramIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(EnrollDateRaw), '')), NULLIF(RTRIM(StatusRaw), '') FROM #WellnessEnrollmentStage;
SET IDENTITY_INSERT dbo.WELLNESS_ENROLLMENT OFF;
DBCC CHECKIDENT ('dbo.WELLNESS_ENROLLMENT', RESEED, 24000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.WELLNESS_ENROLLMENT) <> 24000 OR (SELECT MIN(EnrollmentID) FROM dbo.WELLNESS_ENROLLMENT) <> 1 OR (SELECT MAX(EnrollmentID) FROM dbo.WELLNESS_ENROLLMENT) <> 24000 THROW 51003, 'WELLNESS_ENROLLMENT identity range mismatch.', 1;
GO

CREATE TABLE #WellnessActivityStage (EnrollmentIDRaw VARCHAR(30) NULL, ActivityDateRaw VARCHAR(30) NULL, ActivityTypeRaw VARCHAR(40) NULL, VerifiedFlagRaw VARCHAR(10) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #WellnessActivityStage FROM '/data/WELLNESS_ACTIVITY.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/wellness_activity_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.WELLNESS_ACTIVITY ON;
INSERT dbo.WELLNESS_ACTIVITY (ActivityID, EnrollmentID, ActivityDate, ActivityType, VerifiedFlag)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(EnrollmentIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(ActivityDateRaw), '')), NULLIF(RTRIM(ActivityTypeRaw), ''), NULLIF(RTRIM(VerifiedFlagRaw), '') FROM #WellnessActivityStage;
SET IDENTITY_INSERT dbo.WELLNESS_ACTIVITY OFF;
DBCC CHECKIDENT ('dbo.WELLNESS_ACTIVITY', RESEED, 1000000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.WELLNESS_ACTIVITY) <> 1000000 OR (SELECT MIN(ActivityID) FROM dbo.WELLNESS_ACTIVITY) <> 1 OR (SELECT MAX(ActivityID) FROM dbo.WELLNESS_ACTIVITY) <> 1000000 THROW 51004, 'WELLNESS_ACTIVITY identity range mismatch.', 1;
GO

CREATE TABLE #RiskImprovementStage (EnrollmentIDRaw VARCHAR(30) NULL, MeasureDateRaw VARCHAR(30) NULL, MeasureTypeRaw VARCHAR(40) NULL, MeasureValueRaw VARCHAR(30) NULL, BaselineValueRaw VARCHAR(30) NULL, ImprovementPctRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #RiskImprovementStage FROM '/data/RISK_IMPROVEMENT.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/risk_improvement_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.RISK_IMPROVEMENT ON;
INSERT dbo.RISK_IMPROVEMENT (ImprovementID, EnrollmentID, MeasureDate, MeasureType, MeasureValue, BaselineValue, ImprovementPct)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(EnrollmentIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(MeasureDateRaw), '')), NULLIF(RTRIM(MeasureTypeRaw), ''), TRY_CONVERT(NUMERIC(8,2), NULLIF(RTRIM(MeasureValueRaw), '')), TRY_CONVERT(NUMERIC(8,2), NULLIF(RTRIM(BaselineValueRaw), '')), TRY_CONVERT(NUMERIC(5,2), NULLIF(RTRIM(ImprovementPctRaw), '')) FROM #RiskImprovementStage;
SET IDENTITY_INSERT dbo.RISK_IMPROVEMENT OFF;
DBCC CHECKIDENT ('dbo.RISK_IMPROVEMENT', RESEED, 48000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.RISK_IMPROVEMENT) <> 48000 OR (SELECT MIN(ImprovementID) FROM dbo.RISK_IMPROVEMENT) <> 1 OR (SELECT MAX(ImprovementID) FROM dbo.RISK_IMPROVEMENT) <> 48000 THROW 51005, 'RISK_IMPROVEMENT identity range mismatch.', 1;
GO

CREATE TABLE #PolicyRenewalStage (ContractIDRaw VARCHAR(30) NULL, RenewalDateRaw VARCHAR(30) NULL, NewRateVersionIDRaw VARCHAR(30) NULL, WellnessDiscountPctRaw VARCHAR(30) NULL, FinalPremiumRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #PolicyRenewalStage FROM '/data/POLICY_RENEWAL.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/policy_renewal_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.POLICY_RENEWAL ON;
INSERT dbo.POLICY_RENEWAL (RenewalID, ContractID, RenewalDate, NewRateVersionID, WellnessDiscountPct, FinalPremium)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(ContractIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(RenewalDateRaw), '')), TRY_CONVERT(INT, NULLIF(RTRIM(NewRateVersionIDRaw), '')), TRY_CONVERT(NUMERIC(5,2), NULLIF(RTRIM(WellnessDiscountPctRaw), '')), TRY_CONVERT(NUMERIC(12,2), NULLIF(RTRIM(FinalPremiumRaw), '')) FROM #PolicyRenewalStage;
SET IDENTITY_INSERT dbo.POLICY_RENEWAL OFF;
DBCC CHECKIDENT ('dbo.POLICY_RENEWAL', RESEED, 90000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.POLICY_RENEWAL) <> 90000 OR (SELECT MIN(RenewalID) FROM dbo.POLICY_RENEWAL) <> 1 OR (SELECT MAX(RenewalID) FROM dbo.POLICY_RENEWAL) <> 90000 THROW 51006, 'POLICY_RENEWAL identity range mismatch.', 1;
GO
