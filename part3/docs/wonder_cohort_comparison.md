# Jingrui Feng (jf4446) - database systems project part 3 - wonder cohort comparison

# CDC WONDER mortality-cohort comparison

The local staging load retains two structurally identical CDC WONDER cohorts at
native ten-year age-group granularity. `SourceYear = 2024` is a cohort
identifier for the 2018--2024 pooled export, and `SourceYear = 2023` identifies
the midpoint of the 2022--2024 pooled export; neither value is asserted to be a
literal observation year. `SourceFile` preserves the exact all-cause and
diabetes export names. Crude rates were divided by 100,000 at staging, with no
interpolation.

All four extracts have the same ten-column header and the same native age-group
labels. WONDER disabled totals on the 2022--2024 diabetes export because of
suppression, so only sex-specific rows were loaded for both cohorts. The newer
diabetes extract has the expected one-row suppression at age 1--4 for females:
it has the male row but no female row. Every 15--24 through 85+ group has both
sexes in all four extracts. The comparison excludes the sub-15 groups because
they are outside adult life-insurance pricing scope and the suppressed row
would otherwise make that comparison incomplete.

Each percentage is the diabetes crude mortality rate divided by the all-cause
crude mortality rate for the same cohort, age group, and sex. The final column
is the newer 2022--2024 ratio minus the older 2018--2024 ratio, in percentage
points.

| Age group | Sex | 2018--2024 ratio (%) | 2022--2024 ratio (%) | Difference (percentage points) |
|---|---|---:|---:|---:|
| 15-24 | F | 1.1905 | 1.2195 | 0.0290 |
| 15-24 | M | 0.7306 | 0.6591 | -0.0715 |
| 25-34 | F | 2.0225 | 2.1940 | 0.1715 |
| 25-34 | M | 1.3692 | 1.4844 | 0.1152 |
| 35-44 | F | 2.7641 | 2.7847 | 0.0206 |
| 35-44 | M | 2.5271 | 2.4715 | -0.0556 |
| 45-54 | F | 3.6934 | 3.8264 | 0.1330 |
| 45-54 | M | 4.0293 | 4.1818 | 0.1525 |
| 55-64 | F | 3.8615 | 3.9177 | 0.0562 |
| 55-64 | M | 4.2726 | 4.4616 | 0.1890 |
| 65-74 | F | 3.8181 | 3.7949 | -0.0232 |
| 65-74 | M | 4.1540 | 4.1759 | 0.0219 |
| 75-84 | F | 2.9566 | 2.9358 | -0.0208 |
| 75-84 | M | 3.3561 | 3.4218 | 0.0657 |
| 85+ | F | 1.7901 | 1.7933 | 0.0032 |
| 85+ | M | 2.2328 | 2.2766 | 0.0438 |

The mean absolute cohort difference is 0.073272 percentage points. The largest
absolute difference is 0.189044 percentage points for males aged 55--64, where
the 2022--2024 ratio is 4.461620 percent and the 2018--2024 ratio is 4.272575
percent. The direction is mixed rather than systematic: the newer cohort is
higher in 12 of 16 adult age-sex cells and lower in 4. This falsifies the
original expectation that the COVID-era pooled window would inflate the
diabetes-to-all-cause ratio. The E10--E14 WONDER query counts underlying cause
of death, so COVID-19 deaths with diabetes as a comorbidity increase the
all-cause denominator but are not counted in the diabetes numerator. The
2018--2024 ratio is consequently generally depressed, not inflated, although
the measured distortion is small. The 2022--2024 cohort is the designated
pricing input; the older cohort is retained for comparison only.
