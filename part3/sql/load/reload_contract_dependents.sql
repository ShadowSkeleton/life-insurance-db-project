-- Jingrui Feng (jf4446) - database systems project part 3 - contract dependent reload
-- Rebuild the Contract dependency branch after correcting the empty-date load
-- behavior. SQL Server cannot TRUNCATE a table referenced by a foreign key,
-- even when child tables are empty, so the five constraints referencing
-- Contract are dropped only for the Contract truncate and recreated unchanged.
-- The bridge CSV format files must be available in /tmp/dbsys-p3-load.
SET NOCOUNT ON;
GO

-- Delete rather than truncate children because some are themselves referenced
-- by empty inherited tables. Reseeding restores the documented CSV identities.
DELETE FROM dbo.WELLNESS_ACTIVITY;
DELETE FROM dbo.RISK_IMPROVEMENT;
DELETE FROM dbo.POLICY_RENEWAL;
DELETE FROM dbo.WELLNESS_ENROLLMENT;
DELETE FROM dbo.Claim;
DELETE FROM dbo.ContractParty;
GO

ALTER TABLE dbo.Claim DROP CONSTRAINT Claim_Contract_FK;
ALTER TABLE dbo.ContractBenefit DROP CONSTRAINT ContractBenefit_Contract_FK;
ALTER TABLE dbo.ContractParty DROP CONSTRAINT ContractParty_Contract_FK;
ALTER TABLE dbo.WELLNESS_ENROLLMENT DROP CONSTRAINT WENROLL_CONTRACT_FK;
ALTER TABLE dbo.POLICY_RENEWAL DROP CONSTRAINT PRENEW_CONTRACT_FK;
TRUNCATE TABLE dbo.Contract;
GO

BULK INSERT dbo.Contract FROM '/data/Contract.csv'
WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK, KEEPNULLS);
GO

ALTER TABLE dbo.Claim ADD CONSTRAINT Claim_Contract_FK FOREIGN KEY (Contract_ContractID) REFERENCES dbo.Contract (ContractID);
ALTER TABLE dbo.ContractBenefit ADD CONSTRAINT ContractBenefit_Contract_FK FOREIGN KEY (Contract_ContractID) REFERENCES dbo.Contract (ContractID);
ALTER TABLE dbo.ContractParty ADD CONSTRAINT ContractParty_Contract_FK FOREIGN KEY (Contract_ContractID) REFERENCES dbo.Contract (ContractID);
ALTER TABLE dbo.WELLNESS_ENROLLMENT ADD CONSTRAINT WENROLL_CONTRACT_FK FOREIGN KEY (ContractID) REFERENCES dbo.Contract (ContractID);
ALTER TABLE dbo.POLICY_RENEWAL ADD CONSTRAINT PRENEW_CONTRACT_FK FOREIGN KEY (ContractID) REFERENCES dbo.Contract (ContractID);
GO

BULK INSERT dbo.Claim FROM '/data/Claim.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
BULK INSERT dbo.ContractParty FROM '/data/ContractParty.csv' WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
GO

CREATE TABLE #WellnessEnrollmentReloadStage (ContractIDRaw VARCHAR(30) NULL, WellnessProgramIDRaw VARCHAR(30) NULL, EnrollDateRaw VARCHAR(30) NULL, StatusRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #WellnessEnrollmentReloadStage FROM '/data/WELLNESS_ENROLLMENT.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/wellness_enrollment_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.WELLNESS_ENROLLMENT ON;
INSERT dbo.WELLNESS_ENROLLMENT (EnrollmentID, ContractID, WellnessProgramID, EnrollDate, Status)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(ContractIDRaw), '')), TRY_CONVERT(INT, NULLIF(RTRIM(WellnessProgramIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(EnrollDateRaw), '')), NULLIF(RTRIM(StatusRaw), '') FROM #WellnessEnrollmentReloadStage;
SET IDENTITY_INSERT dbo.WELLNESS_ENROLLMENT OFF;
DBCC CHECKIDENT ('dbo.WELLNESS_ENROLLMENT', RESEED, 24000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.WELLNESS_ENROLLMENT) <> 24000 OR (SELECT MIN(EnrollmentID) FROM dbo.WELLNESS_ENROLLMENT) <> 1 OR (SELECT MAX(EnrollmentID) FROM dbo.WELLNESS_ENROLLMENT) <> 24000 THROW 51013, 'WELLNESS_ENROLLMENT identity range mismatch.', 1;
GO

CREATE TABLE #WellnessActivityReloadStage (EnrollmentIDRaw VARCHAR(30) NULL, ActivityDateRaw VARCHAR(30) NULL, ActivityTypeRaw VARCHAR(40) NULL, VerifiedFlagRaw VARCHAR(10) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #WellnessActivityReloadStage FROM '/data/WELLNESS_ACTIVITY.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/wellness_activity_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.WELLNESS_ACTIVITY ON;
INSERT dbo.WELLNESS_ACTIVITY (ActivityID, EnrollmentID, ActivityDate, ActivityType, VerifiedFlag)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(EnrollmentIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(ActivityDateRaw), '')), NULLIF(RTRIM(ActivityTypeRaw), ''), NULLIF(RTRIM(VerifiedFlagRaw), '') FROM #WellnessActivityReloadStage;
SET IDENTITY_INSERT dbo.WELLNESS_ACTIVITY OFF;
DBCC CHECKIDENT ('dbo.WELLNESS_ACTIVITY', RESEED, 1000000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.WELLNESS_ACTIVITY) <> 1000000 OR (SELECT MIN(ActivityID) FROM dbo.WELLNESS_ACTIVITY) <> 1 OR (SELECT MAX(ActivityID) FROM dbo.WELLNESS_ACTIVITY) <> 1000000 THROW 51014, 'WELLNESS_ACTIVITY identity range mismatch.', 1;
GO

