# Mockaroo CSV validation report

Validation source: `schema_final.sql` and `bridge_schema.sql`.

## Applied fixes

- Each corrected CSV has its original pre-repair version preserved beside it as a `.csv.bak` file.

## Customer.csv

Row count: 1000

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `CustDOB` | 1000 | row 2: 'error: invalid date "1945-01-01"' | Mockaroo error/placeholder text |
| 8 | `StartDate` | 1000 | row 2: 'error: invalid date "2015-01-01"' | Mockaroo error/placeholder text |
| 8 | `EndDate` | 1000 | row 2: 'error: invalid date "2026-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## Product.csv

Row count: 15

### Problems found before repair

Passes all requested checks.

### Status after repair

Passes all requested checks.

## BillingAccount.csv

Row count: 300

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 3 | `BillingState` | 252 | row 3: blank | NOT NULL value is blank |
| 4 | `BillingState` | 3 | row 32 (3 chars): 'MEX' | max length 2 |
| 3 | `BillingZip` | 155 | row 3: blank | NOT NULL value is blank |
| 4 | `BillingZip` | 10 | row 31 (14 chars): '75547 CEDEX 11' | max length 10 |
| 8 | `BillingAddress2` | 300 | row 2: "error: undefined method `first' for nil:NilClass" | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## Contract.csv

Row count: 500

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 4 | `InForceFlag` | 500 | row 2 (48 chars): "error: undefined method `first' for nil:NilClass" | max length 1 |
| 4 | `CardType` | 134 | row 20 (25 chars): 'diners-club-carte-blanche' | max length 10 |
| 8 | `InForceFlag` | 500 | row 2: "error: undefined method `first' for nil:NilClass" | Mockaroo error/placeholder text |
| 8 | `PayUpDate` | 500 | row 2: 'error: invalid date "2040-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## Claim.csv

Row count: 200

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `ClaimDate` | 200 | row 2: 'error: invalid date "2020-01-01"' | Mockaroo error/placeholder text |
| 8 | `SettlementDate` | 200 | row 2: 'error: invalid date "2020-01-01"' | Mockaroo error/placeholder text |
| 8 | `WellnessEligibilityDate` | 200 | row 2: 'error: invalid date "2020-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## ContractParty.csv

Row count: 500

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `CustDOB` | 500 | row 2: 'error: invalid date "1945-01-01"' | Mockaroo error/placeholder text |
| 8 | `StartDate` | 500 | row 2: 'error: invalid date "2015-01-01"' | Mockaroo error/placeholder text |
| 8 | `EndDate` | 500 | row 2: 'error: invalid date "2026-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## Invoice.csv

Row count: 600

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `PaidDate` | 600 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |
| 8 | `DueDate` | 600 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |
| 8 | `RunDate` | 600 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |
| 8 | `PaymentDate` | 600 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## WELLNESS_PROGRAM.csv

Row count: 5

### Problems found before repair

Passes all requested checks.

### Status after repair

Passes all requested checks.

## WELLNESS_ENROLLMENT.csv

Row count: 200

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `EnrollDate` | 200 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## WELLNESS_ACTIVITY.csv

Row count: 800

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `ActivityDate` | 800 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.

## RISK_IMPROVEMENT.csv

Row count: 400

### Problems found before repair

| Check | Column | Rows affected | Example | Detail |
|---:|---|---:|---|---|
| 8 | `MeasureDate` | 400 | row 2: 'error: invalid date "2022-01-01"' | Mockaroo error/placeholder text |

### Status after repair

Passes all requested checks.
