-- Jingrui Feng (jf4446) - database systems project part 3 - local load verifier
SET NOCOUNT ON;
GO

SELECT 'Customer' AS TableName, COUNT_BIG(*) AS LoadedRows FROM dbo.Customer UNION ALL
SELECT 'Product', COUNT_BIG(*) FROM dbo.Product UNION ALL
SELECT 'BillingAccount', COUNT_BIG(*) FROM dbo.BillingAccount UNION ALL
SELECT 'RATE_VERSION', COUNT_BIG(*) FROM dbo.RATE_VERSION UNION ALL
SELECT 'Contract', COUNT_BIG(*) FROM dbo.Contract UNION ALL
SELECT 'Claim', COUNT_BIG(*) FROM dbo.Claim UNION ALL
SELECT 'ContractParty', COUNT_BIG(*) FROM dbo.ContractParty UNION ALL
SELECT 'Invoice', COUNT_BIG(*) FROM dbo.Invoice UNION ALL
SELECT 'WELLNESS_PROGRAM', COUNT_BIG(*) FROM dbo.WELLNESS_PROGRAM UNION ALL
SELECT 'WELLNESS_ENROLLMENT', COUNT_BIG(*) FROM dbo.WELLNESS_ENROLLMENT UNION ALL
SELECT 'WELLNESS_ACTIVITY', COUNT_BIG(*) FROM dbo.WELLNESS_ACTIVITY UNION ALL
SELECT 'RISK_IMPROVEMENT', COUNT_BIG(*) FROM dbo.RISK_IMPROVEMENT UNION ALL
SELECT 'POLICY_RENEWAL', COUNT_BIG(*) FROM dbo.POLICY_RENEWAL;
GO

SELECT COUNT(DISTINCT IssuedRateVersionID) AS DistinctIssuedRateVersions,
       MIN(IssuedRateVersionID) AS MinimumIssuedRateVersion,
       MAX(IssuedRateVersionID) AS MaximumIssuedRateVersion
FROM dbo.Contract;
SELECT MIN(EnrollmentID) AS MinimumEnrollmentID, MAX(EnrollmentID) AS MaximumEnrollmentID,
       COUNT_BIG(*) AS ActivityRows
FROM dbo.WELLNESS_ACTIVITY;
GO

SELECT 'Customer.CustDOB' AS DateColumn, MIN(CustDOB) AS MinimumDate, MAX(CustDOB) AS MaximumDate FROM dbo.Customer UNION ALL
SELECT 'Customer.StartDate', MIN(StartDate), MAX(StartDate) FROM dbo.Customer UNION ALL
SELECT 'Customer.EndDate', MIN(EndDate), MAX(EndDate) FROM dbo.Customer UNION ALL
SELECT 'RATE_VERSION.EffectiveDate', MIN(EffectiveDate), MAX(EffectiveDate) FROM dbo.RATE_VERSION UNION ALL
SELECT 'RATE_VERSION.ExpiryDate', MIN(ExpiryDate), MAX(ExpiryDate) FROM dbo.RATE_VERSION UNION ALL
SELECT 'Contract.PayUpDate', MIN(PayUpDate), MAX(PayUpDate) FROM dbo.Contract UNION ALL
SELECT 'Contract.EffectiveDate', MIN(EffectiveDate), MAX(EffectiveDate) FROM dbo.Contract UNION ALL
SELECT 'Contract.ExpiryDate', MIN(ExpiryDate), MAX(ExpiryDate) FROM dbo.Contract UNION ALL
SELECT 'ContractParty.CustDOB', MIN(CustDOB), MAX(CustDOB) FROM dbo.ContractParty UNION ALL
SELECT 'ContractParty.StartDate', MIN(StartDate), MAX(StartDate) FROM dbo.ContractParty UNION ALL
SELECT 'ContractParty.EndDate', MIN(EndDate), MAX(EndDate) FROM dbo.ContractParty UNION ALL
SELECT 'Claim.ClaimDate', MIN(ClaimDate), MAX(ClaimDate) FROM dbo.Claim UNION ALL
SELECT 'Claim.SettlementDate', MIN(SettlementDate), MAX(SettlementDate) FROM dbo.Claim UNION ALL
SELECT 'Claim.WellnessEligibilityDate', MIN(WellnessEligibilityDate), MAX(WellnessEligibilityDate) FROM dbo.Claim UNION ALL
SELECT 'Invoice.PaidDate', MIN(PaidDate), MAX(PaidDate) FROM dbo.Invoice UNION ALL
SELECT 'Invoice.DueDate', MIN(DueDate), MAX(DueDate) FROM dbo.Invoice UNION ALL
SELECT 'Invoice.RunDate', MIN(RunDate), MAX(RunDate) FROM dbo.Invoice UNION ALL
SELECT 'Invoice.PaymentDate', MIN(PaymentDate), MAX(PaymentDate) FROM dbo.Invoice UNION ALL
SELECT 'WELLNESS_ENROLLMENT.EnrollDate', MIN(EnrollDate), MAX(EnrollDate) FROM dbo.WELLNESS_ENROLLMENT UNION ALL
SELECT 'WELLNESS_ACTIVITY.ActivityDate', MIN(ActivityDate), MAX(ActivityDate) FROM dbo.WELLNESS_ACTIVITY UNION ALL
SELECT 'RISK_IMPROVEMENT.MeasureDate', MIN(MeasureDate), MAX(MeasureDate) FROM dbo.RISK_IMPROVEMENT UNION ALL
SELECT 'POLICY_RENEWAL.RenewalDate', MIN(RenewalDate), MAX(RenewalDate) FROM dbo.POLICY_RENEWAL;
GO

