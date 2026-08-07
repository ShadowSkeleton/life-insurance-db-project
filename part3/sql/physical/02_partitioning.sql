-- Jingrui Feng (jf4446) - database systems project part 3 - local yearly partitioning
-- Increment 2: local-only filegroup placement and yearly partitioning.
-- Azure SQL Database single databases expose PRIMARY only, so the six physical
-- filegroups below are a local SQL Server demonstration and are intentionally
-- excluded from the later Azure deployment script.  Each file is distinct in
-- the Linux container's SQL Server data directory.
--
-- Current keys before this script: WELLNESS_ACTIVITY_PK clustered(ActivityID)
-- and Invoice_PK clustered(InvoiceID).  SQL Server requires a partitioned
-- unique clustered key to contain the partitioning column.  The script keeps
-- each same single-column primary key unique by recreating it NONCLUSTERED,
-- then creates an aligned clustered index (date, ID).  No child FK references
-- either key, so the change preserves all key and FK semantics.
USE LifeInsuranceP3;
GO

IF NOT EXISTS (SELECT 1 FROM sys.filegroups WHERE name = N'P3_FG_2021') ALTER DATABASE LifeInsuranceP3 ADD FILEGROUP P3_FG_2021;
IF NOT EXISTS (SELECT 1 FROM sys.filegroups WHERE name = N'P3_FG_2022') ALTER DATABASE LifeInsuranceP3 ADD FILEGROUP P3_FG_2022;
IF NOT EXISTS (SELECT 1 FROM sys.filegroups WHERE name = N'P3_FG_2023') ALTER DATABASE LifeInsuranceP3 ADD FILEGROUP P3_FG_2023;
IF NOT EXISTS (SELECT 1 FROM sys.filegroups WHERE name = N'P3_FG_2024') ALTER DATABASE LifeInsuranceP3 ADD FILEGROUP P3_FG_2024;
IF NOT EXISTS (SELECT 1 FROM sys.filegroups WHERE name = N'P3_FG_2025') ALTER DATABASE LifeInsuranceP3 ADD FILEGROUP P3_FG_2025;
IF NOT EXISTS (SELECT 1 FROM sys.filegroups WHERE name = N'P3_FG_2026') ALTER DATABASE LifeInsuranceP3 ADD FILEGROUP P3_FG_2026;
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_files WHERE name = N'LifeInsuranceP3_P3_2021') ALTER DATABASE LifeInsuranceP3 ADD FILE (NAME = N'LifeInsuranceP3_P3_2021', FILENAME = N'/var/opt/mssql/data/LifeInsuranceP3_P3_2021.ndf', SIZE = 32MB, FILEGROWTH = 32MB) TO FILEGROUP P3_FG_2021;
IF NOT EXISTS (SELECT 1 FROM sys.database_files WHERE name = N'LifeInsuranceP3_P3_2022') ALTER DATABASE LifeInsuranceP3 ADD FILE (NAME = N'LifeInsuranceP3_P3_2022', FILENAME = N'/var/opt/mssql/data/LifeInsuranceP3_P3_2022.ndf', SIZE = 32MB, FILEGROWTH = 32MB) TO FILEGROUP P3_FG_2022;
IF NOT EXISTS (SELECT 1 FROM sys.database_files WHERE name = N'LifeInsuranceP3_P3_2023') ALTER DATABASE LifeInsuranceP3 ADD FILE (NAME = N'LifeInsuranceP3_P3_2023', FILENAME = N'/var/opt/mssql/data/LifeInsuranceP3_P3_2023.ndf', SIZE = 32MB, FILEGROWTH = 32MB) TO FILEGROUP P3_FG_2023;
IF NOT EXISTS (SELECT 1 FROM sys.database_files WHERE name = N'LifeInsuranceP3_P3_2024') ALTER DATABASE LifeInsuranceP3 ADD FILE (NAME = N'LifeInsuranceP3_P3_2024', FILENAME = N'/var/opt/mssql/data/LifeInsuranceP3_P3_2024.ndf', SIZE = 32MB, FILEGROWTH = 32MB) TO FILEGROUP P3_FG_2024;
IF NOT EXISTS (SELECT 1 FROM sys.database_files WHERE name = N'LifeInsuranceP3_P3_2025') ALTER DATABASE LifeInsuranceP3 ADD FILE (NAME = N'LifeInsuranceP3_P3_2025', FILENAME = N'/var/opt/mssql/data/LifeInsuranceP3_P3_2025.ndf', SIZE = 32MB, FILEGROWTH = 32MB) TO FILEGROUP P3_FG_2025;
IF NOT EXISTS (SELECT 1 FROM sys.database_files WHERE name = N'LifeInsuranceP3_P3_2026') ALTER DATABASE LifeInsuranceP3 ADD FILE (NAME = N'LifeInsuranceP3_P3_2026', FILENAME = N'/var/opt/mssql/data/LifeInsuranceP3_P3_2026.ndf', SIZE = 32MB, FILEGROWTH = 32MB) TO FILEGROUP P3_FG_2026;
GO

