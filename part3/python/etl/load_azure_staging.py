# Jingrui Feng (jf4446) - database systems project part 3 - azure staging data loader
"""Load prepared Part 3 staging CSVs into Azure SQL and aggregate STG_BRFSS."""

from __future__ import annotations

import csv
from pathlib import Path

import pymssql
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data" / "processed" / "staging_load"
BATCH_SIZE = 1_000
TABLES = (("STG_BRFSS_RECORD", 50_000, "StgBRFSSRecordID"), ("STG_NHANES", 8_153, "StgNHANESID"), ("STG_MORTALITY", 109, "StgMortalityID"))


def quoted(value: str) -> str:
    return "[" + value.replace("]", "]]" ) + "]"


def literal(value: str | None) -> str:
    return "NULL" if value in (None, "") else "N'" + value.replace("'", "''") + "'"


def main() -> None:
    config = dotenv_values(ROOT / ".env")
    conn = pymssql.connect(server=config["AZURE_SQL_SERVER"], user=config["AZURE_SQL_USER"], password=config["AZURE_SQL_PASSWORD"], database=config["AZURE_SQL_DATABASE"], login_timeout=60, timeout=600, tds_version="7.4", autocommit=True)
    cur = conn.cursor()
    try:
        cur.execute("TRUNCATE TABLE dbo.STG_BRFSS")
        for table, expected, identity in TABLES:
            cur.execute(f"TRUNCATE TABLE dbo.{quoted(table)}")
            with (SOURCE / f"{table}.csv").open(newline="", encoding="utf-8-sig") as handle:
                reader = csv.DictReader(handle)
                headers = reader.fieldnames or []
                cur.execute(f"SET IDENTITY_INSERT dbo.{quoted(table)} ON")
                rows = 0
                values: list[str] = []
                try:
                    for row in reader:
                        values.append("(" + ",".join(literal(row[column]) for column in headers) + ")")
                        if len(values) == BATCH_SIZE:
                            cur.execute(f"INSERT dbo.{quoted(table)} ({', '.join(quoted(column) for column in headers)}) VALUES " + ",".join(values))
                            rows += len(values); values.clear()
                    if values:
                        cur.execute(f"INSERT dbo.{quoted(table)} ({', '.join(quoted(column) for column in headers)}) VALUES " + ",".join(values))
                        rows += len(values)
                finally:
                    cur.execute(f"SET IDENTITY_INSERT dbo.{quoted(table)} OFF")
            if rows != expected:
                raise RuntimeError(f"{table} source row count {rows} does not match {expected}")
            cur.execute(f"DBCC CHECKIDENT ('dbo.{table}', RESEED, {expected}) WITH NO_INFOMSGS")
            print(f"loaded {table}={rows}", flush=True)
        cur.execute("""
INSERT dbo.STG_BRFSS
    (SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, ExerciseFreq, PrevalenceRate, LoadDate, SourceFile)
SELECT outcome.SourceYear, outcome.AgeBand, outcome.Gender, outcome.SmokingStatus, outcome.DiabetesStatus, outcome.BMIBand, outcome.ExerciseFreq,
       CAST(CAST(outcome.OutcomeRows AS DECIMAL(18,8)) / profile.ProfileRows AS NUMERIC(6,4)), outcome.LoadDate, outcome.SourceFile
FROM (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, ExerciseFreq, LoadDate, SourceFile, COUNT_BIG(*) AS OutcomeRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL AND DiabetesStatus IS NOT NULL AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, DiabetesStatus, BMIBand, ExerciseFreq, LoadDate, SourceFile
) outcome
JOIN (
    SELECT SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq, LoadDate, SourceFile, COUNT_BIG(*) AS ProfileRows
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL AND DiabetesStatus IS NOT NULL AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL
    GROUP BY SourceYear, AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq, LoadDate, SourceFile
) profile ON profile.SourceYear=outcome.SourceYear AND profile.AgeBand=outcome.AgeBand AND profile.Gender=outcome.Gender AND profile.SmokingStatus=outcome.SmokingStatus AND profile.BMIBand=outcome.BMIBand AND profile.ExerciseFreq=outcome.ExerciseFreq AND profile.LoadDate=outcome.LoadDate AND profile.SourceFile=outcome.SourceFile
""")
        cur.execute("SELECT COUNT(*) FROM dbo.STG_BRFSS")
        print("aggregated STG_BRFSS=" + str(cur.fetchone()[0]), flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
