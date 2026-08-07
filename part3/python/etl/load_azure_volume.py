# Jingrui Feng (jf4446) - database systems project part 3 - azure volume data loader
"""Load the generated Part 3 transactional CSVs into Azure SQL in batches.

This is the network-driver fallback for Azure SQL.  The Blob external data
source is used for the lake copy, but Azure SQL returns provider error 7301
when it bulk-loads a temporary identity-order staging table.  This loader uses
1,000-row SQL batches from local CSV files instead.  Each bridge row receives
its explicit 1..N source-line identity through IDENTITY_INSERT, so dependent
foreign keys retain the deterministic ranges documented in load_order.md.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path

import pymssql
from dotenv import dotenv_values


ROOT = Path(__file__).resolve().parents[2]
CSV_DIR = ROOT / "data" / "synthetic" / "large"
BATCH_SIZE = 1_000

TABLES = (
    ("Customer", 50_000, False),
    ("Product", 15, False),
    ("BillingAccount", 40_000, False),
    ("Account", 40_000, False),
    ("AccountMember", 50_000, False),
    ("Relation_3", 40_000, False),
    ("RATE_VERSION", 6, True),
    ("Contract", 60_000, False),
    ("Claim", 5_000, False),
    ("ContractParty", 90_000, False),
    ("Invoice", 300_000, False),
    ("WELLNESS_PROGRAM", 5, True),
    ("WELLNESS_ENROLLMENT", 24_000, True),
    ("WELLNESS_ACTIVITY", 1_000_000, True),
    ("RISK_IMPROVEMENT", 48_000, True),
    ("POLICY_RENEWAL", 90_000, True),
    ("APPLICATION", 90_000, True),
)

IDENTITY_COLUMNS = {
    "RATE_VERSION": "RateVersionID",
    "WELLNESS_PROGRAM": "WellnessProgramID",
    "WELLNESS_ENROLLMENT": "EnrollmentID",
    "WELLNESS_ACTIVITY": "ActivityID",
    "RISK_IMPROVEMENT": "ImprovementID",
    "POLICY_RENEWAL": "RenewalID",
    "APPLICATION": "ApplicationID",
}


def quoted(identifier: str) -> str:
    return "[" + identifier.replace("]", "]]" ) + "]"


def literal(value: str | None) -> str:
    if value is None or value == "":
        return "NULL"
    return "N'" + value.replace("'", "''") + "'"


def connect() -> pymssql.Connection:
    config = dotenv_values(ROOT / ".env")
    return pymssql.connect(
        server=config["AZURE_SQL_SERVER"], user=config["AZURE_SQL_USER"],
        password=config["AZURE_SQL_PASSWORD"], database=config["AZURE_SQL_DATABASE"],
        login_timeout=60, timeout=900, tds_version="7.4", autocommit=True,
    )


def scalar(cursor: pymssql.Cursor, sql: str) -> int:
    cursor.execute(sql)
    return int(cursor.fetchone()[0])


def execute_batch(cursor: pymssql.Cursor, table: str, columns: list[str], values: list[str]) -> None:
    cursor.execute(
        f"INSERT dbo.{quoted(table)} ({', '.join(quoted(column) for column in columns)}) VALUES "
        + ",".join(values)
    )


def load_table(cursor: pymssql.Cursor, table: str, expected_rows: int, identity: bool) -> None:
    path = CSV_DIR / f"{table}.csv"
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        headers = reader.fieldnames or []
        if not headers or len(headers) != len(set(headers)):
            raise ValueError(f"Invalid CSV header for {table}")
        identity_column = IDENTITY_COLUMNS.get(table)
        columns = ([identity_column] if identity else []) + headers
        if identity:
            cursor.execute(f"SET IDENTITY_INSERT dbo.{quoted(table)} ON")
        inserted = 0
        values: list[str] = []
        try:
            for line_number, row in enumerate(reader, start=1):
                source = ([str(line_number)] if identity else []) + [row[header] for header in headers]
                values.append("(" + ",".join(literal(value) for value in source) + ")")
                if len(values) == BATCH_SIZE:
                    execute_batch(cursor, table, columns, values)
                    inserted += len(values)
                    values.clear()
                    if inserted % 50_000 == 0:
                        print(f"{datetime.now().isoformat(timespec='seconds')} loading {table}: {inserted:,}/{expected_rows:,}", flush=True)
            if values:
                execute_batch(cursor, table, columns, values)
                inserted += len(values)
        finally:
            if identity:
                cursor.execute(f"SET IDENTITY_INSERT dbo.{quoted(table)} OFF")
    if inserted != expected_rows:
        raise RuntimeError(f"{table} source rows {inserted:,} do not match {expected_rows:,}")
    if identity:
        cursor.execute(f"DBCC CHECKIDENT ('dbo.{table}', RESEED, {expected_rows}) WITH NO_INFOMSGS")
        actual = scalar(cursor, f"SELECT COUNT(*) FROM dbo.{quoted(table)}")
        minimum = scalar(cursor, f"SELECT MIN({quoted(identity_column)}) FROM dbo.{quoted(table)}")
        maximum = scalar(cursor, f"SELECT MAX({quoted(identity_column)}) FROM dbo.{quoted(table)}")
        if (actual, minimum, maximum) != (expected_rows, 1, expected_rows):
            raise RuntimeError(f"{table} identity range {(actual, minimum, maximum)} is not 1..{expected_rows}")
    elif scalar(cursor, f"SELECT COUNT(*) FROM dbo.{quoted(table)}") != expected_rows:
        raise RuntimeError(f"{table} target count does not match {expected_rows:,}")
    print(f"{datetime.now().isoformat(timespec='seconds')} loaded {table}: {expected_rows:,} rows", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resume-from", choices=[table for table, _, _ in TABLES])
    args = parser.parse_args()
    conn = connect()
    cursor = conn.cursor()
    try:
        start = 0 if args.resume_from is None else next(
            index for index, (table, _, _) in enumerate(TABLES) if table == args.resume_from
        )
        if start == 0:
            # DELETE is required because Customer and Product are FK-referenced.
            cursor.execute("DELETE FROM dbo.Customer")
            cursor.execute("DELETE FROM dbo.Product")
        else:
            for table, expected_rows, _ in TABLES[:start]:
                actual_rows = scalar(cursor, f"SELECT COUNT(*) FROM dbo.{quoted(table)}")
                if actual_rows != expected_rows:
                    raise RuntimeError(f"Cannot resume at {args.resume_from}: {table} has {actual_rows:,}, expected {expected_rows:,}")
            for table, _, _ in TABLES[start + 1:]:
                actual_rows = scalar(cursor, f"SELECT COUNT(*) FROM dbo.{quoted(table)}")
                if actual_rows != 0:
                    raise RuntimeError(f"Cannot resume at {args.resume_from}: dependent {table} is not empty")
            cursor.execute(f"DELETE FROM dbo.{quoted(args.resume_from)}")
            print(f"{datetime.now().isoformat(timespec='seconds')} cleared partial {args.resume_from} load", flush=True)
        for table, rows, identity in TABLES[start:]:
            load_table(cursor, table, rows, identity)
        cursor.execute("UPDATE dbo.Contract SET ApplicationID = ContractID WHERE ContractID BETWEEN 1 AND 60000 AND ApplicationID IS NULL")
        linked = scalar(cursor, "SELECT COUNT(*) FROM dbo.Contract WHERE ApplicationID IS NOT NULL")
        if linked != 60_000:
            raise RuntimeError(f"Contract application backfill count {linked:,} does not match 60,000")
        print(f"{datetime.now().isoformat(timespec='seconds')} Contract.ApplicationID backfill: {linked:,} rows", flush=True)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
