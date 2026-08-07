# Jingrui Feng (jf4446) - database systems project part 3 - diabetes risk model summary

# Diabetes risk-stratification model summary

I trained reproducible BRFSS diabetes risk-stratification models with fixed seed 20260729. The primary analysis uses 41,681 labelled records after the prepared frame excludes pre-diabetes from the primary label. BRFSS is cross-sectional and self-reported, so this is concurrent risk stratification rather than incidence forecasting. The model is not a mortality model.

## Method and primary result

I used logistic regression for the rate-revision and product risk-assessment decision because its coefficients translate directly into rating factors. Age band 40-44 is the reference category. Female, never smoking, and exercise yes are the other reference levels. The held-out AUC is 0.773 and the Brier score is 0.112. At the default threshold, precision is 0.508, recall is 0.051, and F1 is 0.093.

I use the model as a probability estimator, not as a yes-or-no classifier. Its continuous probability is a rating input, so the 0.5 classification threshold does not describe how the company uses it. AUC and Brier score are the operative measures. The Brier score of 0.112 improves on the 0.127 score from a constant base-rate predictor. I retain the threshold metrics because they document the fitted model, but they are not the decision criterion.

The model's pricing role is residual differentiation within the disclosed no-diabetes class. It does not supply all-cause mortality weights for smoking status or BMI. Its coefficients corroborate the direction and ordering of those diabetes-risk factors, while their mortality magnitudes come from documented external actuarial inputs in the refresh pipeline. A disclosed diabetes answer is handled by the external mortality construction, not overridden by the model.

I do not report accuracy. With roughly 14.9 percent diabetes prevalence, a model that predicts no diabetes for every applicant would appear about 85 percent accurate while making no useful pricing distinction. Calibration matters more than discrimination for this use because probabilities feed rate calculations directly. They need to be correct in absolute terms, not merely ranked correctly.

The statistically significant non-intercept coefficients are age_band_01, age_band_02, age_band_03, age_band_04, age_band_06, age_band_07, age_band_08, age_band_09, age_band_10, age_band_11, age_band_12, age_band_13, sex_male, smoking_current, smoking_former, exercise_no, bmi. The coefficient table includes standard errors, odds ratios, and 95 percent confidence intervals in `outputs/model/logistic_coefficients.csv`.

## Decision-tree comparison

I tuned tree depth with five-fold stratified cross-validation. The selected depth is 8, with cross-validation AUC 0.738 and held-out AUC 0.755. Logistic regression is retained as the primary candidate because a coefficient per risk factor is directly explainable in underwriting. A tree's threshold splits are harder to defend even if its discrimination is competitive.

## K-means segmentation

I standardized the encoded inputs before clustering so BMI and one-hot features contributed on comparable scales. The silhouette criterion selected k=8. The cluster profiles below use observed diabetes prevalence only for validation, not for fitting.

| cluster | cluster_name | size | size_percent | modal_age_band | modal_sex | modal_smoking_status | modal_exercise | mean_bmi | observed_diabetes_prevalence |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 35-39 male, never smoking, yes exercise | 2648 | 6.192 | 35-39 | male | never | yes | 29.226 | 0.042 |
| 1 | 50-54 male, never smoking, yes exercise | 9837 | 23.002 | 50-54 | male | never | yes | 28.541 | 0.133 |
| 2 | 60-64 female, never smoking, yes exercise | 4145 | 9.692 | 60-64 | female | never | yes | 29.167 | 0.213 |
| 3 | 80-99 female, never smoking, no exercise | 6373 | 14.902 | 80-99 | female | never | no | 30.554 | 0.262 |
| 4 | 75-79 female, never smoking, yes exercise | 3542 | 8.282 | 75-79 | female | never | yes | 28.049 | 0.245 |
| 5 | 30-34 male, never smoking, yes exercise | 2405 | 5.624 | 30-34 | male | never | yes | 28.808 | 0.030 |
| 6 | 18-24 male, never smoking, yes exercise | 2835 | 6.629 | 18-24 | male | never | yes | 25.886 | 0.012 |
| 7 | 65-69 female, never smoking, yes exercise | 10981 | 25.677 | 65-69 | female | never | yes | 27.896 | 0.132 |

These groups suggest differentiated product presentation and wellness outreach. Higher-BMI, low-exercise groups can receive wellness-program outreach, while lower-risk groups can be candidates for simpler product tiers. The groups are descriptive and are not an underwriting decision by themselves.

K-means uses Euclidean distance, which treats all pairs of one-hot categories as equidistant. That is a poor fit for this mostly categorical data and is the main reason the silhouette score is only 0.221. K-modes or Gower distance would suit mixed data better. I include K-means as an optional complementary segmentation method because its clusters are interpretable, while stating the limitation directly.

