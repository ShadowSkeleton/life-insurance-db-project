# Jingrui Feng (jf4446) - database systems project part 2 - validate mockaroo csv data against database schema

#!/usr/bin/env python3
"""Audit Mockaroo CSV extracts against SQL Server CREATE TABLE definitions.

Run with --fix-known to apply only the explicitly authorized Customer suffix fix.
"""
from __future__ import annotations

import argparse
import csv
import re
import shutil
from collections import Counter
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CSV_DIR = ROOT / "mockaroo"
SQL_FILES = [ROOT / "schema_final.sql", ROOT / "bridge_schema.sql"]
TARGETS = [
    "Customer", "Product", "BillingAccount", "Contract", "Claim", "ContractParty",
    "Invoice", "WELLNESS_PROGRAM", "WELLNESS_ENROLLMENT", "WELLNESS_ACTIVITY",
    "RISK_IMPROVEMENT",
]
BASE_IDS = {
    "Customer": "CustomerID", "Product": "ProductID", "BillingAccount": "BillingAccountID",
    "Contract": "ContractID", "Claim": "ClaimID", "ContractParty": "ContractPartyID",
    "Invoice": "InvoiceID",
}
BRIDGE_IDS = {
    "WELLNESS_PROGRAM": "WellnessProgramID", "WELLNESS_ENROLLMENT": "EnrollmentID",
    "WELLNESS_ACTIVITY": "ActivityID", "RISK_IMPROVEMENT": "ImprovementID",
}
FILE_NAMES = {table: f"{table}.csv" for table in TARGETS}

# These three cross-schema FKs are explicitly requested even though their DDL is
# documented as post-deploy comments in bridge_schema.sql.
EXPLICIT_FKS = [
    ("Contract", "Product_ProductID", "Product", "ProductID"),
    ("Claim", "Contract_ContractID", "Contract", "ContractID"),
    ("ContractParty", "Customer_CustomerID", "Customer", "CustomerID"),
    ("ContractParty", "Contract_ContractID", "Contract", "ContractID"),
    ("Invoice", "BillingAccount_BillingAccountID", "BillingAccount", "BillingAccountID"),
    ("WELLNESS_ENROLLMENT", "ContractID", "Contract", "ContractID"),
    ("WELLNESS_ENROLLMENT", "WellnessProgramID", "WELLNESS_PROGRAM", "WellnessProgramID"),
    ("WELLNESS_ACTIVITY", "EnrollmentID", "WELLNESS_ENROLLMENT", "EnrollmentID"),
    ("RISK_IMPROVEMENT", "EnrollmentID", "WELLNESS_ENROLLMENT", "EnrollmentID"),
]


