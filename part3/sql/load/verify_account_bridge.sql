-- Jingrui Feng (jf4446) - database systems project part 3 - account bridge verifier
SET NOCOUNT ON;
GO

-- Each customer must resolve to exactly one BillingAccount through the declared path.
;WITH CustomerReachability AS (
    SELECT c.CustomerID, COUNT(DISTINCT r.BillingAccount_BillingAccountID) AS BillingAccountCount
    FROM dbo.Customer AS c
    LEFT JOIN dbo.AccountMember AS am ON am.Customer_CustomerID = c.CustomerID
    LEFT JOIN dbo.Account AS a ON a.AccountID = am.Account_AccountID
    LEFT JOIN dbo.Relation_3 AS r ON r.Account_AccountID = a.AccountID
    GROUP BY c.CustomerID
)
SELECT SUM(CASE WHEN BillingAccountCount = 1 THEN 1 ELSE 0 END) AS ExactlyOneReachableBillingAccount,
       SUM(CASE WHEN BillingAccountCount = 0 THEN 1 ELSE 0 END) AS NoReachableBillingAccount,
       SUM(CASE WHEN BillingAccountCount > 1 THEN 1 ELSE 0 END) AS MultipleReachableBillingAccounts
FROM CustomerReachability;
GO

-- Contract-to-invoice traversal has no direct FK; deduplicate the actual pairs.
;WITH ReachablePairs AS (
    SELECT DISTINCT c.ContractID, i.InvoiceID, c.EffectiveDate, i.RunDate
    FROM dbo.Contract AS c
    JOIN dbo.ContractParty AS cp ON cp.Contract_ContractID = c.ContractID
    JOIN dbo.Customer AS cu ON cu.CustomerID = cp.Customer_CustomerID
    JOIN dbo.AccountMember AS am ON am.Customer_CustomerID = cu.CustomerID
    JOIN dbo.Account AS a ON a.AccountID = am.Account_AccountID
    JOIN dbo.Relation_3 AS r ON r.Account_AccountID = a.AccountID
    JOIN dbo.BillingAccount AS ba ON ba.BillingAccountID = r.BillingAccount_BillingAccountID
    JOIN dbo.Invoice AS i ON i.BillingAccount_BillingAccountID = ba.BillingAccountID
)
SELECT COUNT_BIG(*) AS DistinctReachableContractInvoicePairs,
       COUNT(DISTINCT ContractID) AS ContractsWithAtLeastOneReachableInvoice,
       SUM(CASE WHEN RunDate < EffectiveDate THEN 1 ELSE 0 END) AS InvoiceRunDateBeforeContractEffectiveDate,
       CAST(100.0 * SUM(CASE WHEN RunDate < EffectiveDate THEN 1 ELSE 0 END) / NULLIF(COUNT_BIG(*), 0) AS DECIMAL(8,4)) AS PercentInvoiceRunDateBeforeEffective
FROM ReachablePairs;
GO

-- Dynamic row-count inventory covers every local user table (including staging).
CREATE TABLE #RowCounts (TableName SYSNAME NOT NULL, LoadedRows BIGINT NOT NULL);
DECLARE @row_count_sql NVARCHAR(MAX) = N'';
SELECT @row_count_sql = STRING_AGG(
    CAST(N'INSERT #RowCounts SELECT N''' + REPLACE(t.name, N'''', N'''''') + N''', COUNT_BIG(*) FROM ' + QUOTENAME(s.name) + N'.' + QUOTENAME(t.name) + N';' AS NVARCHAR(MAX)),
    CHAR(10))
FROM sys.tables AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
WHERE t.is_ms_shipped = 0;
EXEC sys.sp_executesql @row_count_sql;
SELECT TableName, LoadedRows FROM #RowCounts ORDER BY TableName;
GO

CREATE TABLE #ForeignKeyVerification (
    ForeignKeyName SYSNAME NOT NULL,
    ChildTable SYSNAME NOT NULL,
    ParentTable SYSNAME NOT NULL,
    OrphanCount BIGINT NOT NULL
);
DECLARE @fk_sql NVARCHAR(MAX) = N'';
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
SELECT @fk_sql = STRING_AGG(CAST(N'INSERT #ForeignKeyVerification SELECT N''' + REPLACE(ForeignKeyName, N'''', N'''''') + N''', N''' + REPLACE(ChildTable, N'''', N'''''') + N''', N''' + REPLACE(ParentTable, N'''', N'''''') + N''', COUNT_BIG(*) FROM ' + ChildObject + N' AS c LEFT JOIN ' + ParentObject + N' AS p ON ' + JoinPredicate + N' WHERE ' + NonNullPredicate + N' AND p.' + FirstParentColumn + N' IS NULL;' AS NVARCHAR(MAX)), CHAR(10))
FROM ForeignKeySql;
EXEC sys.sp_executesql @fk_sql;
SELECT ForeignKeyName, ChildTable, ParentTable, OrphanCount
FROM #ForeignKeyVerification
ORDER BY ForeignKeyName;
GO
