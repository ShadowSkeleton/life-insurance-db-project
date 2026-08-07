# Jingrui Feng (jf4446) - database systems project part 3 - design change log

# Part 3 change log

## Design decisions

BRFSS `DIABETE4` response 4, pre-diabetes or borderline diabetes, maps to `no`
when `RISK_FACTOR` is constructed and remains excluded from the model's primary
label. No lake dataset supplies a pre-diabetes mortality multiplier: the CDC
WONDER diabetes extract uses ICD E10–E14 and therefore covers diagnosed
diabetes only, while cross-sectional BRFSS cannot provide progression risk. A
three-level rating factor would require an invented middle value and would
break the bridge schema's source-traceability rule. `STG_BRFSS` retains all four
source outcome levels because staging mirrors the source; the binary collapse
belongs only in `RISK_FACTOR` construction. Modeling must include a sensitivity
analysis using `label_sensitivity` and report how coefficients move when
pre-diabetes is folded into the positive class.

Premium billing is modeled at the BillingAccount grain because `Invoice`
references `BillingAccount`, not `Contract`, consistent with household billing
practice inherited from the Part 1 blueprint. Policy-level premium attribution
is outside the current scope and would require a direct Contract-to-Invoice
foreign key. This is a scope boundary rather than a defect: no use case,
process model, or demonstration screen may imply per-policy premium history.

The retained 2018–2024 CDC WONDER pooled period spans COVID-era mortality. The
original prediction was that diabetes recorded as a contributing condition at
elevated rates would inflate the diabetes-to-all-cause ratio and tend to
overcharge diabetic applicants. That prediction was tested against the loaded
2022–2024 cohort and falsified: the newer ratio is higher in 12 of 16 adult
age-sex cells, so the pooled ratio is generally depressed rather than inflated,
although the direction is mixed. The mean absolute difference is 0.073
percentage points and the largest is 0.189 percentage points for males aged
55–64, so the distortion is real but small.

The mechanism is consistent with the actual WONDER query definition. The
E10–E14 extract uses underlying cause of death, so a death whose underlying
cause was COVID-19 and whose diabetes was a comorbidity was coded to COVID-19,
not diabetes. COVID-era mortality therefore substantially increased the
all-cause denominator while barely affecting the diabetes numerator, depressing
the 2018–2024 ratio. The 2022–2024 cohort is the pricing input; the older pooled
export remains a lake asset for comparison only.

The diabetes model estimates residual diabetes risk among applicants who
disclose no diabetes. The disclosed answer remains authoritative, and the model
refines the no-diabetes class without overriding it. Smoking status, BMI, and
exercise are modifiable model inputs, so a wellness renewal credit can be tied
to a measured reduction in estimated residual risk rather than to an arbitrary
percentage. The coefficients measure diabetes risk rather than direct mortality.
SSA supplies absolute mortality, CDC WONDER supplies the diagnosed-diabetes
effect, documented external all-cause relativities supply smoking and BMI
magnitudes, and the model supplies residual differentiation within the
disclosed no-diabetes class.

The inherited logical model stored policies but not the applications that
produce them. It therefore persisted neither the applicant risk profile nor the
face amount needed to turn a per-1,000 rate into a premium. The gap was
invisible through Parts 1 and 2 because no quote was reproduced from the
schema. It surfaced only when the pricing pipeline attempted to match a contract
to a rate. Part 3 adds `APPLICATION`, which stores raw age and BMI, their BRFSS
bands, disclosed diabetes status, smoking status, face amount, quote version,
quote premium, and status. `Contract.ApplicationID` links a bound policy back
to that application. Exercise remains absent at application because it becomes
observable through wellness enrolment and is used at renewal rather than quote.

## Medium-term extensions

A three-level rating treatment for pre-diabetes is a medium-term extension once
an authoritative source supplies a traceable pre-diabetes mortality multiplier
or progression-risk basis. Policy-level premium attribution is also a
medium-term extension and would require a direct Contract-to-Invoice
relationship plus corresponding changes to the inherited billing process and
demo scope.

## 2026-07-28

`ContractParty.BenefitReference` is present in the inherited schema but is
unpopulated by the synthetic generator: all 90,000 rows are NULL and no current
business rule writes the column.

`Invoice` references `BillingAccount`, but has no direct foreign key to
`Contract`; `Contract` likewise has no foreign key to `BillingAccount`.
The declared policy-to-invoice traversal is Contract → ContractParty → Customer
→ AccountMember → Account → Relation_3 → BillingAccount → Invoice. This models
billing at the account level, which is consistent with insurance practice, but
policy-level invoice attribution requires this multi-table join. The original
volume target omitted Account, AccountMember, and Relation_3 even though they
are required to populate this declared path. On 2026-07-28, the generator and
local load were extended with 40,000 Account rows, 50,000 AccountMember rows,
and 40,000 Relation_3 rows. Each of the 50,000 customers now reaches exactly
one BillingAccount through the path.

With the path populated, 720,259 distinct Contract-to-Invoice pairs are
reachable and all 60,000 generated contracts have at least one reachable
invoice. The later application demonstration added two contracts outside that
synthetic population. The generator's claimed invoice-after-effective-date rule
can now be measured but was not enforceable through the formerly unpopulated relationship. Using
Invoice.RunDate as the invoice date, 161,594 reachable pairs (22.4355 percent)
predate the linked Contract.EffectiveDate. This is recorded for design review;
the existing synthetic data was not regenerated or corrected.

## 2026-07-30

