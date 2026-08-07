-- Jingrui Feng (jf4446) - database systems project part 3 - physical design workload queries
-- Reproducible physical-design workload.  Each marked block is captured twice
-- by python/etl/capture_baseline.py; the first execution is discarded.

/*
Query ID: Q1
Business use case: A service representative retrieves the policies associated
with a customer during a policy inquiry.
Workload profile: Transactional.
Primary optimization criterion: Response time.
Fixed literal: Customer_CustomerID = 1.
*/
-- BEGIN Q1
SELECT cp.Contract_ContractID AS ContractID, c.ContractNumber, c.ActivityStatus,
       c.EffectiveDate, c.ExpiryDate
FROM dbo.ContractParty AS cp
JOIN dbo.Contract AS c ON c.ContractID = cp.Contract_ContractID
WHERE cp.Customer_CustomerID = 1;
-- END Q1

/*
Query ID: Q2
Business use case: A policy service representative retrieves invoice history
for one policy.  Invoice has no direct Contract foreign key, so this follows
the declared account-level billing traversal.
Workload profile: Transactional.
Primary optimization criterion: Response time.
Fixed literal: ContractID = 1.
*/
-- BEGIN Q2
SELECT i.InvoiceID, i.InvoiceNumber, i.RunDate, i.DueDate, i.PaidDate,
       i.PremiumSubTotal, i.PaymentDate
FROM dbo.Contract AS c
JOIN dbo.ContractParty AS cp ON cp.Contract_ContractID = c.ContractID
JOIN dbo.Customer AS cu ON cu.CustomerID = cp.Customer_CustomerID
JOIN dbo.AccountMember AS am ON am.Customer_CustomerID = cu.CustomerID
JOIN dbo.Account AS a ON a.AccountID = am.Account_AccountID
JOIN dbo.Relation_3 AS r ON r.Account_AccountID = a.AccountID
JOIN dbo.BillingAccount AS ba ON ba.BillingAccountID = r.BillingAccount_BillingAccountID
JOIN dbo.Invoice AS i ON i.BillingAccount_BillingAccountID = ba.BillingAccountID
WHERE c.ContractID = 1
ORDER BY i.RunDate, i.InvoiceID;
-- END Q2

/*
Query ID: Q2b
Business use case: A billing representative retrieves an account's invoice
history without policy-level traversal; paired with Q2 to isolate traversal.
Workload profile: Transactional.
Primary optimization criterion: Response time.
Fixed literal: BillingAccount_BillingAccountID = 38.
*/
-- BEGIN Q2b
SELECT i.InvoiceID, i.InvoiceNumber, i.RunDate, i.DueDate, i.PaidDate,
       i.PremiumSubTotal, i.PaymentDate
FROM dbo.Invoice AS i
WHERE i.BillingAccount_BillingAccountID = 38
ORDER BY i.RunDate, i.InvoiceID;
-- END Q2b

/*
Query ID: Q3
Business use case: The rating service resolves the active published rate book.
Workload profile: Transactional.
Primary optimization criterion: Response time.
Fixed literal: Status = 'Active'.
*/
-- BEGIN Q3
SELECT RateVersionID, EffectiveDate, ExpiryDate, Status, CreatedByRunID
FROM dbo.RATE_VERSION
WHERE Status = 'Active';
-- END Q3

/*
Query ID: Q4
Business use case: A renewal process totals a participant's qualifying wellness
activity inside a twelve-month credit period.
Workload profile: Analytical.
Primary optimization criterion: Throughput.
Fixed literals: EnrollmentID = 12971; 2025-01-01 through 2025-12-31.
*/
-- BEGIN Q4
SELECT EnrollmentID, COUNT_BIG(*) AS QualifyingActivityCount
FROM dbo.WELLNESS_ACTIVITY
WHERE EnrollmentID = 12971
  AND ActivityDate >= '2025-01-01'
  AND ActivityDate < '2026-01-01'
  AND VerifiedFlag = 'Y'
GROUP BY EnrollmentID;
-- END Q4

/*
Query ID: Q5
Business use case: The renewal batch computes qualifying activity totals for
all enrolled policies for one calendar year; this is the indexed-view candidate.
Workload profile: Analytical.
Primary optimization criterion: Throughput.
Fixed literals: 2025-01-01 through 2025-12-31.
*/
-- BEGIN Q5
SELECT EnrollmentID, COUNT_BIG(*) AS QualifyingActivityCount
FROM dbo.WELLNESS_ACTIVITY
WHERE ActivityDate >= '2025-01-01'
  AND ActivityDate < '2026-01-01'
  AND VerifiedFlag = 'Y'
GROUP BY EnrollmentID;
-- END Q5