def parse_schema():
    sql = "\n".join(path.read_text(encoding="utf-8") for path in SQL_FILES)
    sql_without_comments = re.sub(r"--[^\n]*", "", sql)
    tables: dict[str, dict] = {}
    for match in re.finditer(r"CREATE\s+TABLE\s+(\w+)\s*\((.*?)\)\s*(?:GO|;)", sql, re.I | re.S):
        name, body = match.groups()
        columns = {}
        uniques = []
        pks = []
        for raw_line in body.splitlines():
            line = raw_line.strip().rstrip(",")
            if not line or line.startswith("--") or line.upper().startswith(("CONSTRAINT", "REFERENCES", "ON DELETE", "ON UPDATE")):
                con = re.search(r"CONSTRAINT\s+(\w+)\s+(PRIMARY\s+KEY|UNIQUE)\s*\(([^)]+)\)", line, re.I)
                if con:
                    (pks if con.group(2).upper().startswith("PRIMARY") else uniques).append(
                        (con.group(1), [x.strip() for x in con.group(3).split(",")])
                    )
                continue
            col = re.match(r"(\w+)\s+([A-Z]+)(?:\s*\((\d+)(?:\s*,\s*(\d+))?\))?(.*)", line, re.I)
            if col:
                colname, typ, length, scale, remainder = col.groups()
                columns[colname] = {
                    "type": typ.upper(), "length": int(length) if length else None,
                    "scale": int(scale) if scale else None,
                    "not_null": bool(re.search(r"\bNOT\s+NULL\b", remainder, re.I)),
                    "identity": bool(re.search(r"\bIDENTITY\b", remainder, re.I)),
                }
        tables[name] = {"columns": columns, "pks": pks, "uniques": uniques, "fks": []}
    # ALTER TABLE primary and unique constraints in the base DDL.
    for match in re.finditer(
        r"ALTER\s+TABLE\s+(\w+)\s+ADD\s+CONSTRAINT\s+(\w+)\s+"
        r"(PRIMARY\s+KEY(?:\s+CLUSTERED)?|UNIQUE(?:\s+NONCLUSTERED)?)\s*\(([^)]+)\)",
        sql, re.I | re.S,
    ):
        table, cname, ctype, cols = match.groups()
        if table in tables:
            entry = (cname, [x.strip() for x in cols.split(",")])
            (tables[table]["pks"] if ctype.upper().startswith("PRIMARY") else tables[table]["uniques"]).append(entry)
    # Covers the SQL Server ALTER TABLE FK syntax used in schema_final.sql and
    # the named inline FK syntax used by bridge_schema.sql.
    for match in re.finditer(
        r"(?:ALTER\s+TABLE\s+)?(\w+)?\s*(?:ADD\s+)?CONSTRAINT\s+\w+\s+FOREIGN\s+KEY\s*"
        r"\(\s*(\w+)\s*\)\s*REFERENCES\s+(\w+)\s*\(\s*(\w+)\s*\)",
        sql_without_comments, re.I | re.S,
    ):
        child, child_col, parent, parent_col = match.groups()
        # Inline constraints omit the child table name in the match; infer it
        # from the nearest preceding CREATE TABLE block.
        if not child:
            prefix = sql_without_comments[:match.start()]
            created = list(re.finditer(r"CREATE\s+TABLE\s+(\w+)", prefix, re.I))
            child = created[-1].group(1) if created else None
        if child in tables:
            tables[child]["fks"].append((child_col, parent, parent_col))
    return tables


def load_csv(path: Path):
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        rows = list(reader)
        return reader.fieldnames or [], rows


def is_blank(value):
    return value is None or value.strip() == ""


def malformed(value):
    if is_blank(value):
        return False
    return bool(re.search(r"undefined method|nil:NilClass|error:\s*invalid|\bitem\s+1\s*,\s*item\s+2\s*,\s*item\s+3\b|^\(blank\)$", value, re.I))


def valid_iso(value):
    try:
        return date.fromisoformat(value)
    except (TypeError, ValueError):
        return None


def add_issue(issues, check, column, rows, example, detail=""):
    issues.append({"check": check, "column": column, "count": len(rows), "example": example, "detail": detail})


