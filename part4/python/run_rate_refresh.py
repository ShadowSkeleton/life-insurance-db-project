# Jingrui Feng (jf4446) - database systems project part 3 - rate book refresh publisher
"""Publish a reproducible local SQL Server rate book from staged health data.

This script has no random operation.  Its fixed project seed is 20260730.
It is deliberately parameterised and re-runnable.  Each successful execution
creates a new DATA_REFRESH_RUN, RISK_FACTOR set, RATE_VERSION, and RATE set in
one SQL Server transaction.  A failed transaction is rolled back and a separate
failed-run record is written afterwards.

Relative-risk derivation
------------------------
Let p be diagnosed-diabetes prevalence, m the SSA population mortality rate,
mn non-diabetic mortality, md diabetic mortality, and f the WONDER ratio of
underlying diabetes deaths to all-cause deaths.  The specified assumptions are

    m = p * md + (1 - p) * mn
    f * m = p * (md - mn)

Writing RR = md / mn and solving the two equations gives

    RR = (f * p - p - f) / (p * (f - 1))

RISK_FACTOR.MortalityMultiplier is a multiple of m, the SSA population baseline
for the row's AgeBand and Gender.  It is not an absolute mortality rate.  The
external smoking and BMI relativities are applied to non-diabetic mortality
before diabetes composition.  For a diagnosed-diabetes row the numerator is
[mn * smoking_RR * bmi_RR * RR] / m.  For a disclosed-no row it is
[mn * smoking_RR * bmi_RR * (1 + residual * (RR - 1))] / m, where residual is
the model probability after marginalising exercise multiplied by the
undiagnosed fraction.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import shlex
import shutil
import sys
import subprocess
import tempfile
from collections import defaultdict
from dataclasses import asdict
from datetime import date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from retraining import run_retraining
import pymssql


SEED = 20260730
DEFAULT_UNDIAGNOSED_FRACTION = Decimal("0.20")
DEFAULT_LOADING_FACTOR = Decimal("1.50")
EFFECTIVE_DATE = date.today()
# SSA is a separate fixed baseline source, not a mortality-cohort selector.
SSA_BASELINE_SOURCE_YEAR = 2023
DEFAULT_WONDER_COHORT_SOURCE_YEAR = 2023
CONTAINER = "dbsys-p3-mssql"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
# External all-cause mortality judgment inputs.  Jha et al., NEJM 2013,
# DOI 10.1056/NEJMsa1211128, found current-smoking all-cause hazards of about
# 2.8 to 3.0 versus never smoking in U.S. adults.  2.30 is a conservative
# underwriting input, not a directly estimated lake value.  Former-smoker risk
# varies strongly by age and time since cessation; 1.30 is a documented
# judgment input consistent with the risk reduction after cessation in the
# 2020 U.S. Surgeon General report, https://www.cdc.gov/tobacco-surgeon-general-reports/reports/2020-smoking-cessation/index.html.
SMOKING_RR = {
    "never": Decimal("1.00"), "former": Decimal("1.30"), "current": Decimal("2.30"),
}
# External all-cause mortality judgment inputs.  The Global BMI Mortality
# Collaboration, Lancet 2016, DOI 10.1016/S0140-6736(16)30175-1, reports the
# lowest all-cause mortality around BMI 20 to under 25 and elevated mortality
# on both sides of that range.  These broad BRFSS-band values are conservative
# category proxies rather than estimates derived from the project lake.
BMI_RR = {
    "normal": Decimal("1.00"), "under": Decimal("1.20"),
    "over": Decimal("1.05"), "obese": Decimal("1.35"),
}
AGE_BANDS = (
    "18-24", "25-29", "30-34", "35-39", "40-44", "45-49", "50-54",
    "55-59", "60-64", "65-69", "70-74", "75-79", "80-99",
)
WONDER_AGE_GROUP = {
    "18-24": "15-24", "25-29": "25-34", "30-34": "25-34",
    "35-39": "35-44", "40-44": "35-44", "45-49": "45-54",
    "50-54": "45-54", "55-59": "55-64", "60-64": "55-64",
    "65-69": "65-74", "70-74": "65-74", "75-79": "75-84",
    "80-99": "85+",
}
# These are documented judgment inputs.  They distinguish product structures
# without deriving anything from Product.AnnualizedPremium, which is synthetic.
PRODUCT_FACTORS = {
    1: Decimal("1.00"), 2: Decimal("1.00"),
    3: Decimal("1.15"), 4: Decimal("1.15"), 5: Decimal("1.15"),
    6: Decimal("1.35"), 7: Decimal("1.35"), 8: Decimal("1.35"),
    9: Decimal("1.35"), 10: Decimal("1.35"),
    11: Decimal("1.20"), 12: Decimal("1.20"), 13: Decimal("1.20"),
    14: Decimal("1.20"), 15: Decimal("1.20"),
}
PART4_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = PART4_ROOT
PROFILE_PATH = PART4_ROOT / "outputs" / "model" / "predicted_risk_by_profile.csv"
CURATED_DIR = PART4_ROOT.parent / "part3" / "data" / "curated"
OUTPUT_DIR = PART4_ROOT / "outputs" / "rate_refresh"
PART4_ENV_FILE = Path(os.environ.get("PART4_ENV_FILE", str(PART4_ROOT / ".env")))
COMMON_CURATED_SOURCES = (
    "brfss_2024_life_risk_sample_50000.csv",
    "ssa_period_life_table_2023.csv",
)
WONDER_COHORT_FILES = {
    2023: ("wonder_all_by_age_sex_2022_2024.tsv", "wonder_diabetes_by_age_sex_2022_2024.tsv"),
    2024: ("wonder_all_by_age_sex.tsv", "wonder_diabetes_by_age_sex.tsv"),
}


def decimal(value: str | Decimal | float | int) -> Decimal:
    return Decimal(str(value))


def q3(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def q2(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def settings(*, azure: bool = False) -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(PROJECT_ROOT / ".env").items() if value}
    # Azure Functions supplies application settings through process environment.
    # Environment values deliberately override a developer's local .env file.
    values.update({key: value for key, value in os.environ.items() if value})
    required = (
        {"AZURE_SQL_SERVER", "AZURE_SQL_DATABASE", "AZURE_SQL_USER", "AZURE_SQL_PASSWORD"}
        if azure else {"MSSQL_SA_PASSWORD", "MSSQL_USER", "MSSQL_DATABASE"}
    )
    missing = sorted(required - values.keys())
    if missing and azure:
        raise ValueError(f".env is missing Azure SQL settings: {', '.join(missing)}")
    return values


def azure_connection():
    """Open the Azure connection without putting credentials in generated files."""
    env = settings(azure=True)
    return pymssql.connect(
        server=env["AZURE_SQL_SERVER"], user=env["AZURE_SQL_USER"],
        password=env["AZURE_SQL_PASSWORD"], database=env["AZURE_SQL_DATABASE"],
        login_timeout=60, timeout=300, autocommit=False,
    )


def sqlcmd_query(sql: str, *, azure: bool = False) -> list[list[str]]:
    """Return pipe-delimited sqlcmd rows without exposing connection settings."""
    if azure:
        with azure_connection() as connection:
            cursor = connection.cursor()
            cursor.execute(sql)
            return [["" if value is None else str(value) for value in row] for row in cursor.fetchall()]
    env = settings()
    if env.get("MSSQL_SA_PASSWORD"):
        command = ["docker", "exec", "-e", f"SQLCMDPASSWORD={env['MSSQL_SA_PASSWORD']}", CONTAINER, SQLCMD, "-C", "-S", "localhost", "-U", env["MSSQL_USER"], "-d", env["MSSQL_DATABASE"], "-b", "-W", "-s", "|", "-h", "-1", "-Q", "SET NOCOUNT ON; " + sql]
    else:
        inner = 'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" ' + shlex.join([SQLCMD, "-C", "-S", "localhost", "-U", "sa", "-d", "LifeInsuranceP3", "-b", "-W", "-s", "|", "-h", "-1", "-Q", "SET NOCOUNT ON; " + sql])
        command = ["docker", "exec", CONTAINER, "sh", "-c", inner]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return [
        line.split("|") for line in result.stdout.splitlines()
        if line.strip() and not line.lstrip().startswith("(")
    ]


def run_sql_file(path: Path) -> str:
    env = settings()
    container_path = f"/tmp/dbsys-p3-rate-refresh/{path.name}"
    subprocess.run(["docker", "exec", CONTAINER, "mkdir", "-p", "/tmp/dbsys-p3-rate-refresh"], check=True)
    subprocess.run(["docker", "cp", str(path), f"{CONTAINER}:{container_path}"], check=True)
    if env.get("MSSQL_SA_PASSWORD"):
        command = ["docker", "exec", "-e", f"SQLCMDPASSWORD={env['MSSQL_SA_PASSWORD']}", CONTAINER, SQLCMD, "-C", "-S", "localhost", "-U", env["MSSQL_USER"], "-d", env["MSSQL_DATABASE"], "-b", "-W", "-s", "|", "-h", "-1", "-i", container_path]
    else:
        inner = 'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" ' + shlex.join([SQLCMD, "-C", "-S", "localhost", "-U", "sa", "-d", "LifeInsuranceP3", "-b", "-W", "-s", "|", "-h", "-1", "-i", container_path])
        command = ["docker", "exec", CONTAINER, "sh", "-c", inner]
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return result.stdout


def refresh_notes(wonder_cohort_source_year: int, loading_factor: Decimal, undiagnosed_fraction: Decimal) -> tuple[str, str]:
    """Build auditable source and parameter strings shared by both publishers."""
    source_datasets = ";".join((*COMMON_CURATED_SOURCES, *WONDER_COHORT_FILES[wonder_cohort_source_year]))
    notes = (
        f"u={undiagnosed_fraction}; loading={loading_factor}; wonder_source_year={wonder_cohort_source_year}; "
        f"ssa_baseline_source_year={SSA_BASELINE_SOURCE_YEAR}; "
        f"smoking_rr=never:{SMOKING_RR['never']},former:{SMOKING_RR['former']},current:{SMOKING_RR['current']}; "
        f"bmi_rr=normal:{BMI_RR['normal']},under:{BMI_RR['under']},over:{BMI_RR['over']},obese:{BMI_RR['obese']}; "
        "model=predicted_risk_by_profile.csv"
    )
    return source_datasets, notes


def source_data(
    wonder_cohort_source_year: int, *, azure: bool = False, profile_path: Path = PROFILE_PATH,
) -> tuple[dict[tuple[str, str], dict[str, Decimal]], dict[str, Decimal], list[int]]:
    if wonder_cohort_source_year not in WONDER_COHORT_FILES:
        raise ValueError(f"Unsupported WONDER cohort source year: {wonder_cohort_source_year}")
    if not azure:
        for source in (*COMMON_CURATED_SOURCES, *WONDER_COHORT_FILES[wonder_cohort_source_year]):
            if not (CURATED_DIR / source).exists():
                raise FileNotFoundError(f"Required curated source does not exist: {source}")
    if not profile_path.exists():
        raise FileNotFoundError(f"Required model profile export does not exist: {profile_path}")

    baseline_rows = sqlcmd_query(
        f"SELECT AgeBand, Gender, CONVERT(VARCHAR(40), MortalityRate) "
        f"FROM dbo.STG_MORTALITY WHERE SourceYear = {SSA_BASELINE_SOURCE_YEAR} "
        "AND ConditionFlag = 'BASELINE' ORDER BY Gender, AgeBand;"
    , azure=azure)
    baseline = {(age, gender): decimal(rate) for age, gender, rate in baseline_rows}

    wonder_rows = sqlcmd_query(
        f"WITH rates AS (SELECT AgeBand, Gender, ConditionFlag, MortalityRate "
        f"FROM dbo.STG_MORTALITY WHERE SourceYear = {wonder_cohort_source_year} "
        "AND ConditionFlag IN ('ALLCAUSE', 'DIABETES')) "
        "SELECT a.AgeBand, a.Gender, CONVERT(VARCHAR(40), a.MortalityRate), "
        "CONVERT(VARCHAR(40), d.MortalityRate) FROM rates a JOIN rates d "
        "ON a.AgeBand = d.AgeBand AND a.Gender = d.Gender "
        "WHERE a.ConditionFlag = 'ALLCAUSE' AND d.ConditionFlag = 'DIABETES' "
        "ORDER BY a.Gender, a.AgeBand;"
    , azure=azure)
    wonder = {(age, gender): decimal(diabetes) / decimal(all_cause) for age, gender, all_cause, diabetes in wonder_rows}

    prevalence_rows = sqlcmd_query(
        "SELECT AgeBand, Gender, "
        "CONVERT(VARCHAR(40), CAST(SUM(CASE WHEN DiabetesStatus = 'yes' THEN 1 ELSE 0 END) AS DECIMAL(18,10)) / "
        "NULLIF(SUM(CASE WHEN DiabetesStatus IN ('yes', 'no', 'gest', 'pre') THEN 1 ELSE 0 END), 0)) "
        "FROM dbo.STG_BRFSS_RECORD "
        "WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL "
        "GROUP BY AgeBand, Gender ORDER BY Gender, AgeBand;"
    , azure=azure)
    prevalence = {(age, gender): decimal(rate) for age, gender, rate in prevalence_rows}

    exercise_rows = sqlcmd_query(
        "SELECT ExerciseFreq, CONVERT(VARCHAR(40), COUNT_BIG(*)) "
        "FROM dbo.STG_BRFSS_RECORD WHERE ExerciseFreq IN ('yes', 'no') "
        "GROUP BY ExerciseFreq ORDER BY ExerciseFreq;"
    , azure=azure)
    exercise_counts = {name: decimal(count) for name, count in exercise_rows}
    if set(exercise_counts) != {"yes", "no"}:
        raise ValueError(f"Staging exercise vocabulary does not support marginalisation: {exercise_counts}")
    total_exercise = sum(exercise_counts.values())
    exercise_weights = {name: count / total_exercise for name, count in exercise_counts.items()}

    products = [int(row[0]) for row in sqlcmd_query("SELECT ProductID FROM dbo.Product ORDER BY ProductID;", azure=azure)]
    if products != sorted(PRODUCT_FACTORS) or len(products) != 15:
        raise ValueError(f"Product IDs do not match the explicit product-factor dictionary: {products}")

    joined: dict[tuple[str, str], dict[str, Decimal]] = {}
    expected = {(age, gender) for age in AGE_BANDS for gender in ("F", "M")}
    for key in expected:
        wonder_key = (WONDER_AGE_GROUP[key[0]], key[1])
        if key not in baseline or key not in prevalence or wonder_key not in wonder:
            raise ValueError(f"Missing SSA, prevalence, or WONDER input for {key}")
        m, p, f = baseline[key], prevalence[key], wonder[wonder_key]
        rr = (f * p - p - f) / (p * (f - 1))
        mn = m / (p * rr + (Decimal(1) - p))
        md = rr * mn
        joined[key] = {"m": m, "p": p, "f": f, "rr": rr, "mn": mn, "md": md}
    return joined, exercise_weights, products


def marginalised_profiles(
    weights: dict[str, Decimal], profile_path: Path = PROFILE_PATH,
) -> dict[tuple[str, str, str, str], Decimal]:
    expected_columns = {"AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq", "PredictedProbability"}
    with profile_path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if not expected_columns <= set(reader.fieldnames or []):
            raise ValueError("Predicted-risk export lacks the required profile columns")
        grouped: dict[tuple[str, str, str, str], dict[str, Decimal]] = defaultdict(dict)
        for row in reader:
            key = (row["AgeBand"], row["Gender"], row["SmokingStatus"], row["BMIBand"])
            grouped[key][row["ExerciseFreq"]] = decimal(row["PredictedProbability"])
    expected = {(age, gender, smoking, bmi) for age in AGE_BANDS for gender in ("F", "M") for smoking in ("current", "former", "never") for bmi in ("under", "normal", "over", "obese")}
    if set(grouped) != expected:
        raise ValueError(f"Predicted-risk profile keys do not cover the required RISK_FACTOR grain: {len(grouped)}")
    marginalised: dict[tuple[str, str, str, str], Decimal] = {}
    for key, by_exercise in grouped.items():
        if set(by_exercise) != set(weights):
            raise ValueError(f"Predicted-risk exercise levels differ for {key}: {by_exercise}")
        marginalised[key] = sum(by_exercise[level] * weights[level] for level in weights)
    return marginalised


def compose_risk_factors(
    derived: dict[tuple[str, str], dict[str, Decimal]],
    marginalised: dict[tuple[str, str, str, str], Decimal],
    undiagnosed_fraction: Decimal,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for age in AGE_BANDS:
        for gender in ("F", "M"):
            values = derived[(age, gender)]
            for smoking in ("current", "former", "never"):
                for bmi in ("under", "normal", "over", "obese"):
                    probability = marginalised[(age, gender, smoking, bmi)]
                    base_mortality = values["mn"] * SMOKING_RR[smoking] * BMI_RR[bmi]
                    no_mortality = base_mortality * (
                        Decimal(1) + probability * undiagnosed_fraction * (values["rr"] - Decimal(1))
                    )
                    yes_mortality = base_mortality * values["rr"]
                    for diabetes, mortality in (("yes", yes_mortality), ("no", no_mortality)):
                        multiplier = q3(mortality / values["m"])
                        if multiplier <= 0 or multiplier > Decimal("999.999"):
                            raise ValueError(
                                f"Mortality multiplier cannot fit NUMERIC(6,3) for {age}/{gender}/{smoking}/{bmi}"
                            )
                        rows.append({
                            "AgeBand": age, "Gender": gender, "SmokingStatus": smoking,
                            "DiabetesStatus": diabetes, "BMIBand": bmi,
                            "MortalityMultiplier": multiplier,
                        })
    if len(rows) != 624:
        raise AssertionError(f"Expected 624 RISK_FACTOR rows, found {len(rows)}")
    return rows


def compose_rates(
    risk_rows: list[dict[str, Any]], derived: dict[tuple[str, str], dict[str, Decimal]],
    products: list[int], loading_factor: Decimal,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for risk in risk_rows:
        baseline = derived[(risk["AgeBand"], risk["Gender"])]["m"]
        for product_id in products:
            base_rate = q2(Decimal(1000) * baseline * risk["MortalityMultiplier"] * loading_factor * PRODUCT_FACTORS[product_id])
            rows.append({**risk, "ProductID": product_id, "BaseRate": base_rate})
    if len(rows) != 9360:
        raise AssertionError(f"Expected 9,360 RATE rows, found {len(rows)}")
    return rows


def write_stage(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\r\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([row[column] for column in headers])
    if b'"' in path.read_bytes():
        raise ValueError(f"Refresh staging file unexpectedly contains quoted values: {path.name}")


def sql_literal(value: str) -> str:
    return value.replace("'", "''")


def sql_value_literal(value: Any) -> str:
    """Render a controlled derived value for the Azure set-based publisher."""
    if isinstance(value, (int, Decimal)):
        return str(value)
    return "'" + sql_literal(str(value)) + "'"


def publish_sql(
    effective_date: date, risk_container_path: str, rate_container_path: str,
    wonder_cohort_source_year: int, loading_factor: Decimal, undiagnosed_fraction: Decimal,
    source_state: dict[str, str | int] | None = None,
) -> str:
    source_datasets, notes = refresh_notes(wonder_cohort_source_year, loading_factor, undiagnosed_fraction)
    state_sql = ""
    if source_state:
        state_sql = f"""    INSERT dbo.DATA_SOURCE_STATE (SourcePath, ContentHash, ByteSize, ObservedAt, ObservedByRunID)
    VALUES ('{sql_literal(str(source_state['source_path']))}', '{sql_literal(str(source_state['observed_hash']))}', {int(source_state['byte_size'])}, SYSUTCDATETIME(), @RunID);
    IF '{os.environ.get('PART4_FORCE_FAILURE_AFTER_STATE', '0')}' = '1' THROW 51201, 'Forced Part 4 failure after DATA_SOURCE_STATE insert.', 1;
