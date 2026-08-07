# Jingrui Feng (jf4446) - database systems project part 3 - quote to policy use cases

# Quote-to-policy use cases

I designed these use cases to document the Part 3 quote-to-policy application and its database interactions. I use the deployed table names so the business workflow stays connected to the physical database work. The local web application implements the documented quote, binding, wellness, and refresh workflows. I added renewal as UC-5 because the wellness offset and current-rate repricing need a complete business workflow.

## UC-1 Applicant obtains a quote

| Field | Description |
|---|---|
| Use Case ID | UC-1 |
| Name | Applicant obtains a quote |
| Primary Actor | Applicant |
| Secondary Actors | Web application, database |
| Stakeholders and Interests | Applicant wants an understandable current quote. The company needs a quote based on the active rate book and a traceable rate-version identifier. |
| Preconditions | A product is available. An active `RATE_VERSION` is effective on the quote date. A corresponding `RATE` row and `RISK_FACTOR` profile can be found. |
| Success Guarantee | A premium quotation is returned with the `RateVersionID` used for the calculation and an `APPLICATION` row records the profile, face amount, quote, and status. No `Contract` is created by this use case. |
| Frequency of Occurrence | On demand, whenever an applicant requests a quote. |
| Special Requirements | The form collects age, gender, smoking status, binary diabetes status, BMI, and face amount. Exercise is not collected at application. It becomes observable through wellness enrolment. |
| Data Touched | Read: `Product`, `RATE_VERSION`, `RATE`, `RISK_FACTOR`, `Customer`. Written: `Customer` when needed and `APPLICATION` with status `quoted`. |

### Main Success Scenario

1. The applicant selects a product and submits age, gender, smoking status, diabetes status, BMI, and face amount.
2. The web application validates that all five profile values are present and can be placed into the rate-factor bands.
3. The system identifies or creates the `Customer` record needed by `APPLICATION`.
4. The system reads the `RATE_VERSION` row that is active and effective on the quote date.
5. The system finds the matching `RISK_FACTOR` profile and the `RATE` row for the selected `Product` and active `RateVersionID`.
6. The system calculates the premium from the matching rate row.
7. The system writes `APPLICATION` with status `quoted`, the profile, face amount, quoted rate version, and quoted premium.
8. The system returns the premium and the `RateVersionID` used.

### Extensions

2a. If the profile is incomplete, the system identifies the missing value and requests correction. No rate tables are read for a final quote.

4a. If no `RATE` row matches the product and profile, the system returns that the profile combination is not available for quotation and routes the case for review. No `Contract` is created.

6a. If the applicant does not convert the quote, the interaction ends. No `Contract`, `ContractParty`, billing-account, or invoice record is created.

## UC-2 Applicant converts a quote to a policy

| Field | Description |
|---|---|
| Use Case ID | UC-2 |
| Name | Applicant converts a quote to a policy |
| Primary Actor | Applicant |
| Secondary Actors | Web application, database |
| Stakeholders and Interests | Applicant wants the accepted policy issued at the correct current rate. The company needs the policy tied permanently to the rate version active on its effective date. |
| Preconditions | The applicant accepts a persisted `APPLICATION` quote. Party information, account-level billing information, and the effective date are available. |
| Success Guarantee | A `Contract` is created with `IssuedRateVersionID` set to the `RATE_VERSION` active on its `EffectiveDate` and `ApplicationID` set to the accepted application. |
| Frequency of Occurrence | When an applicant accepts a quote and coverage is bound. |
| Special Requirements | The issued rate version is determined by the policy effective date, not by the date of a previous quote. Billing is at the account level through `AccountMember`, `Account`, `Relation_3`, and `BillingAccount`. The workflow does not provide per-policy premium history. |
| Data Touched | Read: `APPLICATION`, `Product`, `RATE_VERSION`, `RATE`, `RISK_FACTOR`, `Customer`, `Account`, `AccountMember`, `Relation_3`, `BillingAccount`. Written: `APPLICATION` status, `Contract`, `ContractParty`, `Account`, `AccountMember`, `BillingAccount`, and `Relation_3` when needed. |

### Main Success Scenario

1. The applicant accepts the persisted quote and provides the requested effective date and party details.
2. The web application reads `APPLICATION`, then determines the `RATE_VERSION` active on the requested `EffectiveDate` and obtains the matching `RATE` row.
3. The system validates the `Customer` record attached to `APPLICATION`.
4. The system creates `Contract` with the selected product, effective-date information, `IssuedRateVersionID`, and `ApplicationID`.
5. The system creates `ContractParty` to connect the customer to the contract.
6. The system identifies or creates the account-level billing path through `AccountMember`, `Account`, `Relation_3`, and `BillingAccount`.
7. The system updates `APPLICATION.Status` to `bound` and confirms that the contract is pinned to its issue-time rate version.