CREATE TABLE #ForeignKeyVerification (
    ForeignKeyName SYSNAME NOT NULL,
    ChildTable SYSNAME NOT NULL,
    ParentTable SYSNAME NOT NULL,
    OrphanCount BIGINT NOT NULL
);
DECLARE @sql NVARCHAR(MAX) = N'';
;WITH ForeignKeyParts AS (
    SELECT fk.object_id, fk.name AS ForeignKeyName,
           QUOTENAME(OBJECT_SCHEMA_NAME(fk.parent_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(fk.parent_object_id)) AS ChildObject,
           QUOTENAME(OBJECT_SCHEMA_NAME(fk.referenced_object_id)) + N'.' + QUOTENAME(OBJECT_NAME(fk.referenced_object_id)) AS ParentObject,
           OBJECT_NAME(fk.parent_object_id) AS ChildTable,
           OBJECT_NAME(fk.referenced_object_id) AS ParentTable,
           fkc.constraint_column_id,
           QUOTENAME(COL_NAME(fkc.parent_object_id, fkc.parent_column_id)) AS ChildColumn,
           QUOTENAME(COL_NAME(fkc.referenced_object_id, fkc.referenced_column_id)) AS ParentColumn
    FROM sys.foreign_keys AS fk
    JOIN sys.foreign_key_columns AS fkc ON fkc.constraint_object_id = fk.object_id
), ForeignKeySql AS (
    SELECT object_id, ForeignKeyName, ChildObject, ParentObject, ChildTable, ParentTable,
           STRING_AGG(N'c.' + ChildColumn + N' = p.' + ParentColumn, N' AND ') WITHIN GROUP (ORDER BY constraint_column_id) AS JoinPredicate,
           STRING_AGG(N'c.' + ChildColumn + N' IS NOT NULL', N' AND ') WITHIN GROUP (ORDER BY constraint_column_id) AS NonNullPredicate,
           MIN(ParentColumn) AS FirstParentColumn
    FROM ForeignKeyParts
    GROUP BY object_id, ForeignKeyName, ChildObject, ParentObject, ChildTable, ParentTable
)
SELECT @sql = STRING_AGG(CAST(N'INSERT #ForeignKeyVerification SELECT N''' + REPLACE(ForeignKeyName, N'''', N'''''') + N''', N''' + REPLACE(ChildTable, N'''', N'''''') + N''', N''' + REPLACE(ParentTable, N'''', N'''''') + N''', COUNT_BIG(*) FROM ' + ChildObject + N' AS c LEFT JOIN ' + ParentObject + N' AS p ON ' + JoinPredicate + N' WHERE ' + NonNullPredicate + N' AND p.' + FirstParentColumn + N' IS NULL;' AS NVARCHAR(MAX)), CHAR(10))
FROM ForeignKeySql;
EXEC sys.sp_executesql @sql;
SELECT ForeignKeyName, ChildTable, ParentTable, OrphanCount
FROM #ForeignKeyVerification
ORDER BY ForeignKeyName;
GO
