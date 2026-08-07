# Jingrui Feng (jf4446) - database systems project part 3 - local baseline measurement capture
"""Capture reproducible pre-physical-design workload baselines locally.

The script executes each marked query in sql/physical/workload_queries.sql
twice through the local Docker SQL Server.  It discards the warm-up execution,
then saves the second execution's actual ShowPlanXML and logical-read evidence.
Wall-clock elapsed time is intentionally not written as a performance result:
the local SQL Server runs under Rosetta emulation on Apple Silicon.
"""
from __future__ import annotations

import csv
import argparse
import os
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
WORKLOAD_PATH = ROOT / "sql" / "physical" / "workload_queries.sql"
OUTPUT_DIR = ROOT / "outputs" / "baseline"
PLAN_DIR = OUTPUT_DIR / "plans"
ENV_PATH = ROOT / ".env"
CONTAINER = "dbsys-p3-mssql"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"

# The table whose access method is the primary design signal for each query.
MAIN_TABLES = {
    "Q1": "ContractParty",
    "Q2": "ContractParty",
    "Q2b": "Invoice",
    "Q3": "RATE_VERSION",
    "Q4": "WELLNESS_ACTIVITY",
    "Q5": "WELLNESS_ACTIVITY",
    "Q6": "Contract",
    "Q7": "POLICY_RENEWAL",
    "Q8a-count": "Contract",
    "Q8b-count": "Contract",
    "Q8a": "Contract",
    "Q8b": "Contract",
    "Q9": "STG_BRFSS_RECORD",
}

SHOWPLAN_NS = {"p": "http://schemas.microsoft.com/sqlserver/2004/07/showplan"}
IO_PATTERN = re.compile(
    r"Table '([^']+)'. Scan count (\d+), logical reads (\d+),", re.IGNORECASE
)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    required = ["MSSQL_SA_PASSWORD", "MSSQL_HOST", "MSSQL_PORT", "MSSQL_USER", "MSSQL_DATABASE"]
    missing = [key for key in required if not values.get(key)]
    if missing:
        raise RuntimeError(f"Missing required .env settings: {', '.join(missing)}")
    return values


