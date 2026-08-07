# Jingrui Feng (jf4446) - database systems project part 3 - rate publication pipeline

# Pricing pipeline

The local refresh script is [run_rate_refresh.py](../python/etl/run_rate_refresh.py). It consumes the approved profile-probability export together with staged BRFSS, SSA, and a selected CDC WONDER cohort. A successful run writes a run record, 624 risk factors, a new effective-dated version, and 9,360 rates in one transaction. A failed publication rolls back and then records a separate failed `DATA_REFRESH_RUN` row.

The command accepts `--wonder-cohort-source-year` (2023 for the 2022-2024 cohort or 2024 for the pooled 2018-2024 cohort), `--loading-factor`, and `--undiagnosed-fraction`. The SSA baseline is deliberately always read from SourceYear 2023, the year of `ssa_period_life_table_2023.csv`; it is independent of the selected WONDER cohort. The published `DATA_REFRESH_RUN.Notes` records all three chosen values and the baseline source year, while `SourceDatasets` records the exact curated WONDER filenames.

## Relative-risk derivation

For each age band and gender, I use `m` for the SSA lives-weighted population mortality rate, `p` for staged diagnosed-diabetes prevalence, `mn` for non-diabetic mortality, `md` for diabetic mortality, and `f` for the 2022-2024 WONDER diabetes-to-all-cause ratio. The two assumptions are `m = p * md + (1 - p) * mn` and `f * m = p * (md - mn)`. With `RR = md / mn`, solving gives `RR = (f * p - p - f) / (p * (f - 1))`.

The WONDER extract counts diabetes only when it is the underlying cause of death. Diabetes is often a contributing condition instead, so this source understates the diabetes mortality effect. The resulting lower relative risks are retained as observed rather than adjusted with an invented uplift.

## Smoking, BMI, exercise, and residual risk

The lake's aggregate mortality sources are keyed by age and sex. They therefore support the age, sex, and diabetes components that are calculated from collected data, but cannot estimate all-cause mortality by smoking status or BMI band. The diabetes model estimates diabetes probability, not all-cause mortality. Its smoking and BMI coefficients support the direction and ordering of residual diabetes risk, but they are not used as direct mortality weights.

The refresh uses named external all-cause mortality relativities: never, former, and current smoking are 1.00, 1.30, and 2.30. The current-smoking value is a conservative underwriting judgment input relative to the approximately 2.8 to 3.0 current-versus-never all-cause hazards reported by Jha et al., [21st-Century Hazards of Smoking](https://www.nejm.org/doi/full/10.1056/NEJMsa1211128). The former-smoking value is also a judgment input rather than a universal observed estimate because risk depends on age and time since cessation. The [2020 Surgeon General report](https://www.cdc.gov/tobacco-surgeon-general-reports/reports/2020-smoking-cessation/index.html) documents that cessation reduces mortality-related risks over time.

Normal, underweight, overweight, and obese BMI bands use 1.00, 1.20, 1.05, and 1.35. These are conservative category proxies drawn from the direction and approximate magnitude of the [Global BMI Mortality Collaboration](https://pubmed.ncbi.nlm.nih.gov/27423262/) evidence. They are not derived from the lake. Underweight above normal is intentional: all-cause mortality by BMI is J-shaped, with elevated risk at low BMI as well as at high BMI, potentially reflecting frailty and underlying illness.

A future source remedy is an individual-level or suitably stratified mortality source such as the National Health Interview Survey linked mortality files, which carry smoking information and can support more granular, controlled mortality analysis. It would still require an approved actuarial study before replacing these judgment inputs.

`APPLICATION` deliberately does not collect exercise. Exercise is unknown at quote time and becomes observable through wellness enrolment, which is why its model coefficient can support renewal reassessment rather than initial quote collection. `RISK_FACTOR` also has no exercise column, so each model profile is marginalised using the staged valid-response shares of 77.0203 percent exercise yes and 22.9797 percent exercise no.

For each smoking and BMI profile, the initial mortality base is `mn * smoking_relative_risk * bmi_relative_risk`. For a disclosed-diabetes profile, mortality is that base multiplied by the age-sex diabetes relative risk. For a disclosed-no profile, residual risk is `marginalised_probability * 0.20`, and mortality is the base multiplied by `1 + residual_risk * (diabetes_relative_risk - 1)`. The 0.20 undiagnosed fraction is a named judgment input. It recognises that a probability of prevalent diabetes overstates the risk for someone who directly reports no diabetes.

`RISK_FACTOR.MortalityMultiplier` is a multiple of the SSA population baseline for its age band and gender. It is not an absolute mortality rate. This keeps the age and gender baseline in SSA and the relative profile effect in `RISK_FACTOR`.

There are two population-to-applicant calibration limitations. First, the SSA baseline already includes a population mix of smokers and people in every BMI band. Applying full external smoking and BMI relativities to that average baseline can overstate absolute profile levels. Second, an underwritten applicant pool has lower mortality than the general population, so use of the population SSA baseline creates the select mortality gap. The effects arise in different parts of the construction, profile relativity and population baseline. They do not numerically offset in this prototype: correcting either would generally lower the calculated premium. Neither is numerically corrected, so both remain visible limitations rather than untraceable adjustments.

## Rate construction

`BaseRate` is the premium per 1,000 of face amount. The formula is `1000 * SSA baseline mortality * MortalityMultiplier * 1.50 loading factor * product factor`. The loading factor covers expenses, reserves, and margin.

The Product table has no actuarial rate field or face amount. Its historical `AnnualizedPremium` is synthetic and is not used. Product factors are explicit judgment inputs: Products 1 and 2 use 1.00, Products 3 through 5 use 1.15 for longer level-term exposure, Products 6 through 10 use 1.35 for whole-life cash-value exposure, and Products 11 through 15 use 1.20 for universal-life exposure. The factors are not calibrated to force a market premium.

The resulting population-based premium can exceed an underwritten market quote. This is the select mortality gap. Underwritten policyholders are healthier than the SSA population, so a select-mortality adjustment is the actuarially correct future refinement.

## Wellness credit rule

Wellness activity records participation, but do not directly change a renewal premium. For an enrolled contract, the renewal credit is the arithmetic mean of positive `RISK_IMPROVEMENT.ImprovementPct` values whose `MeasureDate` is strictly before the renewal date. The result is rounded to two decimals and capped at 15.00 percent; a contract with no qualifying measured improvement receives zero. This is the same deterministic rule used by the synthetic transactional generator and lets the demo distinguish participation from a dated measurement.

## Operational limits and lineage

`DATA_REFRESH_RUN.StartedAt` and `CompletedAt` are `DATE` columns, not datetime columns. The run can therefore record its execution day but not intra-day duration. `SourceDatasets` stores the exact curated BRFSS, SSA, and WONDER filenames used by the refresh. The approved model-profile export is recorded in the run notes.

The six historical seed versions have no `RATE` rows, so their applications can retain a quoted version and historical premium without claiming a reproducible rate calculation. `APPLICATION.QuotedRateVersionID` is nullable for that historical case. Bound application premiums remain copies of synthetic historical `Contract.ModalPremium` values and are not reconstructed from the new rate book.

The local database now has eleven rate versions. Versions 7 through 10 were
legitimate refresh publications created during demonstration and testing runs on
2026-07-30. They share that effective date because the inherited
`RATE_VERSION` date columns store `DATE`, not `DATETIME`. The same-day dates are
a column-granularity artifact, not a refresh-pipeline defect. Version 11 is the
current active version.