## Sparsity argument

The staging summary observes 605 of 624 possible profiles. Nineteen profiles have zero records, 34 have exactly one record, and 272 have fewer than 30 records. The sparse-profile comparison below shows why an empirical lookup is unstable.

| AgeBand | Gender | SmokingStatus | BMIBand | ExerciseFreq | Records | EmpiricalPrevalence | PredictedProbability |
|---|---|---|---|---|---|---|---|
| 18-24 | F | current | over | no | 1 | 0.0000 | 0.0175 |
| 18-24 | M | former | obese | no | 1 | 0.0000 | 0.0433 |
| 25-29 | F | former | under | no | 1 | 0.0000 | 0.0100 |
| 25-29 | M | former | under | no | 1 | 0.0000 | 0.0130 |
| 30-34 | F | current | under | no | 1 | 0.0000 | 0.0154 |
| 40-44 | M | former | under | no | 1 | 1.0000 | 0.0449 |
| 55-59 | F | never | under | no | 1 | 1.0000 | 0.0898 |

The final two rows show the other failure of a lookup table. One diabetic response in one record would produce a 100 percent empirical prevalence even though the fitted probabilities are 4.49 and 8.98 percent. The selected zero-record profile has no empirical lookup result but still receives model probability 0.0080. A lookup table alone cannot price 19 of 624 possible profiles, about 3 percent.

## Pre-diabetes sensitivity

I refit the logistic model with 1,085 pre-diabetes records folded into the positive class through `label_sensitivity`. The largest absolute coefficient change is 0.2932. The coefficient signs remain stable across the primary and sensitivity fits. This measures the design decision that pre-diabetes maps to no in `RISK_FACTOR` because the lake has no source-traceable pre-diabetes mortality multiplier.

## External validation and fairness

The WONDER comparison uses the 2022-2024 cohort identified by `SourceYear = 2023`. It compares predicted diabetes prevalence with the diabetes-to-all-cause mortality ratio, so it is a directional rather than numerical check. Spearman correlations are F=0.595 and M=0.548. They are positive and directionally consistent, but eight age groups cannot support a significance claim because the approximate 0.05 critical value is 0.74. I report them as directional evidence only.

The model probability declines from 75-79 to the open-ended 80-99 band for both sexes while SSA mortality continues to rise. This is expected epidemiology rather than a model defect. Survivorship means people with diabetes can die earlier, leaving a healthier surviving population above age 80. Diabetes can also be underdiagnosed in the very old, and the open-ended 80-99 band mixes twenty years of substantially different ages. Prevalence and mortality are different quantities, so they need not move together at the oldest ages.

This result validates the source separation in the design. SSA supplies absolute mortality, while the model supplies relative differentiation rather than the mortality baseline. The same pattern helps explain the subgroup AUC of 0.652 for age 80-99 compared with 0.803 for age 35-39. The oldest band is the hardest group to discriminate for the same survivorship and aggregation reasons, as shown in the fairness results below.

United States permissibility is jurisdiction-specific. Age, smoking, diabetes, and BMI are candidate rating inputs only where the company can show a sound actuarial basis and a valid rationale, then comply with the applicable state law and filing rules. Gender needs separate review because its use is restricted in some United States jurisdictions and prohibited for insurance pricing in the European Union. BMI can have different validity across populations and can act as a proxy for unobserved social and health conditions. The model uses an unweighted BRFSS sample, so probabilities reflect the sample rather than the United States population. The documented 4,631 missing BMI records and other exclusions form roughly 7,200 less-willing respondents rather than scattered noise, which can attenuate the estimated BMI relationship. Calibration and subgroup monitoring are therefore continuing controls.

Sex subgroup AUC:

| subgroup | rows | positive_rows | auc |
|---|---|---|---|
| female | 4226 | 613 | 0.771 |
| male | 4111 | 630 | 0.777 |

Age-band subgroup AUC:

| subgroup | rows | positive_rows | auc |
|---|---|---|---|
| 18-24 | 599 | 6 | 0.752 |
| 25-29 | 430 | 6 | 0.736 |
| 30-34 | 471 | 11 | 0.776 |
| 35-39 | 514 | 24 | 0.803 |
| 40-44 | 583 | 41 | 0.708 |
| 45-49 | 537 | 56 | 0.663 |
| 50-54 | 558 | 94 | 0.730 |
| 55-59 | 669 | 121 | 0.692 |
| 60-64 | 813 | 174 | 0.688 |
| 65-69 | 885 | 210 | 0.686 |
| 70-74 | 843 | 179 | 0.716 |
| 75-79 | 690 | 169 | 0.717 |
| 80-99 | 745 | 152 | 0.652 |
