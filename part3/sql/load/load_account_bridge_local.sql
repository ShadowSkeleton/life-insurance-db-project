-- Jingrui Feng (jf4446) - database systems project part 3 - account billing bridge loader
-- Populate the existing Account billing traversal bridge in LifeInsuranceP3.
-- All three tables use supplied, non-IDENTITY keys.  The source CSVs are
-- CRLF-delimited and include headers; KEEPNULLS preserves intentional NULLs.
SET NOCOUNT ON;
GO

IF (SELECT COUNT(*) FROM dbo.Account) <> 0
    THROW 51020, 'Account must be empty before this one-time bridge load.', 1;
IF (SELECT COUNT(*) FROM dbo.AccountMember) <> 0
    THROW 51021, 'AccountMember must be empty before this one-time bridge load.', 1;
IF (SELECT COUNT(*) FROM dbo.Relation_3) <> 0
    THROW 51022, 'Relation_3 must be empty before this one-time bridge load.', 1;
GO

-- Account has no foreign key.  It must precede both dependent tables.
BULK INSERT dbo.Account FROM '/data/Account.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0d0a', TABLOCK, KEEPNULLS);
GO

IF (SELECT COUNT(*) FROM dbo.Account) <> 40000
   OR (SELECT MIN(AccountID) FROM dbo.Account) <> 1
   OR (SELECT MAX(AccountID) FROM dbo.Account) <> 40000
    THROW 51023, 'Account key range mismatch; do not load dependent bridge tables.', 1;
GO

-- AccountMember depends on Account and the already-loaded Customer table.
BULK INSERT dbo.AccountMember FROM '/data/AccountMember.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0d0a', TABLOCK, KEEPNULLS);
GO

IF (SELECT COUNT(*) FROM dbo.AccountMember) <> 50000
   OR (SELECT MIN(AccountMemberID) FROM dbo.AccountMember) <> 1
   OR (SELECT MAX(AccountMemberID) FROM dbo.AccountMember) <> 50000
    THROW 51024, 'AccountMember key range mismatch.', 1;
GO

-- Relation_3 depends on Account and the already-loaded BillingAccount table.
BULK INSERT dbo.Relation_3 FROM '/data/Relation_3.csv'
WITH (FIRSTROW = 2, FIELDTERMINATOR = ',', ROWTERMINATOR = '0x0d0a', TABLOCK, KEEPNULLS);
GO

IF (SELECT COUNT(*) FROM dbo.Relation_3) <> 40000
   OR (SELECT MIN(Account_AccountID) FROM dbo.Relation_3) <> 1
   OR (SELECT MAX(Account_AccountID) FROM dbo.Relation_3) <> 40000
    THROW 51025, 'Relation_3 Account range mismatch.', 1;
GO
