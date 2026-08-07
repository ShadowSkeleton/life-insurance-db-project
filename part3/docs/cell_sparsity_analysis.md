# Jingrui Feng (jf4446) - database systems project part 3 - brfss profile sparsity evidence

# BRFSS profile sparsity analysis

This analysis uses the 605 observed five-factor profiles in
`STG_BRFSS_RECORD`: AgeBand, Gender, SmokingStatus, BMIBand, and ExerciseFreq.
Records with a NULL in one of those fields or in DiabetesStatus are excluded,
which matches the corrected SQL summary population. DiabetesStatus is an
outcome dimension rather than a profile-key column, so these are records per
profile rather than records per outcome row.

| Statistic | Records per profile |
|---|---:|
| Minimum | 1 |
| 10th percentile | 2.0 |
| 25th percentile | 9.0 |
| Median | 35.0 |
| 75th percentile | 86.0 |
| 90th percentile | 221.2 |
| Maximum | 622 |

Of 605 observed profiles, 272, or 44.96%, contain fewer than 30 records. Thirty-four
profiles contain exactly one record. The five-factor vocabulary permits 624
theoretical profiles (13 age bands × 2 genders × 3 smoking states × 4 BMI bands
× 2 exercise states), so 19 possible profiles have zero observations.

The five sparsest non-empty profiles are shown below. Empirical diabetes
prevalence is the count of `DiabetesStatus = 'yes'` divided by the profile's
record count. The final column is the percentage-point change caused by adding
one diabetic record to the profile.

| AgeBand | Gender | SmokingStatus | BMIBand | ExerciseFreq | Records | Empirical prevalence | One additional diabetic case |
|---|---|---|---|---|---:|---:|---:|
| 18-24 | F | current | over | no | 1 | 0.0000 | 50.00 pp |
| 18-24 | M | former | obese | no | 1 | 0.0000 | 50.00 pp |
| 25-29 | F | former | under | no | 1 | 0.0000 | 50.00 pp |
| 25-29 | M | former | under | no | 1 | 0.0000 | 50.00 pp |
| 30-34 | F | current | under | no | 1 | 0.0000 | 50.00 pp |

An empirical rate based on a handful of records is unusable for pricing. In a
one-record profile, a single diabetic case changes the estimated prevalence by
50 percentage points, and even somewhat larger sparse profiles remain highly
sensitive to one respondent. A predictive model borrows strength across all
records and covariate combinations, allowing every profile, including a sparse
or unobserved one, to receive a more stable estimate. The pricing pipeline
therefore requires a model rather than a lookup table of empirical cell rates.