def marked_queries(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    queries = {
        query_id: sql.strip()
        for query_id, sql in re.findall(
            r"-- BEGIN (Q\d+(?:[a-z]+(?:-count)?)?)\s*\n(.*?)\n-- END \1", text, flags=re.DOTALL
        )
    }
    expected = set(MAIN_TABLES)
    if set(queries) != expected:
        raise RuntimeError(f"Marked workload mismatch. Expected {sorted(expected)}, found {sorted(queries)}")
    return queries


def sqlcmd(env: dict[str, str], sql: str, *, statistics: bool) -> subprocess.CompletedProcess[str]:
    prefix = "SET NOCOUNT ON; "
    if statistics:
        prefix += "SET STATISTICS IO ON; SET STATISTICS XML ON; "
    command = [
        "docker", "exec", "-e", f"SQLCMDPASSWORD={env['MSSQL_SA_PASSWORD']}", CONTAINER,
        SQLCMD, "-C", "-S", f"{env['MSSQL_HOST']},{env['MSSQL_PORT']}",
        "-U", env["MSSQL_USER"], "-d", env["MSSQL_DATABASE"], "-b",
        "-y", "0", "-Y", "0", "-r", "1", "-Q", prefix + sql,
    ]
    completed = subprocess.run(command, text=True, capture_output=True, check=False)
    if completed.returncode:
        raise RuntimeError(
            "sqlcmd failed without exposing credentials:\n"
            + completed.stderr[-4000:]
            + completed.stdout[-4000:]
        )
    return completed


def extract_plan(output: str) -> str:
    start = output.find("<ShowPlanXML")
    end_tag = "</ShowPlanXML>"
    end = output.find(end_tag, start)
    if start < 0 or end < 0:
        raise RuntimeError("ShowPlanXML was absent from sqlcmd output.")
    return output[start : end + len(end_tag)]


def integer(value: str | None) -> int:
    return int(float(value or "0"))


def plan_accesses(plan_xml: str) -> tuple[dict[str, dict[str, object]], int]:
    root = ET.fromstring(plan_xml)
    accesses: dict[str, dict[str, object]] = defaultdict(
        lambda: {"logical_reads": 0, "scan_count": 0, "operators": [], "estimated_rows": 0.0, "actual_rows": 0}
    )
    root_actual_rows = 0
    for relop in root.findall(".//p:RelOp", SHOWPLAN_NS):
        obj = relop.find(".//p:Object", SHOWPLAN_NS)
        table = obj.get("Table") if obj is not None else None
        if not table:
            continue
        table_name = table.strip("[]").split("].[", 1)[-1].strip("[]")
        runtime = relop.findall("./p:RunTimeInformation/p:RunTimeCountersPerThread", SHOWPLAN_NS)
        logical_reads = sum(integer(node.get("ActualLogicalReads")) for node in runtime)
        scans = sum(integer(node.get("ActualScans")) for node in runtime)
        actual_rows = sum(integer(node.get("ActualRows")) for node in runtime)
        entry = accesses[table_name]
        entry["logical_reads"] = int(entry["logical_reads"]) + logical_reads
        entry["scan_count"] = int(entry["scan_count"]) + scans
        entry["actual_rows"] = int(entry["actual_rows"]) + actual_rows
        entry["estimated_rows"] = float(entry["estimated_rows"]) + float(relop.get("EstimateRows", "0"))
        entry["operators"].append((logical_reads, relop.get("PhysicalOp", "Unknown")))
        if relop.get("NodeId") == "0" and runtime:
            root_actual_rows = actual_rows
        elif root_actual_rows == 0 and runtime:
            # Some plans place a presentation-only Compute Scalar at Node 0
            # without runtime counters.  The first executable child then owns
            # the SELECT result cardinality (as in Q9's merge join).
            root_actual_rows = actual_rows
    return accesses, root_actual_rows


def io_accesses(stderr: str) -> dict[str, tuple[int, int]]:
    totals: dict[str, tuple[int, int]] = {}
    for table, scans, reads in IO_PATTERN.findall(stderr):
        old_scans, old_reads = totals.get(table, (0, 0))
        totals[table] = (old_scans + int(scans), old_reads + int(reads))
    return totals


def capture_storage(env: dict[str, str]) -> list[dict[str, str]]:
    storage_sql = """
SELECT CONCAT(s.name, '|', t.name, '|',
       COALESCE(SUM(CASE WHEN ps.index_id IN (0,1) THEN ps.row_count ELSE 0 END), 0), '|',
       COALESCE(SUM(CASE WHEN ps.index_id IN (0,1) THEN ps.in_row_data_page_count + ps.lob_used_page_count + ps.row_overflow_used_page_count ELSE 0 END) * 8, 0), '|',
       COALESCE(SUM(CASE WHEN ps.index_id > 1 THEN ps.used_page_count ELSE 0 END) * 8, 0), '|',
       COALESCE(SUM(ps.used_page_count) * 8, 0))
FROM sys.objects AS t
JOIN sys.schemas AS s ON s.schema_id = t.schema_id
LEFT JOIN sys.dm_db_partition_stats AS ps ON ps.object_id = t.object_id
WHERE t.is_ms_shipped = 0 AND t.type IN ('U', 'V')
GROUP BY s.name, t.name
ORDER BY s.name, t.name;
"""
    output = sqlcmd(env, storage_sql, statistics=False).stdout
    records = []
    for line in output.splitlines():
        fields = [field.strip() for field in line.split("|")]
        if len(fields) == 6 and fields[2].isdigit():
            records.append(dict(zip(("schema_name", "table_name", "row_count", "data_kb", "index_kb", "total_kb"), fields)))
    if len(records) < 42:
        raise RuntimeError(f"Storage inventory expected at least 42 user tables, found {len(records)}.")
    return records


def capture_inventory(env: dict[str, str]) -> None:
    index_sql = """
SELECT t.name AS table_name, i.name AS index_name, i.type_desc,
       i.is_primary_key, i.is_unique_constraint
FROM sys.indexes AS i
JOIN sys.tables AS t ON i.object_id = t.object_id
WHERE i.type > 0 AND t.is_ms_shipped = 0
ORDER BY t.name, i.index_id;

SELECT COUNT(*) AS discretionary_index_count
FROM sys.indexes AS i
JOIN sys.tables AS t ON i.object_id = t.object_id
WHERE i.type > 0 AND t.is_ms_shipped = 0
  AND i.is_primary_key = 0 AND i.is_unique_constraint = 0;
"""
    fk_sql = """
;WITH FKColumns AS (
    SELECT fk.name AS fk_name, OBJECT_NAME(fkc.parent_object_id) AS table_name,
           COL_NAME(fkc.parent_object_id, fkc.parent_column_id) AS column_name,
           fkc.constraint_column_id
    FROM sys.foreign_keys AS fk
    JOIN sys.foreign_key_columns AS fkc ON fkc.constraint_object_id = fk.object_id
)
SELECT fk_name, table_name, column_name
FROM FKColumns AS f
WHERE NOT EXISTS (
    SELECT 1
    FROM sys.indexes AS i
    JOIN sys.index_columns AS ic ON ic.object_id = i.object_id AND ic.index_id = i.index_id
    WHERE i.object_id = OBJECT_ID(N'dbo.' + QUOTENAME(f.table_name))
      AND i.type > 0 AND ic.key_ordinal = 1 AND ic.column_id = COLUMNPROPERTY(i.object_id, f.column_name, 'ColumnId')
)
ORDER BY table_name, fk_name, constraint_column_id;
"""
    (OUTPUT_DIR / "index_inventory.txt").write_text(sqlcmd(env, index_sql, statistics=False).stdout, encoding="utf-8")
    raw = sqlcmd(env, fk_sql, statistics=False).stdout
    rows = []
    for line in raw.splitlines():
        fields = [item.strip() for item in line.split()]
        if len(fields) == 3 and fields[0] != "fk_name":
            rows.append(fields)
    with (OUTPUT_DIR / "unindexed_fk_columns.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["fk_name", "table_name", "column_name"])
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", default="outputs/baseline",
        help="Project-relative directory for capture artifacts (default: %(default)s)",
    )
    parser.add_argument(
        "--indexed-view-set-options", action="store_true",
        help="Enable the SQL Server session SET options required for indexed-view matching.",
    )
    args = parser.parse_args()
    global OUTPUT_DIR, PLAN_DIR
    OUTPUT_DIR = ROOT / args.output_dir
    PLAN_DIR = OUTPUT_DIR / "plans"
    env = read_env(ENV_PATH)
    queries = marked_queries(WORKLOAD_PATH)
    PLAN_DIR.mkdir(parents=True, exist_ok=True)
    capture_inventory(env)

    results: list[dict[str, object]] = []
    query_counts: list[dict[str, object]] = []
    for query_id, query in queries.items():
        print(f"{query_id}: warm-up execution")
        set_options = "" if not args.indexed_view_set_options else (
            "SET ANSI_NULLS ON; SET ANSI_PADDING ON; SET ANSI_WARNINGS ON; "
            "SET ARITHABORT ON; SET CONCAT_NULL_YIELDS_NULL ON; SET QUOTED_IDENTIFIER ON; "
            "SET NUMERIC_ROUNDABORT OFF; "
        )
        sqlcmd(env, set_options + query, statistics=True)  # compilation/warm cache run; deliberately discarded
        print(f"{query_id}: captured execution")
        captured = sqlcmd(env, set_options + query, statistics=True)
        plan_xml = extract_plan(captured.stdout)
        (PLAN_DIR / f"{query_id}_baseline.sqlplan").write_text(plan_xml, encoding="utf-8")
        plan_tables, returned_rows = plan_accesses(plan_xml)
        io_tables = io_accesses(captured.stderr)
        query_counts.append({"query_id": query_id, "returned_rows": returned_rows})
        all_tables = sorted(set(plan_tables) | set(io_tables))
        for table in all_tables:
            if table.lower() in {"worktable", "workfile"}:
                continue
            plan_info = plan_tables.get(table, {})
            io_scans, io_reads = io_tables.get(table, (0, 0))
            operators = plan_info.get("operators", [])
            primary_operator = max(operators, default=(0, "Unknown"), key=lambda item: item[0])[1]
            main = table == MAIN_TABLES[query_id] or (
                query_id in {"Q4", "Q5"} and table == "vWellnessActivityEnrollmentYear"
            )
            results.append({
                "query_id": query_id,
                "table_name": table,
                "logical_reads": io_reads if table in io_tables else plan_info.get("logical_reads", 0),
                "scan_count": io_scans if table in io_tables else plan_info.get("scan_count", 0),
                "main_operator": primary_operator if main else "",
                "estimated_rows": f"{plan_info.get('estimated_rows', 0):.4f}" if main else "",
                "actual_rows": plan_info.get("actual_rows", 0) if main else "",
            })

    results_name = "baseline_results.csv" if OUTPUT_DIR.name == "baseline" else "results.csv"
    storage_name = "storage_baseline.csv" if OUTPUT_DIR.name == "baseline" else "storage.csv"
    with (OUTPUT_DIR / results_name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_id", "table_name", "logical_reads", "scan_count", "main_operator", "estimated_rows", "actual_rows"])
        writer.writeheader()
        writer.writerows(results)
    with (OUTPUT_DIR / "query_return_counts.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["query_id", "returned_rows"])
        writer.writeheader()
        writer.writerows(query_counts)
    storage = capture_storage(env)
    with (OUTPUT_DIR / storage_name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["schema_name", "table_name", "row_count", "data_kb", "index_kb", "total_kb"])
        writer.writeheader()
        writer.writerows(storage)
    print(f"Captured {len(queries)} query baselines, {len(results)} table-access rows, and {len(storage)} storage rows.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Baseline capture failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