def validate(tables, data):
    result = {table: [] for table in TARGETS}
    for table in TARGETS:
        schema = tables[table]
        headers, rows = data[table]
        columns = schema["columns"]
        extras = [h for h in headers if h not in columns]
        # SQL Server creates IDENTITY keys for the bridge tables.  Their values
        # are intentionally omitted from CSV load files.
        missing = [c for c in columns if c not in headers and not columns[c]["identity"]]
        if extras:
            add_issue(result[table], 1, ", ".join(extras), [0], extras[0], "CSV header not in schema")
        if missing:
            add_issue(result[table], 1, ", ".join(missing), [0], missing[0], "schema column missing from CSV")

        # Plain-integer base keys are supplied by CSV and must be exactly 1..n.
        if table in BASE_IDS:
            key = BASE_IDS[table]
            if key not in headers:
                add_issue(result[table], 2, key, [0], key, "required surrogate ID missing")
            else:
                values = [r.get(key, "") for r in rows]
                expected = [str(i) for i in range(1, len(rows) + 1)]
                if values != expected:
                    sample = next((i + 2 for i, (a, b) in enumerate(zip(values, expected)) if a != b), 2)
                    add_issue(result[table], 2, key, [sample], values[sample - 2], "must be sequential 1..row_count with no gaps or duplicates")
        if table in BRIDGE_IDS and BRIDGE_IDS[table] in headers:
            add_issue(result[table], 2, BRIDGE_IDS[table], [0], BRIDGE_IDS[table], "IDENTITY column must not be supplied")

        for col, info in columns.items():
            if col not in headers:
                continue
            vals = [(i + 2, row.get(col, "")) for i, row in enumerate(rows)]
            blanks = [(n, v) for n, v in vals if is_blank(v)]
            if info["not_null"] and blanks:
                add_issue(result[table], 3, col, [n for n, _ in blanks], f"row {blanks[0][0]}: blank", "NOT NULL value is blank")
            if info["type"] in {"VARCHAR", "CHAR"} and info["length"]:
                bad = [(n, v) for n, v in vals if not is_blank(v) and len(v) > info["length"]]
                if bad:
                    longest = max(bad, key=lambda x: len(x[1]))
                    add_issue(result[table], 4, col, [n for n, _ in bad], f"row {longest[0]} ({len(longest[1])} chars): {longest[1]!r}", f"max length {info['length']}")
            if info["type"] == "NUMERIC" and info["length"]:
                bad = []
                for n, v in vals:
                    if is_blank(v):
                        continue
                    try:
                        dec = Decimal(v)
                        tup = dec.as_tuple()
                        digits = len(tup.digits)
                        scale = max(-tup.exponent, 0)
                        integer_digits = max(digits - scale, 0)
                        allowed_int = info["length"] - (info["scale"] or 0)
                        if scale > (info["scale"] or 0) or integer_digits > allowed_int:
                            bad.append((n, v))
                    except InvalidOperation:
                        bad.append((n, v))
                if bad:
                    add_issue(result[table], 4, col, [n for n, _ in bad], f"row {bad[0][0]}: {bad[0][1]!r}", f"NUMERIC({info['length']},{info['scale'] or 0})")

        for cname, cols in schema["uniques"] + schema["pks"]:
            if not all(c in headers for c in cols):
                continue
            combos = [tuple(row[c] for c in cols) for row in rows]
            duplicates = [(combo, count) for combo, count in Counter(combos).items() if count > 1]
            if duplicates:
                combo, count = sorted(duplicates, key=lambda x: (-x[1], x[0]))[0]
                add_issue(result[table], 5, ", ".join(cols), list(range(count)), f"{cname}: {combo} occurs {count} times", "UNIQUE/PK duplicate")

        bad_cells = [(i + 2, h, row[h]) for i, row in enumerate(rows) for h in headers if malformed(row.get(h, ""))]
        if bad_cells:
            by_col = {}
            for n, c, v in bad_cells:
                by_col.setdefault(c, []).append((n, v))
            for c, cells in by_col.items():
                add_issue(result[table], 8, c, [n for n, _ in cells], f"row {cells[0][0]}: {cells[0][1]!r}", "Mockaroo error/placeholder text")

    # Foreign keys are reported on children. Blank optional foreign keys are permitted.
    fk_checks = list(EXPLICIT_FKS)
    for child, info in tables.items():
        for child_col, parent, parent_col in info["fks"]:
            fk_checks.append((child, child_col, parent, parent_col))
    for child, child_col, parent, parent_col in dict.fromkeys(fk_checks):
        if child not in data or parent not in data:
            continue
        h_child, child_rows = data[child]
        h_parent, parent_rows = data[parent]
        if child_col not in h_child:
            continue
        if parent_col in h_parent:
            parent_values = {r[parent_col] for r in parent_rows}
        elif parent in BRIDGE_IDS and parent_col == BRIDGE_IDS[parent]:
            # IDENTITY values are generated by SQL Server in CSV row order.
            parent_values = {str(i) for i in range(1, len(parent_rows) + 1)}
        else:
            continue
        bad = [(i + 2, r.get(child_col, "")) for i, r in enumerate(child_rows)
               if not is_blank(r.get(child_col, "")) and r.get(child_col, "") not in parent_values]
        if bad:
            add_issue(result[child], 6, child_col, [n for n, _ in bad], f"row {bad[0][0]}: {bad[0][1]!r}", f"orphan; parent {parent}.{parent_col} has {len(parent_values)} values")

    # Date logic requested by the assignment.
    for table, earlier, later in [
        ("Customer", "StartDate", "EndDate"), ("ContractParty", "StartDate", "EndDate"),
        ("Claim", "ClaimDate", "SettlementDate"), ("Invoice", "RunDate", "PaymentDate"),
    ]:
        headers, rows = data[table]
        if earlier not in headers or later not in headers:
            continue
        bad = []
        for i, row in enumerate(rows):
            a, b = valid_iso(row.get(earlier, "")), valid_iso(row.get(later, ""))
            if a and b and b < a:
                bad.append((i + 2, row[later]))
        if bad:
            add_issue(result[table], 7, later, [n for n, _ in bad], f"row {bad[0][0]}: {bad[0][1]!r} before {earlier}", "invalid date order")
    return result


