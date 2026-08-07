# Jingrui Feng (jf4446) - database systems project part 3 - measurement summary builder
"""Write all-tables-touched logical-read summaries for saved measurement runs."""
from __future__ import annotations

import csv
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNS = ("baseline", "increment1", "increment2", "increment3", "corrections")


def result_path(run_dir: Path) -> Path:
    baseline = run_dir / "baseline_results.csv"
    return baseline if baseline.exists() else run_dir / "results.csv"


for run_name in RUNS:
    directory = ROOT / "outputs" / run_name
    source = result_path(directory)
    if not source.exists():
        continue
    totals: dict[str, int] = defaultdict(int)
    with source.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            totals[row["query_id"]] += int(row["logical_reads"])
    with (directory / "query_summary_all_tables.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["query_id", "logical_reads_all_tables_touched"])
        writer.writerows(sorted(totals.items()))
    print(f"{run_name}: {len(totals)} query summaries")
