# Jingrui Feng (jf4446) - database systems project part 3 - brfss training frame builder
"""Build the BRFSS 2024 supervised-learning frame for diabetes prediction.

The source is the immutable Part 2 curated sample. This script uses no random
operations. It validates observed response codes before applying every recode
and writes a reproducible Parquet artifact only after its label sanity check.

Age bands are stored as explicit one-hot columns (``age_band_01`` through
``age_band_13``), which remain stable across Parquet round-trips and are ready
for scikit-learn. The original integer ``age_band`` remains available for
reporting and rate-table joins. This preserves BRFSS/risk-factor band
granularity and avoids interpolation for ages 80--99. ``age_midpoint_years``
is retained only as an auxiliary reporting and joining field.
"""

from __future__ import annotations

import argparse

from pathlib import Path
import sys

import pandas as pd


PART4_ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILE = PART4_ROOT / "data" / "curated" / "brfss_2024_life_risk_sample_50000.csv"
OUTPUT_FILE = PART4_ROOT / "data" / "processed" / "brfss_training.parquet"

INSPECTION_COLUMNS = [
    "DIABETE4",
    "_AGEG5YR",
    "_SEX",
    "_SMOKER3",
    "_BMI5",
    "EXERANY2",
    "_TOTINDA",
]

# The source 2024 BRFSS codebook defines _AGEG5YR 1 as 18--24 and 13 as
# 80--99. Code 13 is therefore not a five-year band; its midpoint is 89.5.
AGE_MIDPOINTS = {
    1: 21.0,
    2: 27.0,
    3: 32.0,
    4: 37.0,
    5: 42.0,
    6: 47.0,
    7: 52.0,
    8: 57.0,
    9: 62.0,
    10: 67.0,
    11: 72.0,
    12: 77.0,
    13: 89.5,
}
AGE_BAND_FEATURES = [f"age_band_{age_band:02d}" for age_band in AGE_MIDPOINTS]

# These are the inputs to a future scikit-learn model. The midpoint and
# unencoded age-band code are deliberately excluded; both remain for joins.
MODEL_FEATURES = AGE_BAND_FEATURES + ["sex", "smoking_status", "exercise", "bmi"]


def print_inspection(frame: pd.DataFrame) -> None:
    """Print the required source-level column and value-count inspection."""
    print("BRFSS source inspection")
    print(f"Rows: {len(frame):,}")
    print(f"Columns ({len(frame.columns)}): {frame.columns.tolist()}")

    for column in INSPECTION_COLUMNS:
        print(f"\n{column}")
        if column not in frame.columns:
            print("  present: False")
            continue
        print(f"  present: True")
        print(f"  dtype: {frame[column].dtype}")
        print("  value_counts (including null):")
        print(frame[column].value_counts(dropna=False).to_string())


def print_age_midpoint_mapping() -> None:
    """Print every verified BRFSS age-band-to-midpoint mapping."""
    print("\n_AGEG5YR code-to-midpoint mapping (years)")
    for age_band, midpoint in AGE_MIDPOINTS.items():
        print(f"  {age_band:>2} -> {midpoint:g}")


def verify_activity_redundancy(frame: pd.DataFrame) -> None:
    """Verify valid activity responses map one-to-one before using _TOTINDA."""
    if "EXERANY2" not in frame.columns:
        print("\nEXERANY2 is absent; _TOTINDA will be used without a redundancy crosstab.")
        return

    activity_crosstab = pd.crosstab(frame["EXERANY2"], frame["_TOTINDA"], dropna=False)
    print("\nEXERANY2 / _TOTINDA raw crosstab (before filtering)")
    print(activity_crosstab.to_string())

    valid_submatrix = activity_crosstab.reindex(index=[1.0, 2.0], columns=[1.0, 2.0], fill_value=0)
    off_diagonal_count = int(valid_submatrix.loc[1.0, 2.0] + valid_submatrix.loc[2.0, 1.0])
    if off_diagonal_count:
        raise ValueError(
            "EXERANY2 and _TOTINDA disagree among valid responses: "
            f"{off_diagonal_count} off-diagonal rows. _TOTINDA was not substituted."
        )


def ensure_expected_values(series: pd.Series, allowed: set[int], name: str) -> None:
    """Stop rather than silently recoding a response value outside the spec."""
    observed = set(series.dropna().astype(int).unique())
    unexpected = observed - allowed
    if unexpected:
        raise ValueError(
            f"{name} has observed values outside the documented mapping: "
            f"{sorted(unexpected)}. Observed values: {sorted(observed)}"
        )


def record_audit(audit: list[dict[str, int]], step: str, before: int, after: int) -> None:
    audit.append(
        {
            "step": step,
            "rows_remaining": after,
            "rows_removed_this_step": before - after,
        }
    )