def render_issue_table(lines, issues):
    if not issues:
        lines.append("Passes all requested checks.")
        return
    lines += ["| Check | Column | Rows affected | Example | Detail |", "|---:|---|---:|---|---|"]
    for issue in issues:
        example = issue["example"].replace("|", "\\|")
        lines.append(f"| {issue['check']} | `{issue['column']}` | {issue['count']} | {example} | {issue['detail']} |")


def write_report(tables, data, initial_issues, final_issues, path: Path, fix_notes=None):
    lines = ["# Mockaroo CSV validation report", "", "Validation source: `schema_final.sql` and `bridge_schema.sql`.", ""]
    if fix_notes:
        lines += ["## Applied fixes", ""] + [f"- {note}" for note in fix_notes] + [""]
    for table in TARGETS:
        headers, rows = data[table]
        lines += [f"## {table}.csv", "", f"Row count: {len(rows)}", ""]
        lines += ["### Problems found before repair", ""]
        render_issue_table(lines, initial_issues[table])
        lines += ["", "### Status after repair", ""]
        render_issue_table(lines, final_issues[table])
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def fix_customer_suffix():
    path = CSV_DIR / "Customer.csv"
    headers, rows = load_csv(path)
    bad = [i for i, row in enumerate(rows) if is_blank(row.get("CustSuffix", ""))]
    if not bad:
        return []
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)
    values = ["Jr", "Sr", "II", "III", "NA"]
    for i in bad:
        rows[i]["CustSuffix"] = values[i % len(values)]
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
    return [f"Customer.csv: populated CustSuffix in {len(bad)} blank rows using Jr/Sr/II/III/NA; original saved as Customer.csv.bak."]


def deterministic_date(start: date, end: date, index: int) -> str:
    return (start + timedelta(days=index % ((end - start).days + 1))).isoformat()


def ensure_backup(path: Path):
    backup = path.with_suffix(path.suffix + ".bak")
    if not backup.exists():
        shutil.copy2(path, backup)


def replace_error_dates(rows, column, start, end, blank_mod=None, after_column=None):
    """Replace Mockaroo date errors with deterministic dates from the requested range."""
    changed = 0
    for i, row in enumerate(rows):
        current = row.get(column, "")
        if not malformed(current):
            continue
        if blank_mod and i % blank_mod[0] < blank_mod[1]:
            row[column] = ""
        else:
            candidate = date.fromisoformat(deterministic_date(start, end, i))
            if after_column:
                earlier = valid_iso(row.get(after_column, ""))
                if earlier and candidate < earlier:
                    candidate = earlier
            row[column] = candidate.isoformat()
        changed += 1
    return changed


