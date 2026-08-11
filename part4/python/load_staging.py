# Jingrui Feng (jf4446) - database systems project part 3 - local staging data loader
"""Load curated health data into the local LifeInsuranceP3 staging layer.

No random operation is used.  The default load date is fixed to the execution
date of this reproducible project run and may be overridden explicitly.

BRFSS record recodes mirror ``build_training_frame.py``: source nonresponse
codes are retained at staging grain as NULL recodes.  STG_BRFSS is then
populated by the SQL ``GROUP BY`` in ``sql/load/load_staging_local.sql``.
STG_BRFSS uses the five factor columns as its profile key and DiabetesStatus as
an outcome dimension. Its PrevalenceRate is therefore
``P(DiabetesStatus | profile)``; outcome-row rates sum to 1.0 within a profile.

NHANES is deliberately limited to RIDAGEYR >= 18: minors are outside adult
life-insurance applicant scope and have no RISK_FACTOR age band.  The official
DIQ_L codebook maps DIQ010 1/2/3/7/9 to yes/no/borderline/refused/unknown.

SSA supplies absolute mortality.  Each age-band rate and life expectancy is a
lives-weighted average of single-year values.  WONDER supplies diabetes and
all-cause ratio inputs at native ten-year group-code granularity; its crude
rates are divided by 100,000.  The downstream design assumes that the
diabetes-to-all-cause ratio is constant within a WONDER ten-year group while
SSA retains the absolute, single-year-derived BRFSS bands.  SourceYear is a
cohort identifier for the two pooled WONDER exports: 2024 identifies the
2018--2024 cohort and 2023 identifies the 2022--2024 midpoint cohort.
"""

from __future__ import annotations

import argparse
import csv
import os
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
import shutil
import subprocess
import sys


PART4_ROOT = Path(__file__).resolve().parents[1]
PART3_ROOT = Path("/Users/jingrui_feng/Desktop/Summer2026/DB/project/part3")
CURATED_DIR = PART3_ROOT / "data" / "curated"
OUTPUT_DIR = PART4_ROOT / "data" / "processed" / "staging_load"
SQL_LOAD_FILE = PART3_ROOT / "sql" / "load" / "load_staging_local.sql"
ENV_FILE = PART3_ROOT / ".env"
DEFAULT_LOAD_DATE = "2026-07-27"
DEFAULT_CONTAINER = "dbsys-p3-mssql"
CONTAINER_STAGE_DIR = "/tmp/dbsys-p3-staging"

AGE_BANDS = (
    (18, 24, "18-24"), (25, 29, "25-29"), (30, 34, "30-34"),
    (35, 39, "35-39"), (40, 44, "40-44"), (45, 49, "45-49"),
    (50, 54, "50-54"), (55, 59, "55-59"), (60, 64, "60-64"),
    (65, 69, "65-69"), (70, 74, "70-74"), (75, 79, "75-79"),
    (80, 99, "80-99"),
)
BRFSS_AGE_CODES = {index + 1: label for index, (_, _, label) in enumerate(AGE_BANDS)}
BRFSS_AGE_CODES[13] = "80-99"
BRFSS_GENDER = {1: "M", 2: "F"}
BRFSS_SMOKING = {1: "current", 2: "current", 3: "former", 4: "never"}
BRFSS_DIABETES = {1: "yes", 2: "gest", 3: "no", 4: "pre"}
BRFSS_BMI_BAND = {1: "under", 2: "normal", 3: "over", 4: "obese"}
BRFSS_EXERCISE = {1: "yes", 2: "no"}
NHANES_DIQ010 = {1: "yes", 2: "no", 3: "borderline", 7: "refused", 9: "unknown"}


def parse_env(path: Path) -> dict[str, str]:
    """Read the gitignored local connection settings without printing them."""
    values: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
    return values


