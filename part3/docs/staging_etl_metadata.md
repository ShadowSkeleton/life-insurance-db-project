# Jingrui Feng (jf4446) - database systems project part 3 - staging etl scope

# Part 3 staging ETL scope

The staging loader retains all 50,000 curated BRFSS records at source grain in
`STG_BRFSS_RECORD`; model exclusions remain a separate training-frame step.
`STG_BRFSS` is generated inside SQL Server from those staged records.

NHANES is restricted to respondents with `RIDAGEYR >= 18`. This is an adult
life-insurance scope rule, not a data-quality exclusion: minors are not
potential applicants and the RISK_FACTOR vocabulary has no under-18 age band.

The NIDDK diabetes-prevalence and acute-complications CSVs remain data-lake
assets used as published-reference citations in the report. They are not
pipeline inputs and are intentionally not loaded into a staging table.

## WONDER cohort identifiers and pricing scope

The WONDER all-cause and diabetes exports pool 2018 through 2024. The inherited
`STG_MORTALITY` schema allows one integer SourceYear, so SourceYear is used as a
cohort identifier rather than a literal observation year: 2024 identifies the
2018--2024 cohort and 2023 identifies the midpoint of the 2022--2024 cohort.
SourceFile preserves each export's exact identity. The 2022--2024 cohort is the
pricing input, while the 2018--2024 cohort is retained as a lake asset for
comparison only. This matters because the diabetes-to-all-cause ratio is an
input to RISK_FACTOR and therefore can influence every quoted price.

The pooled window includes 2020 and 2021, when all-cause mortality was sharply
elevated and diabetes could have appeared more often as a contributing
condition. The older cohort is retained to quantify that concern against the
newer export rather than serving as a pricing source. WONDER's 2022--2024
diabetes export suppresses the female 1--4 row and disables total rows; staging
therefore accepts only sex-specific native rows and the comparison is limited to
the complete 15--24 through 85+ pricing groups.
