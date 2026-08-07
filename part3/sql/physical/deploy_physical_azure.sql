-- Jingrui Feng (jf4446) - database systems project part 3 - azure physical design deployment
-- Run in the target database after the inherited schema and Part 3 amendments.
-- Azure SQL single databases expose PRIMARY only: this script preserves the
-- yearly partition function and scheme but omits local filegroups/files and
-- maps every partition to PRIMARY.

CREATE NONCLUSTERED INDEX IX_ContractParty_Customer_CustomerID
ON dbo.ContractParty (Customer_CustomerID) INCLUDE (Contract_ContractID)
WITH (FILLFACTOR = 100);
CREATE NONCLUSTERED INDEX IX_Invoice_BillingAccount_BillingAccountID
ON dbo.Invoice (BillingAccount_BillingAccountID) WITH (FILLFACTOR = 80);
CREATE NONCLUSTERED INDEX IX_WELLNESS_ACTIVITY_EnrollmentID_ActivityDate
ON dbo.WELLNESS_ACTIVITY (EnrollmentID, ActivityDate) INCLUDE (VerifiedFlag)
WITH (FILLFACTOR = 80);
CREATE NONCLUSTERED INDEX IX_Contract_IssuedRateVersionID
ON dbo.Contract (IssuedRateVersionID) WITH (FILLFACTOR = 80);
CREATE NONCLUSTERED INDEX IX_POLICY_RENEWAL_RenewalDate
ON dbo.POLICY_RENEWAL (RenewalDate) WITH (FILLFACTOR = 80);
CREATE NONCLUSTERED INDEX IX_Contract_ActivityStatus
ON dbo.Contract (ActivityStatus) WITH (FILLFACTOR = 80);
GO

-- Increment 2 partitions, retained on PRIMARY for Azure portability.
CREATE PARTITION FUNCTION pf_P3_YearlyDate (DATE)
AS RANGE RIGHT FOR VALUES ('2022-01-01', '2023-01-01', '2024-01-01', '2025-01-01', '2026-01-01');
CREATE PARTITION SCHEME ps_P3_WELLNESS_ACTIVITY
AS PARTITION pf_P3_YearlyDate TO ([PRIMARY], [PRIMARY], [PRIMARY], [PRIMARY], [PRIMARY], [PRIMARY]);
CREATE PARTITION SCHEME ps_P3_Invoice
AS PARTITION pf_P3_YearlyDate TO ([PRIMARY], [PRIMARY], [PRIMARY], [PRIMARY], [PRIMARY], [PRIMARY]);
GO

ALTER TABLE dbo.WELLNESS_ACTIVITY DROP CONSTRAINT WELLNESS_ACTIVITY_PK;
ALTER TABLE dbo.WELLNESS_ACTIVITY ADD CONSTRAINT WELLNESS_ACTIVITY_PK
    PRIMARY KEY NONCLUSTERED (ActivityID) WITH (FILLFACTOR = 80) ON [PRIMARY];
CREATE CLUSTERED INDEX CIX_WELLNESS_ACTIVITY_ActivityDate_ActivityID
ON dbo.WELLNESS_ACTIVITY (ActivityDate, ActivityID)
WITH (FILLFACTOR = 80) ON ps_P3_WELLNESS_ACTIVITY (ActivityDate);
DROP INDEX IX_WELLNESS_ACTIVITY_EnrollmentID_ActivityDate ON dbo.WELLNESS_ACTIVITY;
CREATE NONCLUSTERED INDEX IX_WELLNESS_ACTIVITY_EnrollmentID_ActivityDate
ON dbo.WELLNESS_ACTIVITY (EnrollmentID, ActivityDate) INCLUDE (VerifiedFlag)
WITH (FILLFACTOR = 80) ON ps_P3_WELLNESS_ACTIVITY (ActivityDate);

ALTER TABLE dbo.Invoice DROP CONSTRAINT Invoice_PK;
ALTER TABLE dbo.Invoice ADD CONSTRAINT Invoice_PK
    PRIMARY KEY NONCLUSTERED (InvoiceID) WITH (FILLFACTOR = 80) ON [PRIMARY];
CREATE CLUSTERED INDEX CIX_Invoice_RunDate_InvoiceID
ON dbo.Invoice (RunDate, InvoiceID)
WITH (FILLFACTOR = 80) ON ps_P3_Invoice (RunDate);
DROP INDEX IX_Invoice_BillingAccount_BillingAccountID ON dbo.Invoice;
CREATE NONCLUSTERED INDEX IX_Invoice_BillingAccount_BillingAccountID
ON dbo.Invoice (BillingAccount_BillingAccountID)
WITH (FILLFACTOR = 80) ON ps_P3_Invoice (RunDate);
GO

-- Increment 3 indexed view.
SET ANSI_NULLS ON;
SET ANSI_PADDING ON;
SET ANSI_WARNINGS ON;
SET ARITHABORT ON;
SET CONCAT_NULL_YIELDS_NULL ON;
SET QUOTED_IDENTIFIER ON;
SET NUMERIC_ROUNDABORT OFF;
GO
CREATE VIEW dbo.vWellnessActivityEnrollmentYear
WITH SCHEMABINDING
AS
    SELECT wa.EnrollmentID, DATEPART(YEAR, wa.ActivityDate) AS ActivityYear,
           COUNT_BIG(*) AS QualifyingActivityCount
    FROM dbo.WELLNESS_ACTIVITY AS wa
    WHERE wa.VerifiedFlag = 'Y'
    GROUP BY wa.EnrollmentID, DATEPART(YEAR, wa.ActivityDate);
GO
CREATE UNIQUE CLUSTERED INDEX CIX_vWellnessActivityEnrollmentYear
ON dbo.vWellnessActivityEnrollmentYear (ActivityYear, EnrollmentID)
WITH (FILLFACTOR = 80);
GO