CREATE TABLE #RiskImprovementReloadStage (EnrollmentIDRaw VARCHAR(30) NULL, MeasureDateRaw VARCHAR(30) NULL, MeasureTypeRaw VARCHAR(40) NULL, MeasureValueRaw VARCHAR(30) NULL, BaselineValueRaw VARCHAR(30) NULL, ImprovementPctRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #RiskImprovementReloadStage FROM '/data/RISK_IMPROVEMENT.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/risk_improvement_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.RISK_IMPROVEMENT ON;
INSERT dbo.RISK_IMPROVEMENT (ImprovementID, EnrollmentID, MeasureDate, MeasureType, MeasureValue, BaselineValue, ImprovementPct)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(EnrollmentIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(MeasureDateRaw), '')), NULLIF(RTRIM(MeasureTypeRaw), ''), TRY_CONVERT(NUMERIC(8,2), NULLIF(RTRIM(MeasureValueRaw), '')), TRY_CONVERT(NUMERIC(8,2), NULLIF(RTRIM(BaselineValueRaw), '')), TRY_CONVERT(NUMERIC(5,2), NULLIF(RTRIM(ImprovementPctRaw), '')) FROM #RiskImprovementReloadStage;
SET IDENTITY_INSERT dbo.RISK_IMPROVEMENT OFF;
DBCC CHECKIDENT ('dbo.RISK_IMPROVEMENT', RESEED, 48000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.RISK_IMPROVEMENT) <> 48000 OR (SELECT MIN(ImprovementID) FROM dbo.RISK_IMPROVEMENT) <> 1 OR (SELECT MAX(ImprovementID) FROM dbo.RISK_IMPROVEMENT) <> 48000 THROW 51015, 'RISK_IMPROVEMENT identity range mismatch.', 1;
GO

CREATE TABLE #PolicyRenewalReloadStage (ContractIDRaw VARCHAR(30) NULL, RenewalDateRaw VARCHAR(30) NULL, NewRateVersionIDRaw VARCHAR(30) NULL, WellnessDiscountPctRaw VARCHAR(30) NULL, FinalPremiumRaw VARCHAR(30) NULL, LoadRow INT IDENTITY(1,1) NOT NULL);
BULK INSERT #PolicyRenewalReloadStage FROM '/data/POLICY_RENEWAL.csv' WITH (FIRSTROW=2, FORMATFILE='/tmp/dbsys-p3-load/policy_renewal_stage.fmt', TABLOCK);
SET IDENTITY_INSERT dbo.POLICY_RENEWAL ON;
INSERT dbo.POLICY_RENEWAL (RenewalID, ContractID, RenewalDate, NewRateVersionID, WellnessDiscountPct, FinalPremium)
SELECT LoadRow, TRY_CONVERT(INT, NULLIF(RTRIM(ContractIDRaw), '')), TRY_CONVERT(DATE, NULLIF(RTRIM(RenewalDateRaw), '')), TRY_CONVERT(INT, NULLIF(RTRIM(NewRateVersionIDRaw), '')), TRY_CONVERT(NUMERIC(5,2), NULLIF(RTRIM(WellnessDiscountPctRaw), '')), TRY_CONVERT(NUMERIC(12,2), NULLIF(RTRIM(FinalPremiumRaw), '')) FROM #PolicyRenewalReloadStage;
SET IDENTITY_INSERT dbo.POLICY_RENEWAL OFF;
DBCC CHECKIDENT ('dbo.POLICY_RENEWAL', RESEED, 90000) WITH NO_INFOMSGS;
IF (SELECT COUNT(*) FROM dbo.POLICY_RENEWAL) <> 90000 OR (SELECT MIN(RenewalID) FROM dbo.POLICY_RENEWAL) <> 1 OR (SELECT MAX(RenewalID) FROM dbo.POLICY_RENEWAL) <> 90000 THROW 51016, 'POLICY_RENEWAL identity range mismatch.', 1;
GO