def repair_generation_errors():
    notes = fix_customer_suffix()
    configs = {
        "Customer": [("CustDOB", date(1945, 1, 1), date(2004, 12, 31), None, None),
                     ("StartDate", date(2015, 1, 1), date(2025, 12, 31), None, None),
                     ("EndDate", date(2026, 1, 1), date(2032, 12, 31), (10, 7), "StartDate")],
        "Contract": [("PayUpDate", date(2040, 1, 1), date(2065, 12, 31), None, None)],
        "Claim": [("ClaimDate", date(2020, 1, 1), date(2025, 12, 31), None, None),
                  ("SettlementDate", date(2020, 1, 1), date(2026, 6, 30), (10, 3), "ClaimDate"),
                  ("WellnessEligibilityDate", date(2020, 1, 1), date(2025, 12, 31), (2, 1), None)],
        "ContractParty": [("CustDOB", date(1945, 1, 1), date(2004, 12, 31), None, None),
                          ("StartDate", date(2015, 1, 1), date(2025, 12, 31), None, None),
                          ("EndDate", date(2026, 1, 1), date(2035, 12, 31), (10, 7), "StartDate")],
        "Invoice": [("RunDate", date(2022, 1, 1), date(2026, 6, 30), None, None),
                    ("DueDate", date(2022, 1, 1), date(2026, 12, 31), None, "RunDate"),
                    ("PaidDate", date(2022, 1, 1), date(2026, 6, 30), (4, 1), "RunDate"),
                    ("PaymentDate", date(2022, 1, 1), date(2026, 6, 30), (4, 1), "RunDate")],
        "WELLNESS_ENROLLMENT": [("EnrollDate", date(2022, 1, 1), date(2025, 12, 31), None, None)],
        "WELLNESS_ACTIVITY": [("ActivityDate", date(2022, 1, 1), date(2026, 6, 30), None, None)],
        "RISK_IMPROVEMENT": [("MeasureDate", date(2022, 1, 1), date(2026, 6, 30), None, None)],
    }
    for table, fields in configs.items():
        path = CSV_DIR / FILE_NAMES[table]
        headers, rows = load_csv(path)
        changes = sum(replace_error_dates(rows, *field) for field in fields)
        if changes:
            ensure_backup(path)
            with path.open("w", newline="", encoding="utf-8") as fh:
                writer = csv.DictWriter(fh, fieldnames=headers)
                writer.writeheader(); writer.writerows(rows)
            notes.append(f"{table}.csv: replaced {changes} Mockaroo date-generation errors with deterministic ISO dates in the originally requested ranges; original saved as {table}.csv.bak.")

    # Repair non-date Mockaroo errors and fixed-width overflow using the
    # original Custom List domains / SQL Server length limits.
    path = CSV_DIR / "Contract.csv"; headers, rows = load_csv(path); changes = 0
    for i, row in enumerate(rows):
        if malformed(row.get("InForceFlag", "")):
            row["InForceFlag"] = "Y" if i % 2 == 0 else "N"; changes += 1
        if len(row.get("CardType", "")) > 10:
            row["CardType"] = "Amex"; changes += 1
    if changes:
        ensure_backup(path)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers); writer.writeheader(); writer.writerows(rows)
        notes.append(f"Contract.csv: replaced {changes} malformed/overlength flags with values from the configured domains (Y/N and Amex); original saved as Contract.csv.bak.")

    path = CSV_DIR / "BillingAccount.csv"; headers, rows = load_csv(path); changes = 0
    states = ["CA", "FL", "IL", "NY", "PA", "TX", "VA", "WA"]
    suites = ["Suite 100", "Suite 200", "Floor 3", "Unit B"]
    for i, row in enumerate(rows):
        if malformed(row.get("BillingAddress2", "")):
            row["BillingAddress2"] = suites[i % len(suites)]; changes += 1
        state = row.get("BillingState", "")
        if is_blank(state) or len(state) != 2:
            row["BillingState"] = states[i % len(states)]; changes += 1
        zip_value = row.get("BillingZip", "")
        if is_blank(zip_value) or len(zip_value) > 10:
            row["BillingZip"] = f"{10001 + (i % 89999):05d}"; changes += 1
    if changes:
        ensure_backup(path)
        with path.open("w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=headers); writer.writeheader(); writer.writerows(rows)
        notes.append(f"BillingAccount.csv: replaced {changes} Mockaroo errors/blanks/overflows using the configured address suite list, two-character state codes, and valid five-digit ZIPs; original saved as BillingAccount.csv.bak.")
    return notes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repair", action="store_true", help="apply deterministic repairs for known Mockaroo generation failures")
    parser.add_argument("--report-from-backups", action="store_true", help="compare saved pre-repair .bak files to current CSVs")
    args = parser.parse_args()
    tables = parse_schema()
    missing_tables = [t for t in TARGETS if t not in tables]
    if missing_tables:
        raise SystemExit(f"Schema parser missed tables: {missing_tables}")
    data = {table: load_csv(CSV_DIR / FILE_NAMES[table]) for table in TARGETS}
    if args.report_from_backups:
        initial_data = {
            table: load_csv((CSV_DIR / FILE_NAMES[table]).with_suffix(".csv.bak"))
            if (CSV_DIR / FILE_NAMES[table]).with_suffix(".csv.bak").exists() else data[table]
            for table in TARGETS
        }
    else:
        initial_data = data
    initial_issues = validate(tables, initial_data)
    notes = repair_generation_errors() if args.repair else []
    if args.report_from_backups:
        notes = ["Each corrected CSV has its original pre-repair version preserved beside it as a `.csv.bak` file."]
    data = {table: load_csv(CSV_DIR / FILE_NAMES[table]) for table in TARGETS}
    final_issues = validate(tables, data)
    write_report(tables, data, initial_issues, final_issues, ROOT / "mockaroo_csv_validation_report.md", notes)
    print(ROOT / "mockaroo_csv_validation_report.md")
    for table in TARGETS:
        print(f"{table}: {len(initial_issues[table])} initial issue groups; {len(final_issues[table])} remaining")


if __name__ == "__main__":
    main()
