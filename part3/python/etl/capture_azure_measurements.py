# Jingrui Feng (jf4446) - database systems project part 3 - azure workload measurement capture
"""Capture the four requested Azure physical-design measurements.

Each workload query is executed twice with STATISTICS IO.  The first execution
warms the Azure buffer cache and is discarded.  Result rows are discarded by
the client so Q8's large retrieval variants cannot stall the capture process.
The saved logical reads therefore describe the second execution only.
"""

from __future__ import annotations

import csv
import re
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

from dotenv import dotenv_values
import pymssql


ROOT = Path(__file__).resolve().parents[2]
WORKLOAD = ROOT / "sql" / "physical" / "workload_queries.sql"
OUTPUT = ROOT / "outputs" / "azure"
PLAN_DIR = OUTPUT / "plans"
CONTAINER = "dbsys-p3-mssql"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"
QUERY_IDS = ("Q1", "Q4", "Q5", "Q8a-count", "Q8b-count", "Q8a", "Q8b")
MAIN_TABLE = {
    "Q1": "ContractParty", "Q4": "WELLNESS_ACTIVITY", "Q5": "WELLNESS_ACTIVITY",
    "Q8a-count": "Contract", "Q8b-count": "Contract", "Q8a": "Contract", "Q8b": "Contract",
}
IO_PATTERN = re.compile(r"Table '([^']+)'. Scan count (\d+), logical reads (\d+),", re.I)
SHOWPLAN_NS = {"p": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}
SET_OPTIONS = (
    "SET ANSI_NULLS ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON; SET ARITHABORT ON; "
    "SET CONCAT_NULL_YIELDS_NULL ON; SET QUOTED_IDENTIFIER ON; SET NUMERIC_ROUNDABORT OFF; "
)


def azure_env() -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(ROOT / ".env").items() if value}
    needed = ("AZURE_SQL_SERVER", "AZURE_SQL_DATABASE", "AZURE_SQL_USER", "AZURE_SQL_PASSWORD")
    missing = [key for key in needed if key not in values]
    if missing:
        raise RuntimeError(f"Missing Azure settings: {', '.join(missing)}")
    return values


def queries() -> dict[str, str]:
    text = WORKLOAD.read_text(encoding="utf-8")
    found = {
        identifier: sql.strip()
        for identifier, sql in re.findall(r"-- BEGIN (Q\d+(?:[a-z]+(?:-count)?)?)\s*\n(.*?)\n-- END \1", text, re.S)
    }
    return {identifier: found[identifier] for identifier in QUERY_IDS}


def sqlcmd(env: dict[str, str], sql: str, *, discard_stdout: bool) -> subprocess.CompletedProcess[str]:
    command = [
        "docker", "exec", "-e", f"SQLCMDPASSWORD={env['AZURE_SQL_PASSWORD']}", CONTAINER,
        SQLCMD, "-C", "-S", env["AZURE_SQL_SERVER"], "-U", env["AZURE_SQL_USER"],
        "-d", env["AZURE_SQL_DATABASE"], "-b", "-y", "0", "-Y", "0", "-r", "1", "-Q", sql,
    ]
    result = subprocess.run(
        command, text=True, stdout=subprocess.DEVNULL if discard_stdout else subprocess.PIPE,
        stderr=subprocess.PIPE, check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr[-3000:])
    return result


def plan_for(env: dict[str, str], query: str) -> str:
    connection = pymssql.connect(
        server=env["AZURE_SQL_SERVER"], user=env["AZURE_SQL_USER"], password=env["AZURE_SQL_PASSWORD"],
        database=env["AZURE_SQL_DATABASE"], login_timeout=60, timeout=120,
    )
    try:
        cursor = connection.cursor()
        cursor.execute(SET_OPTIONS)
        cursor.execute("SET SHOWPLAN_XML ON")
        cursor.execute(query)
        plan = str(cursor.fetchone()[0])
        cursor.execute("SET SHOWPLAN_XML OFF")
        return plan
    finally:
        connection.close()


def io_totals(stderr: str) -> dict[str, tuple[int, int]]:
    totals: dict[str, tuple[int, int]] = {}
    for table, scans, reads in IO_PATTERN.findall(stderr):
        old_scans, old_reads = totals.get(table, (0, 0))
        totals[table] = old_scans + int(scans), old_reads + int(reads)
    return totals


def main() -> None:
    env, sql_blocks = azure_env(), queries()
    OUTPUT.mkdir(parents=True, exist_ok=True)
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, object]] = []
    summaries: list[dict[str, object]] = []
    for identifier, query in sql_blocks.items():
        print(f"{identifier}: warm-up", flush=True)
        sqlcmd(env, SET_OPTIONS + "SET NOCOUNT ON; SET STATISTICS IO ON; " + query, discard_stdout=True)
        print(f"{identifier}: capture", flush=True)
        captured = sqlcmd(env, SET_OPTIONS + "SET NOCOUNT ON; SET STATISTICS IO ON; " + query, discard_stdout=True)
        plan = plan_for(env, query)
        (PLAN_DIR / f"{identifier}.sqlplan").write_text(plan, encoding="utf-8")
        io = io_totals(captured.stderr)
        root = ET.fromstring(plan)
        main_operator = "Unknown"
        for relop in root.findall(".//p:RelOp", SHOWPLAN_NS):
            obj = relop.find(".//p:Object", SHOWPLAN_NS)
            table_name = obj.get("Table", "").replace("[", "").replace("]", "").split(".")[-1] if obj is not None else ""
            physical_op = relop.get("PhysicalOp", "Unknown")
            if table_name == MAIN_TABLE[identifier] and ("Seek" in physical_op or "Scan" in physical_op):
                main_operator = physical_op
                break
        total_reads = sum(reads for table, (_, reads) in io.items() if table.lower() not in {"worktable", "workfile"})
        summaries.append({"query_id": identifier, "logical_reads_all_tables_touched": total_reads, "main_operator": main_operator})
        for table, (scans, reads) in sorted(io.items()):
            if table.lower() not in {"worktable", "workfile"}:
                records.append({"query_id": identifier, "table_name": table, "logical_reads": reads, "scan_count": scans, "main_operator": main_operator if table == MAIN_TABLE[identifier] else ""})
    with (OUTPUT / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_id", "table_name", "logical_reads", "scan_count", "main_operator"])
        writer.writeheader(); writer.writerows(records)
    with (OUTPUT / "query_summary_all_tables.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_id", "logical_reads_all_tables_touched", "main_operator"])
        writer.writeheader(); writer.writerows(summaries)
    print(f"Wrote {OUTPUT / 'results.csv'} and {OUTPUT / 'query_summary_all_tables.csv'}")


if __name__ == "__main__":
    main()