-- RANGE RIGHT: the six partitions represent 2021, 2022, 2023, 2024, 2025,
-- and 2026 onward.  The data's five-plus-year range occupies multiple slices.
IF NOT EXISTS (SELECT 1 FROM sys.partition_functions WHERE name = N'pf_P3_YearlyDate')
    EXEC(N'CREATE PARTITION FUNCTION pf_P3_YearlyDate (DATE) AS RANGE RIGHT FOR VALUES (''2022-01-01'', ''2023-01-01'', ''2024-01-01'', ''2025-01-01'', ''2026-01-01'');');
GO
IF NOT EXISTS (SELECT 1 FROM sys.partition_schemes WHERE name = N'ps_P3_WELLNESS_ACTIVITY')
    EXEC(N'CREATE PARTITION SCHEME ps_P3_WELLNESS_ACTIVITY AS PARTITION pf_P3_YearlyDate TO (P3_FG_2021, P3_FG_2022, P3_FG_2023, P3_FG_2024, P3_FG_2025, P3_FG_2026);');
IF NOT EXISTS (SELECT 1 FROM sys.partition_schemes WHERE name = N'ps_P3_Invoice')
    EXEC(N'CREATE PARTITION SCHEME ps_P3_Invoice AS PARTITION pf_P3_YearlyDate TO (P3_FG_2021, P3_FG_2022, P3_FG_2023, P3_FG_2024, P3_FG_2025, P3_FG_2026);');
GO

-- Preserve ActivityID's unique primary-key semantics while releasing the
-- clustered position for the partition-aligned physical access path.
ALTER TABLE dbo.WELLNESS_ACTIVITY DROP CONSTRAINT WELLNESS_ACTIVITY_PK;
ALTER TABLE dbo.WELLNESS_ACTIVITY ADD CONSTRAINT WELLNESS_ACTIVITY_PK
    PRIMARY KEY NONCLUSTERED (ActivityID) WITH (FILLFACTOR = 80) ON [PRIMARY];
CREATE CLUSTERED INDEX CIX_WELLNESS_ACTIVITY_ActivityDate_ActivityID
ON dbo.WELLNESS_ACTIVITY (ActivityDate, ActivityID)
WITH (FILLFACTOR = 80)
ON ps_P3_WELLNESS_ACTIVITY (ActivityDate);
GO

-- Align the Increment 1 wellness access path so date predicates can eliminate
-- partitions even when EnrollmentID remains its leading seek key.
DROP INDEX IX_WELLNESS_ACTIVITY_EnrollmentID_ActivityDate ON dbo.WELLNESS_ACTIVITY;
CREATE NONCLUSTERED INDEX IX_WELLNESS_ACTIVITY_EnrollmentID_ActivityDate
ON dbo.WELLNESS_ACTIVITY (EnrollmentID, ActivityDate)
INCLUDE (VerifiedFlag)
WITH (FILLFACTOR = 80)
ON ps_P3_WELLNESS_ACTIVITY (ActivityDate);
GO

-- Preserve InvoiceID's unique primary-key semantics while releasing the
-- clustered position for the partition-aligned RunDate access path.
ALTER TABLE dbo.Invoice DROP CONSTRAINT Invoice_PK;
ALTER TABLE dbo.Invoice ADD CONSTRAINT Invoice_PK
    PRIMARY KEY NONCLUSTERED (InvoiceID) WITH (FILLFACTOR = 80) ON [PRIMARY];
CREATE CLUSTERED INDEX CIX_Invoice_RunDate_InvoiceID
ON dbo.Invoice (RunDate, InvoiceID)
WITH (FILLFACTOR = 80)
ON ps_P3_Invoice (RunDate);
GO

-- Align the Increment 1 invoice foreign-key access path.  Q2/Q2b have no
-- RunDate predicate, so they may legitimately touch all invoice partitions.
DROP INDEX IX_Invoice_BillingAccount_BillingAccountID ON dbo.Invoice;
CREATE NONCLUSTERED INDEX IX_Invoice_BillingAccount_BillingAccountID
ON dbo.Invoice (BillingAccount_BillingAccountID)
WITH (FILLFACTOR = 80)
ON ps_P3_Invoice (RunDate);
GO