def main(source_file: Path = SOURCE_FILE, output_file: Path = OUTPUT_FILE) -> None:
    if not source_file.exists():
        raise FileNotFoundError(f"Curated BRFSS source not found: {source_file}")

    source = pd.read_csv(source_file)
    print_inspection(source)
    print_age_midpoint_mapping()

    # _TOTINDA is included specifically as the documented fallback for a
    # missing EXERANY2. Every other inspection field is mandatory.
    missing = [
        column
        for column in INSPECTION_COLUMNS
        if column not in source.columns and column != "EXERANY2"
    ]
    if missing:
        raise ValueError(
            "Required BRFSS columns are absent; no replacements were used: "
            + ", ".join(missing)
        )

    ensure_expected_values(source["DIABETE4"], {1, 2, 3, 4, 7, 9}, "DIABETE4")
    ensure_expected_values(source["_AGEG5YR"], set(range(1, 15)), "_AGEG5YR")
    ensure_expected_values(source["_SEX"], {1, 2}, "_SEX")
    ensure_expected_values(source["_SMOKER3"], {1, 2, 3, 4, 9}, "_SMOKER3")
    ensure_expected_values(source["_TOTINDA"], {1, 2, 9}, "_TOTINDA")
    if "EXERANY2" in source.columns:
        ensure_expected_values(source["EXERANY2"], {1, 2, 7, 9}, "EXERANY2")

    verify_activity_redundancy(source)

    if not pd.api.types.is_numeric_dtype(source["_BMI5"]):
        raise ValueError("_BMI5 is not numeric, so its implied-decimal recode was not applied.")

    audit: list[dict[str, int]] = []
    frame = source.copy()
    record_audit(audit, "Source rows", len(frame), len(frame))

    before = len(frame)
    frame = frame.loc[frame["DIABETE4"].isin([1, 3, 4])].copy()
    record_audit(
        audit,
        "DIABETE4: drop gestational (2) and nonresponse (7, 9)",
        before,
        len(frame),
    )

    before = len(frame)
    frame = frame.loc[frame["_AGEG5YR"].isin(AGE_MIDPOINTS)].copy()
    record_audit(audit, "_AGEG5YR: drop unknown (14)", before, len(frame))

    before = len(frame)
    frame = frame.loc[frame["_SMOKER3"].isin([1, 2, 3, 4])].copy()
    record_audit(audit, "_SMOKER3: drop unknown (9)", before, len(frame))

    before = len(frame)
    frame = frame.loc[frame["_TOTINDA"].isin([1, 2])].copy()
    record_audit(
        audit,
        "_TOTINDA: drop nonresponse (9)",
        before,
        len(frame),
    )

    before = len(frame)
    frame = frame.loc[frame["_BMI5"].notna()].copy()
    record_audit(audit, "_BMI5: drop nulls", before, len(frame))

    frame["age_band"] = frame["_AGEG5YR"].astype("int8")
    for age_band, feature_name in zip(AGE_MIDPOINTS, AGE_BAND_FEATURES, strict=True):
        frame[feature_name] = (frame["age_band"] == age_band).astype("int8")
    frame["age_midpoint_years"] = frame["age_band"].map(AGE_MIDPOINTS).astype("float32")
    frame["sex"] = frame["_SEX"].map({1: "male", 2: "female"}).astype("string")
    frame["smoking_status"] = frame["_SMOKER3"].map(
        {1: "current", 2: "current", 3: "former", 4: "never"}
    ).astype("string")
    frame["exercise"] = frame["_TOTINDA"].map({1: "yes", 2: "no"}).astype("string")
    frame["bmi"] = (frame["_BMI5"] / 100).astype("float32")
    frame["diabetes_response"] = frame["DIABETE4"].astype("int8")

    # Response 4 remains available for sensitivity analysis but is excluded
    # from the primary label rather than being silently dropped from the frame.
    frame["label"] = frame["DIABETE4"].map({1: 1, 3: 0}).astype("Int8")
    frame["label_sensitivity"] = frame["DIABETE4"].map({1: 1, 3: 0, 4: 1}).astype("int8")

    training = frame[
        [
            "diabetes_response",
            "label",
            "label_sensitivity",
            "age_band",
            *AGE_BAND_FEATURES,
            "age_midpoint_years",
            "sex",
            "smoking_status",
            "exercise",
            "bmi",
        ]
    ].reset_index(drop=True)

    audit_table = pd.DataFrame(audit)
    primary_distribution = training["label"].value_counts(normalize=True, dropna=True).sort_index()
    primary_prevalence = primary_distribution.get(1, 0.0)

    print("\nFilter audit")
    print(audit_table.to_string(index=False))
    print("\nPrimary-label note: DIABETE4=4 is retained with label=<NA> and label_sensitivity=1.")
    print(f"\nFinal row count: {len(training):,}")
    print("\nPrimary label distribution (normalized; excludes <NA>):")
    print(primary_distribution.rename("proportion").to_string())
    print("\nPrimary-label rows available for model fitting:", f"{training['label'].notna().sum():,}")
    print("\nModel features (age_band is one-hot; age_midpoint_years intentionally excluded):")
    for feature in MODEL_FEATURES:
        print(f"  {feature}: {training[feature].dtype}")
    print("\nNumeric predictor describe():")
    print(training[["age_midpoint_years", "bmi"]].describe().to_string())
    primary_training = training.loc[training["label"].notna()]
    for categorical in ["age_band", "sex", "smoking_status", "exercise"]:
        print(f"\nCrosstab: label by {categorical} (primary label only)")
        print(
            pd.crosstab(
                primary_training[categorical], primary_training["label"], dropna=False
            ).to_string()
        )

    if not 0.08 <= primary_prevalence <= 0.16:
        raise ValueError(
            "Primary diabetes prevalence is outside the expected 0.08--0.16 range: "
            f"{primary_prevalence:.4f}. Parquet was not written."
        )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    training.to_parquet(output_file, index=False, engine="pyarrow")
    print(f"\nWrote training frame: {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-file", type=Path, default=SOURCE_FILE)
    parser.add_argument("--output-file", type=Path, default=OUTPUT_FILE)
    args = parser.parse_args()
    try:
        main(args.source_file, args.output_file)
    except (FileNotFoundError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1) from error
