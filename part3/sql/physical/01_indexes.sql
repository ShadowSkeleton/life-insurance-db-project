-- Jingrui Feng (jf4446) - database systems project part 3 - physical design indexes
-- Increment 1: targeted nonclustered indexes only.  Run after the captured
-- baseline and before partitioning or indexed-view work.  FILLFACTOR 80 is
-- used on continually growing transactional tables to reserve page space and
-- reduce page splits; the load-once ContractParty index uses 100 for density.
-- No RATE_VERSION index is created: Q3 reads two pages from a six-row table.
-- No STG_* index is created: staging is bulk-written and its refresh workload
-- scans full inputs, so extra indexes would add write cost without a seek path.
SET NOCOUNT ON;
GO

-- Q1: customer policy inquiry.  Seeks ContractParty by Customer_CustomerID;
-- Contract_ContractID is included to avoid a key lookup. Response time.
CREATE NONCLUSTERED INDEX IX_ContractParty_Customer_CustomerID
ON dbo.ContractParty (Customer_CustomerID)
INCLUDE (Contract_ContractID)
WITH (FILLFACTOR = 100);
GO

-- Q2/Q2b: account-level invoice history.  Seeks invoices by the declared
-- BillingAccount foreign key. Response time; FILLFACTOR 80 supports inserts.
CREATE NONCLUSTERED INDEX IX_Invoice_BillingAccount_BillingAccountID
ON dbo.Invoice (BillingAccount_BillingAccountID)
WITH (FILLFACTOR = 80);
GO

-- Q4/Q5: wellness credit aggregation.  Seeks an enrollment/date range and
-- scans a narrower date-aware path for annual aggregation. VerifiedFlag is an
-- INCLUDE rather than a key because it is a residual qualifying predicate and
-- makes the aggregation covering without widening the navigation key.
-- Throughput; FILLFACTOR 80 supports continuous activity inserts.
CREATE NONCLUSTERED INDEX IX_WELLNESS_ACTIVITY_EnrollmentID_ActivityDate
ON dbo.WELLNESS_ACTIVITY (EnrollmentID, ActivityDate)
INCLUDE (VerifiedFlag)
WITH (FILLFACTOR = 80);
GO

-- Q6: effective-dated pricing audit.  Seeks contracts pinned to a rate
-- version. Throughput; FILLFACTOR 80 supports continuing contract inserts.
CREATE NONCLUSTERED INDEX IX_Contract_IssuedRateVersionID
ON dbo.Contract (IssuedRateVersionID)
WITH (FILLFACTOR = 80);
GO

-- Q7: quarterly renewal worklist.  Seeks the requested renewal-date range.
-- Throughput; FILLFACTOR 80 supports continuing renewal inserts.
CREATE NONCLUSTERED INDEX IX_POLICY_RENEWAL_RenewalDate
ON dbo.POLICY_RENEWAL (RenewalDate)
WITH (FILLFACTOR = 80);
GO

-- Q8a/Q8b: policy-status selectivity contrast.  Provides a narrow status
-- access path; the optimizer may still prefer a scan for the common Active
-- predicate. Throughput; FILLFACTOR 80 supports continuing contract inserts.
CREATE NONCLUSTERED INDEX IX_Contract_ActivityStatus
ON dbo.Contract (ActivityStatus)
WITH (FILLFACTOR = 80);
GO
