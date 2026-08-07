# Jingrui Feng (jf4446) - database systems project part 3 - brfss training frame dictionary

# BRFSS Training Frame Data Dictionary

The output artifact is `data/processed/brfss_training.parquet`. The model-feature list is `age_band_01` through `age_band_13`, `sex`, `smoking_status`, `exercise`, and `bmi`; `age_midpoint_years` is intentionally excluded from that list. The explicit one-hot age-band representation remains stable when the Parquet file is read back and is directly usable by scikit-learn.

| Column | Source BRFSS variable | Output dtype | Valid values or range | Transformation | Role |
|---|---|---|---|---|---|
| `diabetes_response` | `DIABETE4` | `int8` | 1, 3, 4 | Retains records after excluding 2, 7, and 9. | Auxiliary response provenance |
| `label` | `DIABETE4` | `Int8` | 0, 1, or null | 1 becomes 1 and 3 becomes 0; 4 is retained as null for the primary-label analysis. | Primary label |
| `label_sensitivity` | `DIABETE4` | `int8` | 0, 1 | 1 and 4 become 1; 3 becomes 0. | Sensitivity-analysis label |
| `age_band` | `_AGEG5YR` | `int8` | Codes 1–13 | Drops code 14 and retains the original band code. | Auxiliary reporting and rate-table join |
| `age_band_01` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 1 (ages 18–24); otherwise zero. | Model feature |
| `age_band_02` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 2 (ages 25–29); otherwise zero. | Model feature |
| `age_band_03` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 3 (ages 30–34); otherwise zero. | Model feature |
| `age_band_04` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 4 (ages 35–39); otherwise zero. | Model feature |
| `age_band_05` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 5 (ages 40–44); otherwise zero. | Model feature |
| `age_band_06` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 6 (ages 45–49); otherwise zero. | Model feature |
| `age_band_07` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 7 (ages 50–54); otherwise zero. | Model feature |
| `age_band_08` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 8 (ages 55–59); otherwise zero. | Model feature |
| `age_band_09` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 9 (ages 60–64); otherwise zero. | Model feature |
| `age_band_10` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 10 (ages 65–69); otherwise zero. | Model feature |
| `age_band_11` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 11 (ages 70–74); otherwise zero. | Model feature |
| `age_band_12` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 12 (ages 75–79); otherwise zero. | Model feature |
| `age_band_13` | `_AGEG5YR` | `int8` | 0 or 1 | One when `age_band` is 13 (ages 80–99). | Model feature |
| `age_midpoint_years` | `_AGEG5YR` | `float32` | 21, 27, 32, 37, 42, 47, 52, 57, 62, 67, 72, 77, 89.5 | Maps each retained age band to the codebook-derived interval midpoint; code 1 is 18–24 and code 13 is 80–99. | Auxiliary reporting and rate-table join |
| `sex` | `_SEX` | `string` | `male`, `female` | Maps 1 to `male` and 2 to `female`. | Model feature |
| `smoking_status` | `_SMOKER3` | `string` | `current`, `former`, `never` | Maps 1 and 2 to `current`, 3 to `former`, and 4 to `never`; drops 9. | Model feature |
| `exercise` | `_TOTINDA` | `string` | `yes`, `no` | Maps 1 to `yes` and 2 to `no`; drops 9. `EXERANY2` is not retained because its valid responses are redundant with this calculated variable. | Model feature |
| `bmi` | `_BMI5` | `float32` | 12.53–99.79 in the rebuilt frame | Drops nulls and divides the implied-decimal source value by 100. | Model feature |

## BMI band definition used outside the training frame

`BMIBand` is retained in the staged BRFSS record layer rather than in this
continuous-BMI training artifact. The source is the BRFSS calculated variable
`_BMI5CAT`, which applies the CDC and WHO category boundaries: `under` is BMI
below 18.5, `normal` is 18.5 inclusive to below 25.0, `over` is 25.0 inclusive
to below 30.0, and `obese` is 30.0 or higher. The lower bound is inclusive and
the upper bound is exclusive, so BMI 25.00 is `over`.

The staged `STG_BRFSS_RECORD` data verifies the boundaries: observed BMI ranges
are 12.53–18.49 for `under`, 18.50–24.99 for `normal`, 25.00–29.99 for `over`,
and 30.00–99.79 for `obese`. This explicit documentation is needed because the
web application is the first project component to derive a band from raw BMI.