"""
    return f"""SET NOCOUNT ON;
SET XACT_ABORT ON;
BEGIN TRY
    BEGIN TRANSACTION;
    DECLARE @RunID INT, @RateVersionID INT, @ActiveCount INT;
    INSERT dbo.DATA_REFRESH_RUN (RunType, StartedAt, CompletedAt, Status, SourceDatasets, NewRateVersionID, Notes)
    VALUES ('manual', '{effective_date.isoformat()}', NULL, 'running', '{sql_literal(source_datasets)}', NULL, '{sql_literal(notes)}');
    SET @RunID = SCOPE_IDENTITY();
{state_sql}
    CREATE TABLE #RiskStage (
        AgeBand VARCHAR(10) NOT NULL, Gender VARCHAR(1) NOT NULL,
        SmokingStatus VARCHAR(10) NOT NULL, DiabetesStatus VARCHAR(10) NOT NULL,
        BMIBand VARCHAR(10) NOT NULL, MortalityMultiplier NUMERIC(6,3) NOT NULL
    );
    BULK INSERT #RiskStage FROM '{risk_container_path}'
    WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
    IF (SELECT COUNT(*) FROM #RiskStage) <> 624
        THROW 51101, 'RISK_FACTOR stage row count mismatch.', 1;
    INSERT dbo.RISK_FACTOR (AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, MortalityMultiplier, DerivedFromRunID)
    SELECT AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, MortalityMultiplier, @RunID FROM #RiskStage;
    IF (SELECT COUNT(*) FROM dbo.RISK_FACTOR WHERE DerivedFromRunID = @RunID) <> 624
        THROW 51102, 'RISK_FACTOR publish row count mismatch.', 1;

    SELECT @ActiveCount = COUNT(*) FROM dbo.RATE_VERSION WHERE Status = 'active';
    IF @ActiveCount <> 1
        THROW 51103, 'Expected exactly one active RATE_VERSION before publication.', 1;
    UPDATE dbo.RATE_VERSION SET Status = 'superseded', ExpiryDate = '{effective_date.isoformat()}' WHERE Status = 'active';
    INSERT dbo.RATE_VERSION (EffectiveDate, ExpiryDate, Status, CreatedByRunID)
    VALUES ('{effective_date.isoformat()}', NULL, 'active', @RunID);
    SET @RateVersionID = SCOPE_IDENTITY();

    CREATE TABLE #RateStage (
        AgeBand VARCHAR(10) NOT NULL, Gender VARCHAR(1) NOT NULL,
        SmokingStatus VARCHAR(10) NOT NULL, DiabetesStatus VARCHAR(10) NOT NULL,
        BMIBand VARCHAR(10) NOT NULL, ProductID INT NOT NULL, BaseRate NUMERIC(12,2) NOT NULL
    );
    BULK INSERT #RateStage FROM '{rate_container_path}'
    WITH (FIRSTROW=2, FIELDTERMINATOR=',', ROWTERMINATOR='0x0d0a', TABLOCK);
    IF (SELECT COUNT(*) FROM #RateStage) <> 9360
        THROW 51104, 'RATE stage row count mismatch.', 1;
    INSERT dbo.RATE (RateVersionID, RiskFactorID, ProductID, BaseRate)
    SELECT @RateVersionID, rf.RiskFactorID, rs.ProductID, rs.BaseRate
    FROM #RateStage rs
    JOIN dbo.RISK_FACTOR rf ON rf.AgeBand = rs.AgeBand AND rf.Gender = rs.Gender
        AND rf.SmokingStatus = rs.SmokingStatus AND rf.DiabetesStatus = rs.DiabetesStatus
        AND rf.BMIBand = rs.BMIBand AND rf.DerivedFromRunID = @RunID;
    IF (SELECT COUNT(*) FROM dbo.RATE WHERE RateVersionID = @RateVersionID) <> 9360
        THROW 51105, 'RATE publish row count mismatch.', 1;
    UPDATE dbo.DATA_REFRESH_RUN
    SET CompletedAt = '{effective_date.isoformat()}', Status = 'success', NewRateVersionID = @RateVersionID
    WHERE RunID = @RunID;
    COMMIT TRANSACTION;
    PRINT CONCAT('PUBLISHED|', @RunID, '|', @RateVersionID);
END TRY
BEGIN CATCH
    IF @@TRANCOUNT > 0 ROLLBACK TRANSACTION;
    THROW;
END CATCH;
"""


def publish_azure(
    effective_date: date, risk_rows: list[dict[str, Any]], rate_rows: list[dict[str, Any]],
    wonder_cohort_source_year: int, loading_factor: Decimal, undiagnosed_fraction: Decimal,
) -> tuple[int, int]:
    """Publish a rate book through the Azure network driver in one transaction.

    Azure SQL cannot read the local temporary CSV files.  The small derived
    sets are therefore inserted in parameterised batches, retaining the same
    validation and transaction boundaries as the local BULK INSERT path.
    """
    source_datasets, notes = refresh_notes(wonder_cohort_source_year, loading_factor, undiagnosed_fraction)
    connection = azure_connection()
    try:
        cursor = connection.cursor()
        cursor.execute(
            "INSERT dbo.DATA_REFRESH_RUN (RunType, StartedAt, CompletedAt, Status, SourceDatasets, NewRateVersionID, Notes) "
            "OUTPUT INSERTED.RunID VALUES (%s, %s, NULL, %s, %s, NULL, %s);",
            ("manual", effective_date, "running", source_datasets, notes),
        )
        run_id = int(cursor.fetchone()[0])
        print(f"Azure DATA_REFRESH_RUN: {run_id}", flush=True)

        risk_values = [
            (row["AgeBand"], row["Gender"], row["SmokingStatus"], row["DiabetesStatus"],
             row["BMIBand"], str(row["MortalityMultiplier"]), run_id)
            for row in risk_rows
        ]
        cursor.execute(
            "INSERT dbo.RISK_FACTOR (AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, MortalityMultiplier, DerivedFromRunID) VALUES "
            + ", ".join("(" + ", ".join(sql_value_literal(value) for value in row) + ")" for row in risk_values)
        )
        print(f"Azure RISK_FACTOR: {len(risk_values)}/{len(risk_values)}", flush=True)
        cursor.execute("SELECT COUNT(*) FROM dbo.RISK_FACTOR WHERE DerivedFromRunID = %s", (run_id,))
        if int(cursor.fetchone()[0]) != 624:
            raise RuntimeError("RISK_FACTOR publish row count mismatch.")

        cursor.execute("SELECT COUNT(*) FROM dbo.RATE_VERSION WHERE Status = 'active'")
        if int(cursor.fetchone()[0]) != 1:
            raise RuntimeError("Expected exactly one active RATE_VERSION before publication.")
        cursor.execute("UPDATE dbo.RATE_VERSION SET Status = 'superseded', ExpiryDate = %s WHERE Status = 'active'", (effective_date,))
        cursor.execute(
            "INSERT dbo.RATE_VERSION (EffectiveDate, ExpiryDate, Status, CreatedByRunID) "
            "OUTPUT INSERTED.RateVersionID VALUES (%s, NULL, 'active', %s);", (effective_date, run_id),
        )
        rate_version_id = int(cursor.fetchone()[0])
        print(f"Azure RATE_VERSION: {rate_version_id}", flush=True)

        cursor.execute(
            "CREATE TABLE #RateStage (AgeBand VARCHAR(10) NOT NULL, Gender VARCHAR(1) NOT NULL, "
            "SmokingStatus VARCHAR(10) NOT NULL, DiabetesStatus VARCHAR(10) NOT NULL, BMIBand VARCHAR(10) NOT NULL, "
            "ProductID INT NOT NULL, BaseRate NUMERIC(12,2) NOT NULL)"
        )
        rate_values = [
            (row["AgeBand"], row["Gender"], row["SmokingStatus"], row["DiabetesStatus"],
             row["BMIBand"], row["ProductID"], str(row["BaseRate"]))
            for row in rate_rows
        ]
        for start in range(0, len(rate_values), 900):
            batch = rate_values[start : start + 900]
            cursor.execute(
                "INSERT #RateStage (AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, ProductID, BaseRate) VALUES "
                + ", ".join("(" + ", ".join(sql_value_literal(value) for value in row) + ")" for row in batch)
            )
            print(f"Azure RATE stage: {min(start + 900, len(rate_values))}/{len(rate_values)}", flush=True)
        cursor.execute(
            "INSERT dbo.RATE (RateVersionID, RiskFactorID, ProductID, BaseRate) "
            "SELECT %s, rf.RiskFactorID, rs.ProductID, rs.BaseRate FROM #RateStage AS rs "
            "JOIN dbo.RISK_FACTOR AS rf ON rf.AgeBand = rs.AgeBand AND rf.Gender = rs.Gender "
            "AND rf.SmokingStatus = rs.SmokingStatus AND rf.DiabetesStatus = rs.DiabetesStatus "
            "AND rf.BMIBand = rs.BMIBand AND rf.DerivedFromRunID = %s",
            (rate_version_id, run_id),
        )
        cursor.execute("SELECT COUNT(*) FROM dbo.RATE WHERE RateVersionID = %s", (rate_version_id,))
        if int(cursor.fetchone()[0]) != 9360:
            raise RuntimeError("RATE publish row count mismatch.")
        cursor.execute(
            "UPDATE dbo.DATA_REFRESH_RUN SET CompletedAt = %s, Status = 'success', NewRateVersionID = %s WHERE RunID = %s",
            (effective_date, rate_version_id, run_id),
        )
        connection.commit()
        return run_id, rate_version_id
    except Exception as error:
        print(f"Azure publication failed before commit: {error}", flush=True)
        connection.rollback()
        raise
    finally:
        connection.close()


def log_failure(effective_date: date, reason: str, wonder_cohort_source_year: int, *, azure: bool = False) -> int | None:
    source_datasets = ";".join((*COMMON_CURATED_SOURCES, *WONDER_COHORT_FILES[wonder_cohort_source_year]))
    safe_reason = sql_literal(reason.replace("\n", " ")[:220])
    rows = sqlcmd_query(
        "INSERT dbo.DATA_REFRESH_RUN (RunType, StartedAt, CompletedAt, Status, SourceDatasets, NewRateVersionID, Notes) "
        f"VALUES ('manual', '{effective_date.isoformat()}', '{effective_date.isoformat()}', "
        f"'failed', '{sql_literal(source_datasets)}', NULL, 'Refresh failed: {safe_reason}'); "
        "SELECT SCOPE_IDENTITY();", azure=azure
    )
    return int(decimal(rows[-1][0])) if rows else None


class RetrainingGateError(RuntimeError):
    """Carries the completed fit when validation retains the previous model."""

    def __init__(self, retraining: Any):
        self.retraining = retraining
        super().__init__(f"Retraining validation gate failed: {retraining.gate}")


def run(
    effective_date: date,
    wonder_cohort_source_year: int = DEFAULT_WONDER_COHORT_SOURCE_YEAR,
    loading_factor: Decimal = DEFAULT_LOADING_FACTOR,
    undiagnosed_fraction: Decimal = DEFAULT_UNDIAGNOSED_FRACTION,
    *, azure: bool = False, profile_path: Path = PROFILE_PATH,
) -> dict[str, Any]:
    if loading_factor <= 0 or undiagnosed_fraction < 0 or undiagnosed_fraction > 1:
        raise ValueError("Loading factor must be positive and undiagnosed fraction must be from 0 through 1.")
    source_state = None
    if not azure:
        retraining = run_retraining(env_file=PART4_ENV_FILE, python_executable=sys.executable)
        if not retraining.gate["passed"]:
            raise RetrainingGateError(retraining)
        profile_path = Path(retraining.local_profile_path)
        if retraining.retrained:
            source_state = {"source_path": retraining.source_path, "observed_hash": retraining.observed_hash, "byte_size": retraining.byte_size}
            staged_source = PART4_ROOT / "data" / "curated" / Path(retraining.source_path).name
            subprocess.run([
                sys.executable, str(PART4_ROOT / "python" / "load_staging.py"),
                "--brfss-source", str(staged_source),
                "--output-dir", str(PART4_ROOT / "data" / "processed" / "staging_load"),
                "--env-file", str(PART4_ENV_FILE),
            ], check=True)
    derived, exercise_weights, products = source_data(
        wonder_cohort_source_year, azure=azure, profile_path=profile_path,
    )
    marginalised = marginalised_profiles(exercise_weights, profile_path)
    risk_rows = compose_risk_factors(derived, marginalised, undiagnosed_fraction)
    rate_rows = compose_rates(risk_rows, derived, products, loading_factor)
    if azure:
        run_id, rate_version_id = publish_azure(
            effective_date, risk_rows, rate_rows, wonder_cohort_source_year, loading_factor, undiagnosed_fraction
        )
    else:
        with tempfile.TemporaryDirectory(prefix="p3-rate-refresh-") as directory:
            temp = Path(directory)
            risk_file, rate_file, sql_file = temp / "risk_stage.csv", temp / "rate_stage.csv", temp / "publish.sql"
            risk_headers = ["AgeBand", "Gender", "SmokingStatus", "DiabetesStatus", "BMIBand", "MortalityMultiplier"]
            rate_headers = ["AgeBand", "Gender", "SmokingStatus", "DiabetesStatus", "BMIBand", "ProductID", "BaseRate"]
            write_stage(risk_file, risk_headers, risk_rows)
            write_stage(rate_file, rate_headers, rate_rows)
            subprocess.run(["docker", "exec", CONTAINER, "mkdir", "-p", "/tmp/dbsys-p3-rate-refresh"], check=True)
            subprocess.run(["docker", "cp", str(risk_file), f"{CONTAINER}:/tmp/dbsys-p3-rate-refresh/risk_stage.csv"], check=True)
            subprocess.run(["docker", "cp", str(rate_file), f"{CONTAINER}:/tmp/dbsys-p3-rate-refresh/rate_stage.csv"], check=True)
            sql_file.write_text(publish_sql(effective_date, "/tmp/dbsys-p3-rate-refresh/risk_stage.csv", "/tmp/dbsys-p3-rate-refresh/rate_stage.csv", wonder_cohort_source_year, loading_factor, undiagnosed_fraction, source_state), encoding="utf-8")
            output = run_sql_file(sql_file)
        published = [line for line in output.splitlines() if line.startswith("PUBLISHED|")]
        if len(published) != 1:
            raise RuntimeError(f"Publication did not return one identifier: {output}")
        _, run_id, rate_version_id = published[0].split("|")
    return {
        "seed": SEED, "run_id": int(run_id), "rate_version_id": int(rate_version_id),
        "effective_date": effective_date.isoformat(), "wonder_cohort_source_year": wonder_cohort_source_year,
        "ssa_baseline_source_year": SSA_BASELINE_SOURCE_YEAR, "loading_factor": float(loading_factor),
        "undiagnosed_fraction": float(undiagnosed_fraction), "exercise_weights": {key: float(value) for key, value in exercise_weights.items()},
        "derived": {f"{age}|{gender}": {key: float(value) for key, value in values.items()} for (age, gender), values in derived.items()},
        "risk_rows": risk_rows, "rate_rows": len(rate_rows), "product_factors": {str(key): float(value) for key, value in PRODUCT_FACTORS.items()},
        "retraining": asdict(retraining) if not azure else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--effective-date", type=date.fromisoformat, default=EFFECTIVE_DATE)
    parser.add_argument("--wonder-cohort-source-year", type=int, choices=sorted(WONDER_COHORT_FILES), default=DEFAULT_WONDER_COHORT_SOURCE_YEAR)
    parser.add_argument("--loading-factor", type=decimal, default=DEFAULT_LOADING_FACTOR)
    parser.add_argument("--undiagnosed-fraction", type=decimal, default=DEFAULT_UNDIAGNOSED_FRACTION)
    parser.add_argument("--azure", action="store_true", help="Read staging data and publish through AZURE_SQL_* settings.")
    parser.add_argument("--profile-path", type=Path, default=PROFILE_PATH,
                        help="Path to predicted_risk_by_profile.csv, normally the project export or Blob download.")
    args = parser.parse_args()
    try:
        result = run(args.effective_date, args.wonder_cohort_source_year, args.loading_factor, args.undiagnosed_fraction,
                     azure=args.azure, profile_path=args.profile_path)
    except RetrainingGateError as error:
        failure_id = log_failure(args.effective_date, str(error), args.wonder_cohort_source_year, azure=args.azure)
        print("PART4_REFRESH_RESULT=" + json.dumps({
            "outcome": "retraining_gate_failed",
            "run_id": failure_id,
            "rate_version_id": None,
            "retraining": asdict(error.retraining),
        }, default=str))
        return
    except Exception as error:
        failure_id = log_failure(args.effective_date, str(error), args.wonder_cohort_source_year, azure=args.azure)
        raise RuntimeError(f"Rate refresh failed and logged DATA_REFRESH_RUN {failure_id}") from error
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = "azure_" if args.azure else ""
    report_path = OUTPUT_DIR / f"rate_refresh_{target}v{result['rate_version_id']}.json"
    report_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    summary = {key: value for key, value in result.items() if key not in {"risk_rows", "derived"}}
    summary["outcome"] = "retrained_gate_passed" if result["retraining"]["retrained"] else "no_source_change"
    print(json.dumps(summary, indent=2))
    print("PART4_REFRESH_RESULT=" + json.dumps(summary, default=str))
    print(f"Wrote {report_path}")


if __name__ == "__main__":
    main()
