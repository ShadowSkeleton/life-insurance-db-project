"""Create a deterministic simulated BRFSS coding revision for pipeline demonstration.

This is a simulated revision created solely to demonstrate the Part 4
retraining pipeline. It does not represent an actual CDC data correction.
"""
from __future__ import annotations

import argparse
import csv
import random
from pathlib import Path

SEED = 20260729
TARGET_AGE_BAND_CODE = "6"
TARGET_SEX_CODE = "1"
DEFAULT_COUNT = 60


def numeric_code(value: str | None) -> str:
    """Normalise CSV numeric codes such as `1` and `1.0`."""
    if value is None:
        return ""
    return str(int(float(value)))


def revise(source: Path, output: Path, *, count: int = DEFAULT_COUNT, seed: int = SEED) -> list[int]:
    with source.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames
        if not fieldnames:
            raise ValueError("Source CSV has no header.")
        required = {"DIABETE4", "_AGEG5YR", "_SEX"}
        missing = required - set(fieldnames)
        if missing:
            raise ValueError(f"Source CSV lacks required columns: {sorted(missing)}")
        rows = list(reader)

    candidates = [
        index
        for index, row in enumerate(rows, start=1)
        if numeric_code(row["DIABETE4"]) == "1"
        and numeric_code(row["_AGEG5YR"]) == TARGET_AGE_BAND_CODE
        and numeric_code(row["_SEX"]) == TARGET_SEX_CODE
    ]
    if len(candidates) < count:
        raise ValueError(f"Only {len(candidates)} target rows are available; {count} are required.")

    changed = sorted(random.Random(seed).sample(candidates, count))
    for index in changed:
        rows[index - 1]["DIABETE4"] = "3"

    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path, help="Original curated CSV; it is never modified.")
    parser.add_argument("output", type=Path, help="Path for the revised CSV copy.")
    parser.add_argument("--count", type=int, default=DEFAULT_COUNT)
    parser.add_argument("--seed", type=int, default=SEED)
    args = parser.parse_args()
    changed = revise(args.source, args.output, count=args.count, seed=args.seed)
    print("SIMULATED SOURCE REVISION — not an actual CDC correction")
    print(f"source={args.source}")
    print(f"output={args.output}")
    print(f"seed={args.seed}; changed_count={len(changed)}")
    print("Changed CSV data-row identifiers (1-based; header excluded):")
    for index in changed:
        print(index)


if __name__ == "__main__":
    main()