### Extensions

2a. If the rate version changed between quotation and binding, the system recalculates the quote from the rate version active on the requested effective date and asks the applicant to accept the revised premium before proceeding.

3a. If identity or party validation fails, the system does not create the contract and requests correction.

6a. If the billing-account relationship cannot be established, the system does not bind the policy. No invoice is created as part of policy binding.

## UC-3 Policyholder reports wellness participation

| Field | Description |
|---|---|
| Use Case ID | UC-3 |
| Name | Policyholder reports wellness participation |
| Primary Actor | Participating gym |
| Secondary Actors | Policyholder, web application, database, periodic measurement process |
| Stakeholders and Interests | Policyholders want verified participation recognized before renewal. The company needs traceable activity and measured improvement before applying a renewal offset. |
| Preconditions | The policyholder has a bound `Contract` and can select a published `WELLNESS_PROGRAM`. The gym can identify the enrollment after it is recorded. |
| Success Guarantee | The enrollment and activity are recorded in `WELLNESS_ENROLLMENT` and `WELLNESS_ACTIVITY`. Verified participation can later contribute to a measured `RISK_IMPROVEMENT` before a renewal date. |
| Frequency of Occurrence | Each time a participating gym reports an activity, with periodic improvement measurement. |
| Special Requirements | Only `RISK_IMPROVEMENT` rows dated before a renewal are eligible for that renewal's discount. The discount calculation is capped at 15 percent. |
| Data Touched | Read: `WELLNESS_PROGRAM`, `Contract`. Written: `WELLNESS_ENROLLMENT`, `WELLNESS_ACTIVITY`, and later `RISK_IMPROVEMENT`. |

### Main Success Scenario

1. The policyholder selects a published wellness program for the bound policy and records an enrollment date before the next projected renewal.
2. The system writes an active `WELLNESS_ENROLLMENT` associated with the `Contract` and selected `WELLNESS_PROGRAM`.
3. A participating gym submits an activity with the enrollment identifier, activity date, and activity type.
4. The system verifies that the enrollment exists and is eligible for the wellness program.
5. The system records the activity in `WELLNESS_ACTIVITY` with its `VerifiedFlag`.
6. A periodic measurement process evaluates eligible verified activity and changeable-factor measurements.
7. The process writes a dated `RISK_IMPROVEMENT` row with the measure, baseline, and improvement percentage.
8. The resulting improvement remains available for a later renewal calculation if its `MeasureDate` is before the renewal date.

### Extensions

1a. If the selected program does not exist or the enrollment date is not before the projected renewal, the system does not create `WELLNESS_ENROLLMENT`.

5a. If the activity cannot be verified, the system records it with an unverified `VerifiedFlag`. It is not used by the periodic measurement process until verification is resolved.

6a. If no qualifying change can be measured, the system creates no `RISK_IMPROVEMENT` row. A later renewal receives no wellness offset from that missing measurement.

## UC-4 System performs scheduled rate revision

| Field | Description |
|---|---|
| Use Case ID | UC-4 |
| Name | System performs scheduled rate revision |
| Primary Actor | Scheduler |
| Secondary Actors | Scheduled refresh job, model scoring process, database, Azure Blob Storage, Synapse serverless |
| Stakeholders and Interests | The company needs current, traceable pricing inputs without interrupting quote and policy transactions. Applicants need new quotes to use the current approved rate book. Existing policyholders must retain their issue-time rate version. |
| Preconditions | Curated external files are available in the data lake. Staging tables are loaded. An approved diabetes-risk model and its coefficients are available for scoring. |
| Success Guarantee | A successful run records `DATA_REFRESH_RUN`, derives `RISK_FACTOR` rows, publishes a new `RATE_VERSION` with `RATE` rows, and records the producing run on the published rate version. |
| Frequency of Occurrence | Scheduled, with a manual run available only for controlled operations. The local demonstration runs the job locally. The target architecture maps the job host to Azure Functions. |
| Special Requirements | The model performs diabetes risk stratification from BRFSS data. It is not described or used as a mortality model. The job is asynchronous and does not update `Contract.IssuedRateVersionID` for in-force policies. |
| Data Touched | Read: `STG_BRFSS_RECORD`, `STG_BRFSS`, `STG_NHANES`, `STG_MORTALITY`, `Product`, existing `RATE_VERSION`. Written: `DATA_REFRESH_RUN`, `RISK_FACTOR`, `RATE_VERSION`, `RATE`. |

### Main Success Scenario