/*
Query ID: Q6
Business use case: Audit policies pinned to the rate version current at issue,
demonstrating that a later rate revision does not reprice existing policies.
Workload profile: Analytical.
Primary optimization criterion: Throughput.
Fixed literal: IssuedRateVersionID = 6.
*/
-- BEGIN Q6
SELECT ContractID, ContractNumber, EffectiveDate, ExpiryDate, ModalPremium,
       IssuedRateVersionID
FROM dbo.Contract
WHERE IssuedRateVersionID = 6;
-- END Q6

/*
Query ID: Q7
Business use case: The quarterly renewal batch identifies policies to reprice.
Workload profile: Analytical.
Primary optimization criterion: Throughput.
Fixed literals: 2025-01-01 through 2025-03-31.
*/
-- BEGIN Q7
SELECT RenewalID, ContractID, RenewalDate, NewRateVersionID,
       WellnessDiscountPct, FinalPremium
FROM dbo.POLICY_RENEWAL
WHERE RenewalDate >= '2025-01-01'
  AND RenewalDate < '2025-04-01';
-- END Q7

/*
Query IDs: Q8a-count, Q8b-count, Q8a, Q8b
Business use case: The physical-design analysis contrasts covered counts with
non-covering policy retrieval at selective Lapsed and common Active predicates.
Workload profile: Analytical selectivity contrast.
Primary optimization criterion: Throughput.
Fixed literals: ActivityStatus = 'Lapsed' and ActivityStatus = 'Active'.
*/
-- BEGIN Q8a-count
SELECT COUNT_BIG(*) AS LapsedContractCount
FROM dbo.Contract
WHERE ActivityStatus = 'Lapsed'
-- END Q8a-count

-- BEGIN Q8b-count
SELECT COUNT_BIG(*) AS ActiveContractCount
FROM dbo.Contract
WHERE ActivityStatus = 'Active';
-- END Q8b-count

-- Not covered by IX_Contract_ActivityStatus: EffectiveDate and ModalPremium
-- require a lookup if the status index is chosen, exposing the selectivity
-- crossover against a clustered scan.
-- BEGIN Q8a
SELECT ContractID, EffectiveDate, ModalPremium
FROM dbo.Contract
WHERE ActivityStatus = 'Lapsed';
-- END Q8a

-- BEGIN Q8b
SELECT ContractID, EffectiveDate, ModalPremium
FROM dbo.Contract
WHERE ActivityStatus = 'Active';
-- END Q8b

/*
Query ID: Q9
Business use case: The asynchronous refresh process derives BRFSS diabetes
prevalence by modeling profile before it publishes a new rate version.
Workload profile: Batch.
Primary optimization criterion: Throughput.
Fixed literal: all loaded 2024 BRFSS records.
*/
-- BEGIN Q9
WITH outcome AS (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand,
           ExerciseFreq, LoadDate, SourceFile, COUNT_BIG(*) AS OutcomeRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL
      AND DiabetesStatus IS NOT NULL AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand,
             ExerciseFreq, LoadDate, SourceFile
),
profile AS (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq,
           LoadDate, SourceFile, COUNT_BIG(*) AS ProfileRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL
      AND DiabetesStatus IS NOT NULL AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq,
             LoadDate, SourceFile
)
SELECT outcome.SourceYear, outcome.AgeBand, outcome.Gender, outcome.SmokingStatus,
       outcome.DiabetesStatus, outcome.BMIBand, outcome.ExerciseFreq,
       CAST(CAST(outcome.OutcomeRows AS DECIMAL(18,8)) / profile.ProfileRows AS NUMERIC(6,4)) AS PrevalenceRate
FROM outcome
JOIN profile
  ON profile.SourceYear = outcome.SourceYear
 AND profile.AgeBand = outcome.AgeBand
 AND profile.Gender = outcome.Gender
 AND profile.SmokingStatus = outcome.SmokingStatus
 AND profile.BMIBand = outcome.BMIBand
 AND profile.ExerciseFreq = outcome.ExerciseFreq
 AND profile.LoadDate = outcome.LoadDate
 AND profile.SourceFile = outcome.SourceFile;
-- END Q9

/*
Query ID: Q10 (not measured)
Business use case: Generate a quoted premium for a new applicant from RATE.
RATE is intentionally empty pending the model-and-refresh pipeline, so this is
kept commented out rather than fabricating rate data solely for measurement.
*/
-- SELECT r.RateVersionID, r.ProductID, r.BaseRate
-- FROM dbo.RATE AS r
-- JOIN dbo.RATE_VERSION AS rv ON rv.RateVersionID = r.RateVersionID
-- WHERE rv.Status = 'Active' AND r.ProductID = 1;
