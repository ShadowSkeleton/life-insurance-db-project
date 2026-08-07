# Jingrui Feng (jf4446) - database systems project part 3 - training data quality notes

# Data Quality Notes

## Label prevalence and age composition

The primary-label training subset has a diabetes prevalence of 14.9%, above the roughly 11–12% prevalence for U.S. adults. The curated BRFSS sample is unweighted and visibly older than a population-representative adult distribution: the raw `_AGEG5YR` distribution is 3,309 respondents in code 1, 2,607 in code 2, 2,883 in code 3, 3,107 in code 4, 3,343 in code 5, 3,167 in code 6, 3,560 in code 7, 3,873 in code 8, 4,727 in code 9, 5,196 in code 10, 4,806 in code 11, 4,024 in code 12, 4,460 in code 13, and 938 in code 14 (unknown/refused). In particular, 23,213 of 50,000 sampled records are in age bands 60 and above (codes 9–13), and diabetes prevalence rises substantially with age.

Training proceeds without survey weights, which is standard when the goal is to learn conditional predictive relationships. The consequence here is a shifted base rate, not an automatic distortion of each conditional relationship. Calibration against the SSA period life table and the CDC WONDER exports is therefore required rather than optional; that subsequent step aligns model outputs with the intended population and mortality context.

## BMI missingness

The BRFSS source contains 4,631 rows with a null `_BMI5`, and the training-frame build drops those rows. This missingness is unlikely to be completely at random because a missing BMI can reflect refusal to report height or weight, and refusal plausibly correlates with higher weight. The dropped slice may therefore be higher risk than the retained sample, which would bias the estimated BMI effect toward zero.

No imputation is applied at this first-model stage. Retaining complete observed measurements provides a transparent baseline and avoids introducing an unvalidated model for a potentially informative missingness process. The limitation is documented so that later work can compare complete-case results with a deliberately justified imputation and missingness-indicator strategy.

## Activity-variable redundancy verification

The raw, pre-filter crosstab verifies that `_TOTINDA` is a deterministic derived version of `EXERANY2` for the relevant activity responses. Valid answers map one-to-one: 38,390 `EXERANY2=1` records map to `_TOTINDA=1`, and 11,454 `EXERANY2=2` records map to `_TOTINDA=2`; both valid off-diagonal cells are zero. The nonresponse coding is intentionally consolidated by the calculated variable: 103 `EXERANY2=7` records and 53 `EXERANY2=9` records both map to `_TOTINDA=9`.

| `EXERANY2` | `_TOTINDA=1` | `_TOTINDA=2` | `_TOTINDA=9` |
|---:|---:|---:|---:|
| 1 | 38,390 | 0 | 0 |
| 2 | 0 | 11,454 | 0 |
| 7 | 0 | 0 | 103 |
| 9 | 0 | 0 | 53 |

Using only the `_TOTINDA`-derived activity feature avoids perfect collinearity in a future logistic-regression model while retaining the calculated variable's consistent nonresponse handling.