def as_int(value: str | None) -> int | None:
    if value is None or value.strip() == "":
        return None
    try:
        numeric = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Non-numeric source code: {value!r}") from error
    if numeric != numeric.to_integral_value():
        raise ValueError(f"Non-integral source code: {value!r}")
    return int(numeric)


def as_decimal(value: str | None, places: str | None = None) -> Decimal | None:
    if value is None or value.strip() == "":
        return None
    try:
        result = Decimal(value)
    except InvalidOperation as error:
        raise ValueError(f"Non-numeric source value: {value!r}") from error
    return result.quantize(Decimal(places), rounding=ROUND_HALF_UP) if places else result


def as_age(value: str | None) -> int | None:
    """Read NHANES integer ages, treating the observed near-zero token as age 0."""
    if value is None or value.strip() == "":
        return None
    numeric = as_decimal(value)
    if Decimal(0) <= numeric < Decimal(1):
        return 0
    if numeric != numeric.to_integral_value():
        raise ValueError(f"Non-integral age value: {value!r}")
    return int(numeric)


def age_band(age: int | None) -> str | None:
    if age is None:
        return None
    for lower, upper, label in AGE_BANDS:
        if lower <= age <= upper:
            return label
    return None


def clean(value: str | None) -> str | None:
    return value if value not in (None, "") else None