1. The scheduler starts the asynchronous refresh job.
2. The job creates a running `DATA_REFRESH_RUN` row with source dataset lineage.
3. The job reads the staged BRFSS, NHANES, and mortality information. `STG_BRFSS_RECORD` retains source records and `STG_BRFSS` supplies database-derived profile prevalence.
4. The model scoring process applies the approved diabetes-risk coefficients to the supported profile bands.
5. The job combines the approved scoring output and normalized staging information to write the new `RISK_FACTOR` rows for the run.
6. The job creates a new effective-dated `RATE_VERSION` and writes its `RATE` rows for the available products and risk factors.
7. The job records the new rate version in `DATA_REFRESH_RUN.NewRateVersionID`, marks the run successful, and closes the preceding active rate version as appropriate.
8. Publishing the new `RATE_VERSION` does not modify any existing `Contract` row and specifically does not alter `Contract.IssuedRateVersionID`. Existing policies continue to reference the rate version active on their own effective date. New quotes use the newly active rate version.

### Extensions

3a. If a required source dataset is unavailable or fails validation, the job records failure details in `DATA_REFRESH_RUN`, writes no new rate version, and leaves the existing active `RATE_VERSION` available for quoting.

4a. If model scoring produces implausible output under the approved validation thresholds, the job records failure details in `DATA_REFRESH_RUN` and does not publish `RISK_FACTOR`, `RATE_VERSION`, or `RATE` rows for that run.

6a. If rate publication fails, the job marks the run failed and does not expose a partially published rate version as active.

## UC-5 Policy renewal is repriced with a wellness offset

| Field | Description |
|---|---|
| Use Case ID | UC-5 |
| Name | Policy renewal is repriced with a wellness offset |
| Primary Actor | Scheduler |
| Secondary Actors | Renewal service, database, policyholder |
| Stakeholders and Interests | Policyholders want eligible wellness participation reflected at renewal. The company needs renewals repriced against the rate version active on the renewal date, with a reproducible discount. |
| Preconditions | A contract has reached a renewal anniversary within its coverage period. A `RATE_VERSION` is active on the renewal date. |
| Success Guarantee | A `POLICY_RENEWAL` row records the renewal date, the active `NewRateVersionID`, the calculated wellness discount, and the final premium. |
| Frequency of Occurrence | At each eligible contract anniversary. |
| Special Requirements | The renewal uses the version active on the renewal date. The contract's original `IssuedRateVersionID` is retained. Only `RISK_IMPROVEMENT` rows dated before the renewal count. The wellness discount is capped at 15 percent. |
| Data Touched | Read: `Contract`, `APPLICATION`, `RATE_VERSION`, `RATE`, `RISK_FACTOR`, `WELLNESS_ENROLLMENT`, `RISK_IMPROVEMENT`. Written: `POLICY_RENEWAL`. |

### Main Success Scenario

1. The scheduler identifies an eligible contract anniversary.
2. The renewal service reads the linked `APPLICATION` profile and face amount, then finds the applicable `RATE` row for the version active on the `RenewalDate`.
3. The service reads the contract's wellness enrollment and `RISK_IMPROVEMENT` rows dated before the renewal date.
4. The service derives a wellness discount from measured improvement, using zero when there is no qualifying improvement and capping the result at 15 percent.
5. The service writes `POLICY_RENEWAL` with the contract, renewal date, active `NewRateVersionID`, wellness discount, and final premium.
6. The contract continues to retain its original `IssuedRateVersionID`, even when `NewRateVersionID` is newer.

### Extensions

3a. If the contract has no wellness enrollment or no qualifying improvement before the renewal date, the service applies a zero wellness discount.

4a. If the derived discount exceeds 15 percent, the service stores 15 percent.

2a. If no active rate version or matching rate row is available, the service does not create `POLICY_RENEWAL` and routes the renewal for review.

## Required-mechanism mapping

| Professor-required mechanism | Use case and steps | Database evidence |
|---|---|---|
| An asynchronous mechanism revises policy pricing from external datasets | UC-4 steps 1 through 7 | `DATA_REFRESH_RUN` records the run. Staging tables supply inputs. `RISK_FACTOR`, `RATE_VERSION`, and `RATE` publish the result. |
| Pricing changes do not affect existing policyholders. New applicants get current rates | UC-1 steps 3 through 6, UC-2 steps 2 through 7, and UC-4 step 8 | UC-1 reads the active `RATE_VERSION`. UC-2 writes `Contract.IssuedRateVersionID` for the version active on `EffectiveDate`. UC-4 explicitly publishes rate data without modifying existing `Contract` rows or their issue-time version pins. |
| Renewals are repriced against new rates, offset by wellness participation | UC-3 steps 1 through 8 and UC-5 steps 2 through 6 | `RISK_IMPROVEMENT` is dated and linked to enrollment. `POLICY_RENEWAL.NewRateVersionID` identifies the active renewal rate version and `WellnessDiscountPct` records the capped offset. |
