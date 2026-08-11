# Diabetes risk-stratification model summary

I trained reproducible BRFSS diabetes risk-stratification models with fixed seed 20260729. The primary analysis uses 41,681 labelled records after the prepared frame excludes pre-diabetes from the primary label. BRFSS is cross-sectional and self-reported, so this is concurrent risk stratification rather than incidence forecasting. The model is not a mortality model.

## Method and primary result

I used logistic regression for the rate-revision and product risk-assessment decision because its coefficients translate directly into rating factors. Age band 40-44 is the reference category. Female, never smoking, and exercise yes are the other reference levels. The held-out AUC is 0.765 and the Brier score is 0.113. At the default threshold, precision is 0.366, recall is 0.042, and F1 is 0.076.

I do not report accuracy. With roughly 14.9 percent diabetes prevalence, a model that predicts no diabetes for every applicant would appear about 85 percent accurate while making no useful pricing distinction. Calibration matters more than discrimination for this use because probabilities feed rate calculations directly. They need to be correct in absolute terms, not merely ranked correctly.

The statistically significant non-intercept coefficients are age_band_01, age_band_02, age_band_03, age_band_04, age_band_06, age_band_07, age_band_08, age_band_09, age_band_10, age_band_11, age_band_12, age_band_13, sex_male, smoking_current, smoking_former, exercise_no, bmi. The coefficient table includes standard errors, odds ratios, and 95 percent confidence intervals in `outputs/model/logistic_coefficients.csv`.

## Decision-tree comparison

I tuned tree depth with five-fold stratified cross-validation. The selected depth is 8, with cross-validation AUC 0.729 and held-out AUC 0.739. Logistic regression is retained as the primary candidate because a coefficient per risk factor is directly explainable in underwriting. A tree's threshold splits are harder to defend even if its discrimination is competitive.

## K-means segmentation

I standardized the encoded inputs before clustering so BMI and one-hot features contributed on comparable scales. The silhouette criterion selected k=8. The cluster profiles below use observed diabetes prevalence only for validation, not for fitting.

| cluster | cluster_name | size | size_percent | modal_age_band | modal_sex | modal_smoking_status | modal_exercise | mean_bmi | observed_diabetes_prevalence |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 35-39 male, never smoking, yes exercise | 2648 | 6.192 | 35-39 | male | never | yes | 29.226 | 0.042 |
| 1 | 50-54 male, never smoking, yes exercise | 9837 | 23.002 | 50-54 | male | never | yes | 28.541 | 0.129 |
| 2 | 60-64 female, never smoking, yes exercise | 4145 | 9.692 | 60-64 | female | never | yes | 29.167 | 0.213 |
| 3 | 80-99 female, never smoking, no exercise | 6373 | 14.902 | 80-99 | female | never | no | 30.554 | 0.260 |
| 4 | 75-79 female, never smoking, yes exercise | 3542 | 8.282 | 75-79 | female | never | yes | 28.049 | 0.245 |
| 5 | 30-34 male, never smoking, yes exercise | 2405 | 5.624 | 30-34 | male | never | yes | 28.808 | 0.030 |
| 6 | 18-24 male, never smoking, yes exercise | 2835 | 6.629 | 18-24 | male | never | yes | 25.886 | 0.012 |
| 7 | 65-69 female, never smoking, yes exercise | 10981 | 25.677 | 65-69 | female | never | yes | 27.896 | 0.132 |

These groups suggest differentiated product presentation and wellness outreach. Higher-BMI, low-exercise groups can receive wellness-program outreach, while lower-risk groups can be candidates for simpler product tiers. The groups are descriptive and are not an underwriting decision by themselves.

## Sparsity argument

The staging summary observes 605 of 624 possible profiles. Nineteen profiles have zero records, 34 have exactly one record, and 272 have fewer than 30 records. The sparse-profile comparison below shows why an empirical lookup is unstable.

| AgeBand | Gender | SmokingStatus | BMIBand | ExerciseFreq | Records | EmpiricalPrevalence | PredictedProbability |
|---|---|---|---|---|---|---|---|
| 18-24 | F | current | over | no | 1 | 0.0000 | 0.0179 |
| 18-24 | M | former | obese | no | 1 | 0.0000 | 0.0428 |
| 25-29 | F | former | under | no | 1 | 0.0000 | 0.0099 |
| 25-29 | M | former | under | no | 1 | 0.0000 | 0.0126 |
| 30-34 | F | current | under | no | 1 | 0.0000 | 0.0157 |

The selected zero-record profile has no empirical lookup result but still receives model probability 0.0081. A lookup table alone cannot price 19 of 624 possible profiles, about 3 percent.

## Pre-diabetes sensitivity

I refit the logistic model with 1,085 pre-diabetes records folded into the positive class through `label_sensitivity`. The largest absolute coefficient change is 0.2803. The coefficient signs remain stable across the primary and sensitivity fits. This measures the design decision that pre-diabetes maps to no in `RISK_FACTOR` because the lake has no source-traceable pre-diabetes mortality multiplier.

## External validation and fairness

The WONDER comparison uses the 2022-2024 cohort identified by `SourceYear = 2023`. It compares predicted diabetes prevalence with the diabetes-to-all-cause mortality ratio, so it is a directional rather than numerical check. Spearman correlations are F=0.595 and M=0.548. The SSA ordering check reports model non-decreasing by age for F=False and M=False. SSA mortality is non-decreasing for F=True and M=True. The model falls from age 75-79 to the open-ended 80-99 band for both sexes while SSA mortality continues to rise. I treat that failed monotonic check as a calibration finding for review, not as a reason to alter the source data or force a rate factor.

United States permissibility is jurisdiction-specific. Age, smoking, diabetes, and BMI are candidate rating inputs only where the company can show a sound actuarial basis and a valid rationale, then comply with the applicable state law and filing rules. Gender needs separate review because its use is restricted in some United States jurisdictions and prohibited for insurance pricing in the European Union. BMI can have different validity across populations and can act as a proxy for unobserved social and health conditions. The model uses an unweighted BRFSS sample, so probabilities reflect the sample rather than the United States population. The documented 4,631 missing BMI records and other exclusions form roughly 7,200 less-willing respondents rather than scattered noise, which can attenuate the estimated BMI relationship. Calibration and subgroup monitoring are therefore continuing controls.

Sex subgroup AUC:

| subgroup | rows | positive_rows | auc |
|---|---|---|---|
| female | 4207 | 587 | 0.761 |
| male | 4130 | 645 | 0.766 |

Age-band subgroup AUC:

| subgroup | rows | positive_rows | auc |
|---|---|---|---|
| 18-24 | 567 | 5 | 0.532 |
| 25-29 | 435 | 6 | 0.756 |
| 30-34 | 488 | 19 | 0.849 |
| 35-39 | 529 | 31 | 0.724 |
| 40-44 | 527 | 39 | 0.748 |
| 45-49 | 507 | 37 | 0.763 |
| 50-54 | 601 | 84 | 0.728 |
| 55-59 | 633 | 122 | 0.634 |
| 60-64 | 780 | 180 | 0.709 |
| 65-69 | 952 | 211 | 0.703 |
| 70-74 | 847 | 178 | 0.669 |
| 75-79 | 713 | 160 | 0.715 |
| 80-99 | 758 | 160 | 0.622 |