def write_csv(path: Path, headers: list[str], rows: list[list[object | None]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow(["" if value is None else value for value in row])
    if b'"' in path.read_bytes():
        raise ValueError(f"Generated staging file has quoted fields and cannot use the validated plain bulk parser: {path.name}")


def build_brfss(load_date: str, source: Path) -> tuple[list[list[object | None]], dict[str, Counter[str]]]:
    with source.open(newline="", encoding="utf-8-sig") as handle:
        raw_rows = list(csv.DictReader(handle))
    if len(raw_rows) != 50_000:
        raise ValueError(f"Expected 50,000 BRFSS records; found {len(raw_rows):,}")

    recoded: list[list[object | None]] = []
    counters: dict[str, Counter[str]] = defaultdict(Counter)
    for record_id, raw in enumerate(raw_rows, start=1):
        age = BRFSS_AGE_CODES.get(as_int(raw["_AGEG5YR"]))
        gender = BRFSS_GENDER.get(as_int(raw["_SEX"]))
        smoking = BRFSS_SMOKING.get(as_int(raw["_SMOKER3"]))
        diabetes = BRFSS_DIABETES.get(as_int(raw["DIABETE4"]))
        bmi_band = BRFSS_BMI_BAND.get(as_int(raw["_BMI5CAT"]))
        exercise = BRFSS_EXERCISE.get(as_int(raw["_TOTINDA"]))
        bmi_raw = as_decimal(raw["_BMI5"])
        bmi_value = (bmi_raw / Decimal(100)).quantize(Decimal("0.01")) if bmi_raw is not None else None
        values = {
            "AgeBand": age, "Gender": gender, "SmokingStatus": smoking,
            "DiabetesStatus": diabetes, "BMIBand": bmi_band,
            "ExerciseFreq": exercise,
        }
        for column, value in values.items():
            counters[column][value or "<NULL>"] += 1
        recoded.append([
            record_id, 2024, age, gender, smoking, diabetes, bmi_band, exercise,
            bmi_value, load_date, source.name,
        ])
    for column, values in counters.items():
        if any(len(value) > 10 for value in values if value != "<NULL>"):
            raise ValueError(f"A BRFSS value exceeds VARCHAR(10) in {column}: {values}")
    return recoded, counters


def build_nhanes(load_date: str) -> tuple[list[list[object | None]], dict[str, int]]:
    source = CURATED_DIR / "nhanes_2021_2023_diabetes_body_measures.csv"
    with source.open(newline="", encoding="utf-8-sig") as handle:
        raw_rows = list(csv.DictReader(handle))
    if len(raw_rows) != 11_933:
        raise ValueError(f"Expected 11,933 NHANES rows; found {len(raw_rows):,}")

    retained: list[list[object | None]] = []
    excluded = 0
    observed_ages: list[int] = []
    for raw in raw_rows:
        age = as_age(raw["RIDAGEYR"])
        if age is None or age < 18:
            excluded += 1
            continue
        band = age_band(age)
        if band is None:
            raise ValueError(f"Adult NHANES age has no configured BRFSS band: {age}")
        gender = BRFSS_GENDER.get(as_int(raw["RIAGENDR"]))
        if gender is None:
            raise ValueError(f"NHANES RIAGENDR is not mappable for retained row: {raw['RIAGENDR']!r}")
        bmi = as_decimal(raw["BMXBMI"], "0.01")
        retained.append([
            len(retained) + 1, "2021-2023", band, gender,
            NHANES_DIQ010.get(as_int(raw["DIQ010"])), bmi, load_date, source.name,
        ])
        observed_ages.append(age)
    return retained, {"source_rows": len(raw_rows), "excluded_under_18": excluded,
                      "retained": len(retained), "max_age": max(observed_ages)}


def build_ssa_mortality(load_date: str, start_id: int) -> tuple[list[list[object | None]], list[dict[str, object]]]:
    source = CURATED_DIR / "ssa_period_life_table_2023.csv"
    with source.open(newline="", encoding="utf-8-sig") as handle:
        records = list(csv.DictReader(handle))
    rows: list[list[object | None]] = []
    results: list[dict[str, object]] = []
    for gender, lives_column, probability_column, expectancy_column in (
        ("M", "male_lives", "male_death_probability", "male_life_expectancy"),
        ("F", "female_lives", "female_death_probability", "female_life_expectancy"),
    ):
        for lower, upper, label in AGE_BANDS:
            band_rows = [row for row in records if lower <= as_int(row["age"]) <= upper]
            total_lives = sum(as_decimal(row[lives_column]) for row in band_rows)
            mortality = sum(as_decimal(row[lives_column]) * as_decimal(row[probability_column]) for row in band_rows) / total_lives
            expectancy = sum(as_decimal(row[lives_column]) * as_decimal(row[expectancy_column]) for row in band_rows) / total_lives
            mortality = mortality.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
            expectancy = expectancy.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            row_id = start_id + len(rows)
            rows.append([row_id, 2023, label, gender, "BASELINE", mortality, expectancy, load_date, source.name])
            results.append({"gender": gender, "age_band": label, "mortality_rate": str(mortality), "life_expectancy": str(expectancy)})
    return rows, results


WONDER_COHORTS = (
    (2024, "wonder_all_by_age_sex.tsv", "wonder_diabetes_by_age_sex.tsv"),
    (2023, "wonder_all_by_age_sex_2022_2024.tsv", "wonder_diabetes_by_age_sex_2022_2024.tsv"),
)
PRICING_WONDER_GROUPS = ("15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+")


def read_wonder(file_name: str) -> tuple[list[str], list[dict[str, str]]]:
    with (CURATED_DIR / file_name).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        return reader.fieldnames or [], list(reader)


def validate_wonder_structure() -> dict[str, object]:
    """Fail closed if the four WONDER extracts cannot support cohort comparison."""
    source: dict[str, tuple[list[str], list[dict[str, str]]]] = {}
    for _, all_file, diabetes_file in WONDER_COHORTS:
        source[all_file] = read_wonder(all_file)
        source[diabetes_file] = read_wonder(diabetes_file)
    headers = {tuple(headers) for headers, _ in source.values()}
    if len(headers) != 1:
        raise ValueError("WONDER cohort headers differ; refusing a confounded comparison")

    group_labels: dict[str, set[str]] = {}
    sex_by_group: dict[str, dict[str, set[str]]] = {}
    for file_name, (_, records) in source.items():
        group_labels[file_name] = {
            row["Ten-Year Age Groups Code"] for row in records
            if row.get("Sex Code") in {"F", "M"}
        }
        sex_by_group[file_name] = {
            group: {row["Sex Code"] for row in records
                    if row.get("Ten-Year Age Groups Code") == group and row.get("Sex Code") in {"F", "M"}}
            for group in group_labels[file_name]
        }
    if group_labels[WONDER_COHORTS[0][1]] != group_labels[WONDER_COHORTS[1][1]]:
        raise ValueError("WONDER all-cause age-group labels differ between cohorts")
    if group_labels[WONDER_COHORTS[0][2]] != group_labels[WONDER_COHORTS[1][2]]:
        raise ValueError("WONDER diabetes age-group labels differ between cohorts")
    for file_name, groups in sex_by_group.items():
        for group in PRICING_WONDER_GROUPS:
            if groups.get(group) != {"F", "M"}:
                raise ValueError(f"WONDER {file_name} lacks both sexes for pricing group {group}")
    if sex_by_group["wonder_diabetes_by_age_sex_2022_2024.tsv"].get("1-4") != {"M"}:
        raise ValueError("Expected 1-4 female suppression was not observed in the 2022-2024 diabetes export")
    return {
        "headers": list(next(iter(headers))),
        "suppressed_1_4_female": True,
        "pricing_groups_verified": list(PRICING_WONDER_GROUPS),
    }


def build_wonder_mortality(load_date: str, start_id: int) -> tuple[list[list[object | None]], dict[str, object]]:
    structure = validate_wonder_structure()
    rows: list[list[object | None]] = []
    minimum_nonzero: Decimal | None = None
    loaded_by_cohort: Counter[str] = Counter()
    zero_source_rates = 0
    for cohort_year, all_file, diabetes_file in WONDER_COHORTS:
        for file_name, flag in ((all_file, "ALLCAUSE"), (diabetes_file, "DIABETES")):
            _, source_rows = read_wonder(file_name)
            for raw in source_rows:
                gender = raw.get("Sex Code")
                group_code = raw.get("Ten-Year Age Groups Code")
                crude_rate = raw.get("Crude Rate")
                # Sex-specific rows only: WONDER totals may be absent when
                # suppression disables them and are never inputs to pricing.
                if gender not in {"M", "F"} or not group_code or crude_rate in (None, "", "Not Applicable"):
                    continue
                if len(group_code) > 10:
                    raise ValueError(f"WONDER native age-group code exceeds VARCHAR(10): {group_code!r}")
                normalized = (as_decimal(crude_rate) / Decimal(100_000)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
                if normalized == 0:
                    zero_source_rates += 1
                else:
                    minimum_nonzero = normalized if minimum_nonzero is None else min(minimum_nonzero, normalized)
                rows.append([
                    start_id + len(rows), cohort_year, group_code, gender, flag, normalized,
                    None, load_date, file_name,
                ])
                loaded_by_cohort[f"{cohort_year}_{flag}"] += 1
    if minimum_nonzero is None:
        raise ValueError("No non-zero WONDER mortality rate survived normalization")
    return rows, {"loaded_by_cohort": dict(loaded_by_cohort), "minimum_nonzero_rate": str(minimum_nonzero),
                  "source_zero_rate_rows": zero_source_rates, **structure}


def run_command(command: list[str]) -> None:
    subprocess.run(command, check=True)


def load_local(container: str, env: dict[str, str], output_dir: Path, sql_load_file: Path) -> None:
    run_command(["docker", "exec", container, "mkdir", "-p", CONTAINER_STAGE_DIR])
    for path in sorted(output_dir.glob("STG_*.csv")):
        run_command(["docker", "cp", str(path), f"{container}:{CONTAINER_STAGE_DIR}/{path.name}"])
    run_command(["docker", "cp", str(sql_load_file), f"{container}:{CONTAINER_STAGE_DIR}/load_staging_local.sql"])
    if env.get("MSSQL_SA_PASSWORD"):
        command = [
            "docker", "exec", container, "/opt/mssql-tools18/bin/sqlcmd", "-C",
            "-S", "localhost", "-U", env["MSSQL_USER"], "-P", env["MSSQL_SA_PASSWORD"],
            "-d", env["MSSQL_DATABASE"], "-b", "-i", f"{CONTAINER_STAGE_DIR}/load_staging_local.sql",
        ]
    else:
        command = [
            "docker", "exec", container, "sh", "-c",
            'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" /opt/mssql-tools18/bin/sqlcmd '
            f"-C -S localhost -U sa -d LifeInsuranceP3 -b -i {CONTAINER_STAGE_DIR}/load_staging_local.sql",
        ]
    run_command(command)


def main() -> None:
    global CURATED_DIR
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--load-date", default=DEFAULT_LOAD_DATE, help="ISO date stored as LoadDate (default: %(default)s)")
    parser.add_argument("--container", default=DEFAULT_CONTAINER, help="Local SQL Server Docker container")
    parser.add_argument("--brfss-source", type=Path, default=CURATED_DIR / "brfss_2024_life_risk_sample_50000.csv")
    parser.add_argument("--curated-dir", type=Path, default=CURATED_DIR, help="Directory for NHANES, SSA, and WONDER sources")
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--sql-load-file", type=Path, default=SQL_LOAD_FILE)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args()
    date.fromisoformat(args.load_date)

    CURATED_DIR = args.curated_dir
    args.output_dir.mkdir(parents=True, exist_ok=True)
    brfss_rows, brfss_counts = build_brfss(args.load_date, args.brfss_source)
    nhanes_rows, nhanes_metrics = build_nhanes(args.load_date)
    ssa_rows, ssa_results = build_ssa_mortality(args.load_date, start_id=1)
    wonder_rows, wonder_metrics = build_wonder_mortality(args.load_date, start_id=len(ssa_rows) + 1)
    mortality_rows = ssa_rows + wonder_rows

    write_csv(args.output_dir / "STG_BRFSS_RECORD.csv", [
        "StgBRFSSRecordID", "SourceYear", "AgeBand", "Gender", "SmokingStatus",
        "DiabetesStatus", "BMIBand", "ExerciseFreq", "BMIValue", "LoadDate", "SourceFile",
    ], brfss_rows)
    write_csv(args.output_dir / "STG_NHANES.csv", [
        "StgNHANESID", "SourceCycle", "AgeBand", "Gender", "DiabetesBiomarker",
        "BMIMeasured", "LoadDate", "SourceFile",
    ], nhanes_rows)
    write_csv(args.output_dir / "STG_MORTALITY.csv", [
        "StgMortalityID", "SourceYear", "AgeBand", "Gender", "ConditionFlag",
        "MortalityRate", "LifeExpectancy", "LoadDate", "SourceFile",
    ], mortality_rows)

    load_local(args.container, parse_env(args.env_file), args.output_dir, args.sql_load_file)
    print(f"Loaded STG_BRFSS_RECORD source rows: {len(brfss_rows):,}")
    print(f"Loaded STG_NHANES retained rows: {len(nhanes_rows):,}; excluded under 18: {nhanes_metrics['excluded_under_18']:,}")
    print(f"Loaded STG_MORTALITY rows: {len(mortality_rows):,}")
    print("BRFSS recoded value counts:")
    for column, counts in brfss_counts.items():
        print(f"  {column}: {dict(sorted(counts.items()))}")
    print(f"NHANES maximum retained RIDAGEYR: {nhanes_metrics['max_age']}")
    print(f"WONDER minimum non-zero normalized rate: {wonder_metrics['minimum_nonzero_rate']}")
    print("SSA weighted results:")
    for result in ssa_results:
        print(f"  {result['gender']} {result['age_band']}: {result['mortality_rate']} (LE {result['life_expectancy']})")


if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