Version 7 exposed a pricing gap. Its 312 disclosed-diabetes factors collapsed
to 26 distinct multipliers because they depended only on age band and gender.
Its 312 disclosed-no factors had 38 distinct multipliers, and all 26 age-sex
cells had three or more values across the twelve smoking-BMI combinations.
For the requested 45-49 male, non-diabetic Product 3 comparison, the
current-smoking, obese annual premium was $1,802.50 and the never-smoking,
normal premium was $1,787.50, a ratio of 1.0084. The requested audit text
anticipated a 1.3 percent spread, but the measured comparison is 0.84 percent;
the measured value is retained rather than rounded up.

Version 8 corrects that gap by applying named external all-cause mortality
relativities before the diabetes composition: never, former, and current
smoking are 1.00, 1.30, and 2.30, while normal, underweight, overweight, and
obese BMI bands are 1.00, 1.20, 1.05, and 1.35. They are external judgment
inputs supported by smoking and BMI mortality literature, not coefficients
derived from the diabetes model or the project lake.

`APPLICATION` represents submitted applications rather than casual quotes, so
the 66.7 percent bound-application conversion rate is a realistic workflow
measure rather than a consumer quote conversion claim. The approximately 2.2x
gap between the $1,787.50 reference computed premium and an $800 mid-market
reference point is the expected order of magnitude for a population-based
prototype. Select mortality in early insured durations commonly runs at roughly
40 to 60 percent of population mortality, so a future selection adjustment is
required before treating the rate book as a market quote.

The BMI band definitions entered the project implicitly through the BRFSS
calculated variable `_BMI5CAT` and were never stated in project code. Earlier
components consumed the pre-banded value, so none needed the cut points. The
web application is the first component to derive a band from raw BMI, which
exposed the gap. The CDC and WHO boundaries are now recorded explicitly:
`under` is below 18.5, `normal` is 18.5 inclusive to below 25.0, `over` is
25.0 inclusive to below 30.0, and `obese` is 30.0 or higher. The staged BRFSS
record data verifies the observed ranges as 12.53–18.49, 18.50–24.99,
25.00–29.99, and 30.00–99.79 respectively.

Versions 7 through 10 are visibly effective and expired on 2026-07-30. Each is
a legitimate refresh publication from demonstration or testing runs. Their
zero-length calendar lifetimes are an artifact of multiple runs on one day while
the inherited `RATE_VERSION` columns use `DATE`, not `DATETIME`. This is a
date-granularity limitation, not a pipeline defect. Version 11 is the current
active version.

The first attempt to select a WONDER cohort exposed a refresh lookup bug. The
script incorrectly used the selected WONDER SourceYear to find the SSA baseline,
although `ssa_period_life_table_2023.csv` is staged only under SourceYear 2023.
The SSA lookup is now fixed to SourceYear 2023 while the WONDER ratio is selected
independently by cohort. The command records the selected cohort, loading factor,
and undiagnosed fraction in the published run notes so a rate version can be
traced to its inputs.

Switching WONDER cohorts moved premiums by at most 0.91 percent across the three
checked Product 3, $250,000 profiles. The small, bounded effect means the
COVID-period difference in the pooled cohort does not materially destabilize
pricing in this prototype; it is a measured robustness finding rather than a
limitation of the refresh mechanism.

## 2026-08-03

I found 200 Customer rows and 15 Product rows in the Azure deployment during
the Part 3 inventory. The Part 2 report described approximately 1,015 loaded
rows. I record the discrepancy without further investigation because the Azure
database is being redeployed from the verified Part 3 volume data.

| Profile | 2022-2024 cohort | 2018-2024 cohort | Difference |
| --- | ---: | ---: | ---: |
| 45-49 male, never smoker, normal BMI, DIABETIC | $2,482.50 | $2,460.00 | -0.91% |
| 55-59 male, current smoker, obese, DIABETIC | $14,317.50 | $14,217.50 | -0.70% |
| 45-49 male, never smoker, normal BMI, NON-diabetic | $1,787.50 | $1,787.50 | 0.00% |

## 2026-08-04

I deployed `func-dbp3-raterefresh` as a Linux Python 3.11 Azure Function on
the Consumption plan. At initial deployment, its timer schedule was
`0 0 2 * * *`, so the asynchronous pricing mechanism executed at 02:00 UTC
each day without a human trigger.
The function reads the Blob model export and Azure staging data, then writes
only `DATA_REFRESH_RUN`, `RISK_FACTOR`, `RATE_VERSION`, and `RATE`; it has no
write path to Contract.

The first successful manual timer invocation published version 8. Two later
diagnostic invocations also completed successfully and published version 9,
which is now active. Each published run recorded cohort 2023, loading 1.50,
undiagnosed fraction 0.20, the fixed SSA baseline source year 2023, and the
external smoking and BMI relativity inputs in `DATA_REFRESH_RUN.Notes`. No
Contract references either new version.

I changed the Azure Function timer from daily to monthly, with NCRONTAB
expression `0 0 2 1 * *`: the first day of each month at 02:00 UTC. CDC WONDER,
SSA period life tables, and BRFSS all publish annually, so daily execution would
normally recompute the same rates from unchanged inputs. Monthly execution is
still more frequent than the source publication cycle and retains the
asynchronous, unattended mechanism. It also avoids waking the serverless Azure
SQL database each day for work that has no new source data.

Three deployment-verification invocations published Azure rate versions 7, 8,
and 9. Each created 624 `RISK_FACTOR` rows and 9,360 `RATE` rows, and zero
Contracts reference any of those versions. Repeated publication without
disturbing existing policies is the pricing mechanism behaving correctly under
load, not an anomaly. Azure version 9 is active, while the local database is on
version 11 because it received additional demonstration runs.
