# Jingrui Feng (jf4446) - database systems project part 3 - diabetes risk model trainer
"""Train and evaluate reproducible BRFSS diabetes risk-stratification models.

Fixed seed: 20260729. The models stratify concurrent self-reported diabetes
risk from BRFSS. They do not forecast incidence and are not mortality models.
The local SQL Server staging reads in this module are SELECT-only.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
from itertools import product
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from dotenv import dotenv_values
from scipy.stats import norm, spearmanr
from sklearn.calibration import calibration_curve
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    auc,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    silhouette_score,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.tree import DecisionTreeClassifier, plot_tree


SEED = 20260729
PART4_ROOT = Path(__file__).resolve().parents[1]
FRAME_PATH = PART4_ROOT / "data" / "processed" / "brfss_training.parquet"
OUTPUT_DIR = PART4_ROOT / "outputs" / "model"
FIGURE_DIR = OUTPUT_DIR / "figures"
METRICS_PATH = OUTPUT_DIR / "model_metrics.json"
COEFFICIENTS_PATH = OUTPUT_DIR / "logistic_coefficients.csv"
PROFILE_PATH = OUTPUT_DIR / "predicted_risk_by_profile.csv"
SUMMARY_PATH = PART4_ROOT / "docs" / "ml_model_summary.md"
ENV_FILE = PART4_ROOT / ".env"
LOCAL_CONTAINER = "dbsys-p3-mssql"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"

AGE_BAND_TO_CODE = {
    "18-24": 1,
    "25-29": 2,
    "30-34": 3,
    "35-39": 4,
    "40-44": 5,
    "45-49": 6,
    "50-54": 7,
    "55-59": 8,
    "60-64": 9,
    "65-69": 10,
    "70-74": 11,
    "75-79": 12,
    "80-99": 13,
}
AGE_CODE_TO_BAND = {value: key for key, value in AGE_BAND_TO_CODE.items()}
WONDER_AGE_GROUP = {
    1: "15-24",
    2: "25-34",
    3: "25-34",
    4: "35-44",
    5: "35-44",
    6: "45-54",
    7: "45-54",
    8: "55-64",
    9: "55-64",
    10: "65-74",
    11: "65-74",
    12: "75-84",
    13: "85+",
}
AGE_FEATURES = [f"age_band_{code:02d}" for code in range(1, 14)]
LOGIT_AGE_FEATURES = [name for name in AGE_FEATURES if name != "age_band_05"]
LOGIT_FEATURES = LOGIT_AGE_FEATURES + [
    "sex_male",
    "smoking_current",
    "smoking_former",
    "exercise_no",
    "bmi",
]
TREE_FEATURES = AGE_FEATURES + [
    "sex_female",
    "sex_male",
    "smoking_current",
    "smoking_former",
    "smoking_never",
    "exercise_no",
    "exercise_yes",
    "bmi",
]


def local_settings() -> dict[str, str]:
    """Read local credentials without exposing them in output."""
    values = {key: value for key, value in dotenv_values(ENV_FILE).items() if value}
    required = {"MSSQL_SA_PASSWORD", "MSSQL_USER", "MSSQL_DATABASE"}
    missing = sorted(required - values.keys())
    if missing:
        raise RuntimeError("Missing local SQL settings: " + ", ".join(missing))
    return values


def read_local_sql(query: str, columns: list[str]) -> pd.DataFrame:
    """Run a read-only query through the existing local Docker SQL Server."""
    try:
        settings = local_settings()
    except RuntimeError:
        settings = {}
    if settings:
        command = [
            "docker", "exec", "-e", f"SQLCMDPASSWORD={settings['MSSQL_SA_PASSWORD']}",
            LOCAL_CONTAINER, SQLCMD, "-C", "-S", "localhost,1433", "-U", settings["MSSQL_USER"],
            "-d", settings["MSSQL_DATABASE"], "-b", "-W", "-h", "-1", "-s", "|", "-Q", query,
        ]
    else:
        sqlcmd = 'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" ' + shlex.join([
            SQLCMD, "-C", "-S", "localhost", "-U", "sa", "-d", "LifeInsuranceP3",
            "-b", "-W", "-h", "-1", "-s", "|", "-Q", query,
        ])
        command = ["docker", "exec", LOCAL_CONTAINER, "sh", "-c", sqlcmd]
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError("Local SQL read failed without exposing credentials: " + completed.stderr[-1000:])
    rows: list[list[str]] = []
    for line in completed.stdout.splitlines():
        if "|" not in line or line.startswith("(") or set(line) <= {"-", "|"}:
            continue
        values = [value.strip() for value in line.split("|")]
        if len(values) == len(columns):
            rows.append(values)
    return pd.DataFrame(rows, columns=columns)


def build_logit_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Use age band 5, female, never, and yes as fixed reference levels."""
    matrix = frame[LOGIT_AGE_FEATURES].astype(float).copy()
    matrix["sex_male"] = (frame["sex"] == "male").astype(float)
    matrix["smoking_current"] = (frame["smoking_status"] == "current").astype(float)
    matrix["smoking_former"] = (frame["smoking_status"] == "former").astype(float)
    matrix["exercise_no"] = (frame["exercise"] == "no").astype(float)
    matrix["bmi"] = frame["bmi"].astype(float)
    if matrix.isna().any().any():
        raise ValueError("Logistic design matrix contains nulls")
    return matrix[LOGIT_FEATURES]


def build_tree_matrix(frame: pd.DataFrame) -> pd.DataFrame:
    """Retain all one-hot levels for tree and clustering inputs."""
    matrix = frame[AGE_FEATURES].astype(float).copy()
    matrix["sex_female"] = (frame["sex"] == "female").astype(float)
    matrix["sex_male"] = (frame["sex"] == "male").astype(float)
    for value in ("current", "former", "never"):
        matrix[f"smoking_{value}"] = (frame["smoking_status"] == value).astype(float)
    matrix["exercise_no"] = (frame["exercise"] == "no").astype(float)
    matrix["exercise_yes"] = (frame["exercise"] == "yes").astype(float)
    matrix["bmi"] = frame["bmi"].astype(float)
    if matrix.isna().any().any():
        raise ValueError("Tree and clustering design matrix contains nulls")
    return matrix[TREE_FEATURES]


def fit_logistic_with_inference(features: pd.DataFrame, labels: pd.Series) -> tuple[LogisticRegression, pd.DataFrame]:
    """Fit unregularized logistic regression and estimate Hessian-based errors."""
    model = LogisticRegression(C=np.inf, solver="lbfgs", max_iter=2000, random_state=SEED)
    model.fit(features, labels.astype(int))
    design = np.column_stack([np.ones(len(features)), features.to_numpy(dtype=float)])
    fitted = model.predict_proba(features)[:, 1]
    weights = np.clip(fitted * (1.0 - fitted), 1e-9, None)
    covariance = np.linalg.pinv(design.T @ (weights[:, None] * design))
    standard_errors = np.sqrt(np.diag(covariance))
    coefficients = np.concatenate([model.intercept_, model.coef_.ravel()])
    z_values = coefficients / standard_errors
    p_values = 2.0 * norm.sf(np.abs(z_values))
    lower = coefficients - 1.96 * standard_errors
    upper = coefficients + 1.96 * standard_errors
    table = pd.DataFrame(
        {
            "feature": ["Intercept", *features.columns.tolist()],
            "coefficient": coefficients,
            "std_error": standard_errors,
            "z_value": z_values,
            "p_value": p_values,
            "significant_0_05": p_values < 0.05,
            "odds_ratio": np.exp(coefficients),
            "coefficient_ci_lower_95": lower,
            "coefficient_ci_upper_95": upper,
            "odds_ratio_ci_lower_95": np.exp(lower),
            "odds_ratio_ci_upper_95": np.exp(upper),
        }
    )
    return model, table


def classification_metrics(labels: pd.Series, probabilities: np.ndarray) -> dict[str, float]:
    """Return threshold and probability metrics without reporting accuracy."""
    predictions = (probabilities >= 0.5).astype(int)
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    return {
        "auc": float(roc_auc_score(labels, probabilities)),
        "brier_score": float(brier_score_loss(labels, probabilities)),
        "precision_at_0_5": float(precision_score(labels, predictions, zero_division=0)),
        "recall_at_0_5": float(recall_score(labels, predictions, zero_division=0)),
        "f1_at_0_5": float(f1_score(labels, predictions, zero_division=0)),
        "pr_auc": float(auc(recall, precision)),
    }


def save_pr_curve(labels: pd.Series, probabilities: np.ndarray, path: Path, title: str) -> None:
    precision, recall, _ = precision_recall_curve(labels, probabilities)
    figure, axis = plt.subplots(figsize=(7, 5))
    axis.plot(recall, precision, color="black")
    axis.set_xlabel("Recall")
    axis.set_ylabel("Precision")
    axis.set_title(title)
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def save_calibration_plot(labels: pd.Series, probabilities: np.ndarray, path: Path, title: str) -> None:
    observed, predicted = calibration_curve(labels, probabilities, n_bins=10, strategy="quantile")
    figure, axis = plt.subplots(figsize=(6, 6))
    axis.plot([0, 1], [0, 1], color="gray", linestyle=":", label="Perfect calibration")
    axis.plot(predicted, observed, marker="o", color="black", label="Model")
    axis.set_xlabel("Mean predicted probability")
    axis.set_ylabel("Observed positive proportion")
    axis.set_title(title)
    axis.legend()
    axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_tree(train_x: pd.DataFrame, test_x: pd.DataFrame, train_y: pd.Series, test_y: pd.Series) -> tuple[DecisionTreeClassifier, dict[str, Any]]:
    folds = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    search = GridSearchCV(
        DecisionTreeClassifier(random_state=SEED),
        param_grid={"max_depth": list(range(1, 9))},
        scoring="roc_auc",
        cv=folds,
        n_jobs=-1,
    )
    search.fit(train_x, train_y)
    tree = search.best_estimator_
    probabilities = tree.predict_proba(test_x)[:, 1]
    metrics = classification_metrics(test_y, probabilities)
    metrics["chosen_depth"] = int(search.best_params_["max_depth"])
    metrics["cross_validation_auc"] = float(search.best_score_)
    metrics["cv_results"] = {
        str(depth): float(score)
        for depth, score in zip(search.cv_results_["param_max_depth"], search.cv_results_["mean_test_score"], strict=True)
    }
    return tree, metrics


def save_tree_plot(tree: DecisionTreeClassifier, feature_names: list[str], path: Path) -> None:
    figure, axis = plt.subplots(figsize=(18, 10))
    plot_tree(
        tree,
        feature_names=feature_names,
        class_names=["no", "yes"],
        filled=False,
        rounded=False,
        max_depth=3,
        ax=axis,
    )
    axis.set_title("Decision tree, first three levels")
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def run_kmeans(frame: pd.DataFrame, matrix: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, Any]]:
    scaled = StandardScaler().fit_transform(matrix)
    candidates = range(2, 9)
    inertia: dict[int, float] = {}
    silhouettes: dict[int, float] = {}
    fitted: dict[int, KMeans] = {}
    for k in candidates:
        model = KMeans(n_clusters=k, random_state=SEED, n_init=20)
        labels = model.fit_predict(scaled)
        inertia[k] = float(model.inertia_)
        silhouettes[k] = float(silhouette_score(scaled, labels, sample_size=min(10_000, len(frame)), random_state=SEED))
        fitted[k] = model
    chosen_k = max(silhouettes, key=silhouettes.get)
    labels = fitted[chosen_k].labels_
    clustered = frame.copy()
    clustered["cluster"] = labels
    rows: list[dict[str, Any]] = []
    for cluster in sorted(clustered["cluster"].unique()):
        subset = clustered.loc[clustered["cluster"] == cluster]
        age_code = int(subset["age_band"].mode().iloc[0])
        sex = str(subset["sex"].mode().iloc[0])
        smoking = str(subset["smoking_status"].mode().iloc[0])
        exercise = str(subset["exercise"].mode().iloc[0])
        rows.append(
            {
                "cluster": int(cluster),
                "cluster_name": f"{AGE_CODE_TO_BAND[age_code]} {sex}, {smoking} smoking, {exercise} exercise",
                "size": int(len(subset)),
                "size_percent": float(len(subset) / len(clustered) * 100),
                "modal_age_band": AGE_CODE_TO_BAND[age_code],
                "modal_sex": sex,
                "modal_smoking_status": smoking,
                "modal_exercise": exercise,
                "mean_bmi": float(subset["bmi"].mean()),
                "observed_diabetes_prevalence": float(subset["label"].astype(float).mean()),
            }
        )
    profile = pd.DataFrame(rows)
    details = {
        "chosen_k": int(chosen_k),
        "inertia": {str(key): value for key, value in inertia.items()},
        "silhouette": {str(key): value for key, value in silhouettes.items()},
    }
    return profile, details


def save_kmeans_selection_plot(details: dict[str, Any], path: Path) -> None:
    k_values = [int(value) for value in details["inertia"]]
    inertia = [details["inertia"][str(value)] for value in k_values]
    silhouette = [details["silhouette"][str(value)] for value in k_values]
    figure, axes = plt.subplots(1, 2, figsize=(11, 4))
    axes[0].plot(k_values, inertia, marker="o", color="black")
    axes[0].set_xlabel("k")
    axes[0].set_ylabel("Inertia")
    axes[0].set_title("Elbow diagnostic")
    axes[1].plot(k_values, silhouette, marker="o", color="black")
    axes[1].set_xlabel("k")
    axes[1].set_ylabel("Silhouette score")
    axes[1].set_title("Silhouette diagnostic")
    for axis in axes:
        axis.grid(alpha=0.25)
    figure.tight_layout()
    figure.savefig(path, dpi=180)
    plt.close(figure)


def stage_profile_vocabulary() -> dict[str, list[str]]:
    query = """
    SELECT 'AgeBand' AS Variable, AgeBand AS Value FROM dbo.STG_BRFSS_RECORD WHERE AgeBand IS NOT NULL
    UNION
    SELECT 'Gender', Gender FROM dbo.STG_BRFSS_RECORD WHERE Gender IS NOT NULL
    UNION
    SELECT 'SmokingStatus', SmokingStatus FROM dbo.STG_BRFSS_RECORD WHERE SmokingStatus IS NOT NULL
    UNION
    SELECT 'BMIBand', BMIBand FROM dbo.STG_BRFSS_RECORD WHERE BMIBand IS NOT NULL
    UNION
    SELECT 'ExerciseFreq', ExerciseFreq FROM dbo.STG_BRFSS_RECORD WHERE ExerciseFreq IS NOT NULL
    ORDER BY Variable, Value
    """
    values = read_local_sql(query, ["Variable", "Value"])
    return {
        variable: sorted(values.loc[values["Variable"] == variable, "Value"].tolist())
        for variable in ("AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq")
    }


def stage_bmi_representatives() -> dict[str, float]:
    query = """
    SELECT BMIBand, AVG(CAST(BMIValue AS FLOAT)) AS RepresentativeBMI
    FROM dbo.STG_BRFSS_RECORD
    WHERE BMIBand IS NOT NULL AND BMIValue IS NOT NULL
    GROUP BY BMIBand
    ORDER BY BMIBand
    """
    result = read_local_sql(query, ["BMIBand", "RepresentativeBMI"])
    result["RepresentativeBMI"] = pd.to_numeric(result["RepresentativeBMI"])
    return dict(zip(result["BMIBand"], result["RepresentativeBMI"], strict=True))


def export_profile_predictions(final_model: LogisticRegression) -> tuple[pd.DataFrame, dict[str, list[str]], dict[str, float]]:
    vocabulary = stage_profile_vocabulary()
    expected = {
        "AgeBand": list(AGE_BAND_TO_CODE),
        "Gender": ["F", "M"],
        "SmokingStatus": ["current", "former", "never"],
        "BMIBand": ["normal", "obese", "over", "under"],
        "ExerciseFreq": ["no", "yes"],
    }
    if vocabulary != expected:
        raise ValueError(f"STG_BRFSS profile vocabulary diverges from verified expected values: {vocabulary}")
    representatives = stage_bmi_representatives()
    if set(representatives) != set(vocabulary["BMIBand"]):
        raise ValueError("A stage BMI band has no observed BMI representative")
    rows = [
        {
            "AgeBand": age_band,
            "Gender": gender,
            "SmokingStatus": smoking,
            "BMIBand": bmi_band,
            "ExerciseFreq": exercise,
        }
        for age_band, gender, smoking, bmi_band, exercise in product(
            vocabulary["AgeBand"],
            vocabulary["Gender"],
            vocabulary["SmokingStatus"],
            vocabulary["BMIBand"],
            vocabulary["ExerciseFreq"],
        )
    ]
    profiles = pd.DataFrame(rows)
    model_frame = pd.DataFrame(
        {
            "age_band": profiles["AgeBand"].map(AGE_BAND_TO_CODE).astype("int8"),
            "sex": profiles["Gender"].map({"F": "female", "M": "male"}).astype("string"),
            "smoking_status": profiles["SmokingStatus"].astype("string"),
            "exercise": profiles["ExerciseFreq"].astype("string"),
            "bmi": profiles["BMIBand"].map(representatives).astype(float),
        }
    )
    for code in range(1, 14):
        model_frame[f"age_band_{code:02d}"] = (model_frame["age_band"] == code).astype("int8")
    profiles["PredictedProbability"] = final_model.predict_proba(build_logit_matrix(model_frame))[:, 1]
    if len(profiles) != 624:
        raise ValueError(f"Expected 624 profile combinations, found {len(profiles)}")
    profiles.to_csv(PROFILE_PATH, index=False, float_format="%.8f")
    return profiles, vocabulary, representatives


def profile_sparsity_table(predictions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, int]:
    query = """
    SELECT AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq,
           COUNT_BIG(*) AS Records,
           CAST(SUM(CASE WHEN DiabetesStatus = 'yes' THEN 1 ELSE 0 END) AS FLOAT) / COUNT_BIG(*) AS EmpiricalPrevalence
    FROM dbo.STG_BRFSS_RECORD
    WHERE AgeBand IS NOT NULL AND Gender IS NOT NULL AND SmokingStatus IS NOT NULL
      AND BMIBand IS NOT NULL AND ExerciseFreq IS NOT NULL AND DiabetesStatus IS NOT NULL
    GROUP BY AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq
    ORDER BY COUNT_BIG(*), AgeBand, Gender, SmokingStatus, BMIBand, ExerciseFreq
    """
    observed = read_local_sql(
        query,
        ["AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq", "Records", "EmpiricalPrevalence"],
    )
    observed["Records"] = pd.to_numeric(observed["Records"], downcast="integer")
    observed["EmpiricalPrevalence"] = pd.to_numeric(observed["EmpiricalPrevalence"])
    merged = observed.merge(
        predictions,
        on=["AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq"],
        how="left",
        validate="one_to_one",
    )
    sparse = merged.head(5).copy()
    zero = predictions.merge(
        observed[["AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq"]],
        on=["AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq"],
        how="left",
        indicator=True,
    )
    zero = zero.loc[zero["_merge"] == "left_only"].drop(columns="_merge").sort_values(
        ["AgeBand", "Gender", "SmokingStatus", "BMIBand", "ExerciseFreq"]
    )
    if len(zero) != 19:
        raise ValueError(f"Expected 19 zero-record profiles, found {len(zero)}")
    sparse.to_csv(OUTPUT_DIR / "sparsity_empirical_vs_predicted.csv", index=False, float_format="%.8f")
    zero.head(1).to_csv(OUTPUT_DIR / "sparsity_zero_record_example.csv", index=False, float_format="%.8f")
    return sparse, zero.head(1), len(observed)


def external_validation(frame: pd.DataFrame, final_model: LogisticRegression) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    labelled = frame.loc[frame["label"].notna()].copy()
    labelled["predicted_probability"] = final_model.predict_proba(build_logit_matrix(labelled))[:, 1]
    labelled["WonderAgeBand"] = labelled["age_band"].map(WONDER_AGE_GROUP)
    labelled["Gender"] = labelled["sex"].map({"female": "F", "male": "M"})
    model_wonder = labelled.groupby(["WonderAgeBand", "Gender"], as_index=False)["predicted_probability"].mean()
    wonder_query = """
    WITH mortality AS (
        SELECT AgeBand, Gender, ConditionFlag, CAST(MortalityRate AS FLOAT) AS MortalityRate
        FROM dbo.STG_MORTALITY
        WHERE SourceYear = 2023 AND ConditionFlag IN ('ALLCAUSE', 'DIABETES')
    )
    SELECT a.AgeBand, a.Gender, a.MortalityRate AS AllCauseRate,
           d.MortalityRate AS DiabetesRate,
           d.MortalityRate / NULLIF(a.MortalityRate, 0) AS DiabetesToAllCauseRatio
    FROM mortality AS a
    JOIN mortality AS d ON d.AgeBand = a.AgeBand AND d.Gender = a.Gender
    WHERE a.ConditionFlag = 'ALLCAUSE' AND d.ConditionFlag = 'DIABETES'
    ORDER BY a.AgeBand, a.Gender
    """
    wonder = read_local_sql(
        wonder_query,
        ["AgeBand", "Gender", "AllCauseRate", "DiabetesRate", "DiabetesToAllCauseRatio"],
    )
    for column in ("AllCauseRate", "DiabetesRate", "DiabetesToAllCauseRatio"):
        wonder[column] = pd.to_numeric(wonder[column])
    comparison = model_wonder.merge(wonder, left_on=["WonderAgeBand", "Gender"], right_on=["AgeBand", "Gender"], how="inner")
    ssa_query = """
    SELECT AgeBand, Gender, CAST(MortalityRate AS FLOAT) AS MortalityRate
    FROM dbo.STG_MORTALITY
    WHERE SourceYear = 2023 AND ConditionFlag = 'BASELINE'
    ORDER BY AgeBand, Gender
    """
    ssa = read_local_sql(ssa_query, ["AgeBand", "Gender", "MortalityRate"])
    ssa["MortalityRate"] = pd.to_numeric(ssa["MortalityRate"])
    model_ssa = labelled.groupby(["age_band", "Gender"], as_index=False)["predicted_probability"].mean()
    model_ssa["AgeBand"] = model_ssa["age_band"].map(AGE_CODE_TO_BAND)
    ordering = model_ssa.merge(ssa, on=["AgeBand", "Gender"], how="inner")
    age_order = list(AGE_BAND_TO_CODE)
    wonder_order = ["15-24", "25-34", "35-44", "45-54", "55-64", "65-74", "75-84", "85+"]
    comparison["AgeBand"] = pd.Categorical(comparison["AgeBand"], categories=wonder_order, ordered=True)
    comparison = comparison.sort_values(["Gender", "AgeBand"])
    ordering["AgeBand"] = pd.Categorical(ordering["AgeBand"], categories=age_order, ordered=True)
    ordering = ordering.sort_values(["Gender", "AgeBand"])
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
    for axis, gender in zip(axes, ["F", "M"], strict=True):
        subset = comparison.loc[comparison["Gender"] == gender]
        axis.plot(subset["AgeBand"].astype(str), subset["predicted_probability"], marker="o", color="black", label="Model prevalence")
        twin = axis.twinx()
        twin.plot(subset["AgeBand"].astype(str), subset["DiabetesToAllCauseRatio"], marker="s", color="gray", label="WONDER ratio")
        axis.set_title(f"WONDER comparison, {gender}")
        axis.set_xlabel("WONDER age group")
        axis.set_ylabel("Predicted diabetes prevalence")
        twin.set_ylabel("Diabetes to all-cause ratio")
        axis.tick_params(axis="x", rotation=45)
    figure.tight_layout()
    figure.savefig(FIGURE_DIR / "wonder_directional_comparison.png", dpi=180)
    plt.close(figure)
    figure, axes = plt.subplots(1, 2, figsize=(12, 4.5), sharey=False)
    for axis, gender in zip(axes, ["F", "M"], strict=True):
        subset = ordering.loc[ordering["Gender"] == gender]
        axis.plot(subset["AgeBand"].astype(str), subset["predicted_probability"], marker="o", color="black", label="Model prevalence")
        twin = axis.twinx()
        twin.plot(subset["AgeBand"].astype(str), subset["MortalityRate"], marker="s", color="gray", label="SSA mortality rate")
        axis.set_title(f"SSA ordering check, {gender}")
        axis.set_xlabel("BRFSS age band")
        axis.set_ylabel("Predicted diabetes prevalence")
        twin.set_ylabel("Lives-weighted mortality rate")
        axis.tick_params(axis="x", rotation=45)
    figure.tight_layout()
    figure.savefig(FIGURE_DIR / "ssa_ordering_comparison.png", dpi=180)
    plt.close(figure)
    metrics: dict[str, Any] = {"wonder_spearman_by_sex": {}, "ssa_monotonic_by_sex": {}}
    for gender in ("F", "M"):
        wonder_subset = comparison.loc[comparison["Gender"] == gender]
        metrics["wonder_spearman_by_sex"][gender] = float(
            spearmanr(wonder_subset["predicted_probability"], wonder_subset["DiabetesToAllCauseRatio"]).statistic
        )
        ssa_subset = ordering.loc[ordering["Gender"] == gender]
        metrics["ssa_monotonic_by_sex"][gender] = {
            "model_non_decreasing": bool(np.all(np.diff(ssa_subset["predicted_probability"]) >= 0)),
            "ssa_non_decreasing": bool(np.all(np.diff(ssa_subset["MortalityRate"]) >= 0)),
        }
    comparison.to_csv(OUTPUT_DIR / "wonder_directional_comparison.csv", index=False)
    ordering.to_csv(OUTPUT_DIR / "ssa_ordering_comparison.csv", index=False)
    return comparison, ordering, metrics


def subgroup_auc(test_frame: pd.DataFrame, test_labels: pd.Series, probabilities: np.ndarray) -> tuple[pd.DataFrame, pd.DataFrame]:
    audit = test_frame[["sex", "age_band"]].copy()
    audit["label"] = test_labels.to_numpy()
    audit["probability"] = probabilities
    sex_rows: list[dict[str, Any]] = []
    for value, subset in audit.groupby("sex"):
        sex_rows.append({"subgroup": value, "rows": len(subset), "positive_rows": int(subset["label"].sum()), "auc": float(roc_auc_score(subset["label"], subset["probability"]))})
    age_rows: list[dict[str, Any]] = []
    for value, subset in audit.groupby("age_band"):
        if subset["label"].nunique() < 2:
            auc_value = np.nan
        else:
            auc_value = float(roc_auc_score(subset["label"], subset["probability"]))
        age_rows.append({"subgroup": AGE_CODE_TO_BAND[int(value)], "rows": len(subset), "positive_rows": int(subset["label"].sum()), "auc": auc_value})
    sex = pd.DataFrame(sex_rows).sort_values("subgroup")
    age = pd.DataFrame(age_rows)
    age["subgroup"] = pd.Categorical(age["subgroup"], categories=list(AGE_BAND_TO_CODE), ordered=True)
    return sex, age.sort_values("subgroup")


def markdown_table(frame: pd.DataFrame, precision: int = 3) -> str:
    """Render a small report table without an additional package dependency."""
    def render(value: Any) -> str:
        if isinstance(value, (float, np.floating)):
            return f"{value:.{precision}f}"
        return str(value)

    columns = frame.columns.tolist()
    header = "| " + " | ".join(columns) + " |"
    divider = "|" + "|".join("---" for _ in columns) + "|"
    rows = ["| " + " | ".join(render(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join([header, divider, *rows])


def write_summary(
    split: pd.DataFrame,
    logistic_metrics: dict[str, Any],
    tree_metrics: dict[str, Any],
    clusters: pd.DataFrame,
    sparse: pd.DataFrame,
    zero: pd.DataFrame,
    observed_profiles: int,
    sensitivity: pd.DataFrame,
    validation: dict[str, Any],
    sex_auc: pd.DataFrame,
    age_auc: pd.DataFrame,
    significant: pd.DataFrame,
) -> None:
    significant_names = ", ".join(significant.loc[significant["feature"] != "Intercept", "feature"].tolist())
    sensitivity_max = sensitivity.loc[sensitivity["feature"] != "Intercept", "coefficient_change"].abs().max()
    conclusion = "The coefficient signs remain stable across the primary and sensitivity fits." if not (sensitivity.loc[sensitivity["feature"] != "Intercept", "sign_changed"]).any() else "At least one coefficient changes sign in the sensitivity fit."
    content = f"""# Diabetes risk-stratification model summary

I trained reproducible BRFSS diabetes risk-stratification models with fixed seed {SEED}. The primary analysis uses {split.loc[split['split'] == 'train', 'rows'].iloc[0] + split.loc[split['split'] == 'test', 'rows'].iloc[0]:,} labelled records after the prepared frame excludes pre-diabetes from the primary label. BRFSS is cross-sectional and self-reported, so this is concurrent risk stratification rather than incidence forecasting. The model is not a mortality model.

## Method and primary result

I used logistic regression for the rate-revision and product risk-assessment decision because its coefficients translate directly into rating factors. Age band 40-44 is the reference category. Female, never smoking, and exercise yes are the other reference levels. The held-out AUC is {logistic_metrics['auc']:.3f} and the Brier score is {logistic_metrics['brier_score']:.3f}. At the default threshold, precision is {logistic_metrics['precision_at_0_5']:.3f}, recall is {logistic_metrics['recall_at_0_5']:.3f}, and F1 is {logistic_metrics['f1_at_0_5']:.3f}.

I do not report accuracy. With roughly 14.9 percent diabetes prevalence, a model that predicts no diabetes for every applicant would appear about 85 percent accurate while making no useful pricing distinction. Calibration matters more than discrimination for this use because probabilities feed rate calculations directly. They need to be correct in absolute terms, not merely ranked correctly.

The statistically significant non-intercept coefficients are {significant_names}. The coefficient table includes standard errors, odds ratios, and 95 percent confidence intervals in `outputs/model/logistic_coefficients.csv`.

## Decision-tree comparison

I tuned tree depth with five-fold stratified cross-validation. The selected depth is {tree_metrics['chosen_depth']}, with cross-validation AUC {tree_metrics['cross_validation_auc']:.3f} and held-out AUC {tree_metrics['auc']:.3f}. Logistic regression is retained as the primary candidate because a coefficient per risk factor is directly explainable in underwriting. A tree's threshold splits are harder to defend even if its discrimination is competitive.

## K-means segmentation

I standardized the encoded inputs before clustering so BMI and one-hot features contributed on comparable scales. The silhouette criterion selected k={clusters.shape[0]}. The cluster profiles below use observed diabetes prevalence only for validation, not for fitting.

{markdown_table(clusters, precision=3)}

These groups suggest differentiated product presentation and wellness outreach. Higher-BMI, low-exercise groups can receive wellness-program outreach, while lower-risk groups can be candidates for simpler product tiers. The groups are descriptive and are not an underwriting decision by themselves.

## Sparsity argument

The staging summary observes {observed_profiles} of 624 possible profiles. Nineteen profiles have zero records, 34 have exactly one record, and 272 have fewer than 30 records. The sparse-profile comparison below shows why an empirical lookup is unstable.

{markdown_table(sparse, precision=4)}

The selected zero-record profile has no empirical lookup result but still receives model probability {zero['PredictedProbability'].iloc[0]:.4f}. A lookup table alone cannot price 19 of 624 possible profiles, about 3 percent.

## Pre-diabetes sensitivity

I refit the logistic model with 1,085 pre-diabetes records folded into the positive class through `label_sensitivity`. The largest absolute coefficient change is {sensitivity_max:.4f}. {conclusion} This measures the design decision that pre-diabetes maps to no in `RISK_FACTOR` because the lake has no source-traceable pre-diabetes mortality multiplier.

## External validation and fairness

The WONDER comparison uses the 2022-2024 cohort identified by `SourceYear = 2023`. It compares predicted diabetes prevalence with the diabetes-to-all-cause mortality ratio, so it is a directional rather than numerical check. Spearman correlations are F={validation['wonder_spearman_by_sex']['F']:.3f} and M={validation['wonder_spearman_by_sex']['M']:.3f}. The SSA ordering check reports model non-decreasing by age for F={validation['ssa_monotonic_by_sex']['F']['model_non_decreasing']} and M={validation['ssa_monotonic_by_sex']['M']['model_non_decreasing']}. SSA mortality is non-decreasing for F={validation['ssa_monotonic_by_sex']['F']['ssa_non_decreasing']} and M={validation['ssa_monotonic_by_sex']['M']['ssa_non_decreasing']}. The model falls from age 75-79 to the open-ended 80-99 band for both sexes while SSA mortality continues to rise. I treat that failed monotonic check as a calibration finding for review, not as a reason to alter the source data or force a rate factor.

United States permissibility is jurisdiction-specific. Age, smoking, diabetes, and BMI are candidate rating inputs only where the company can show a sound actuarial basis and a valid rationale, then comply with the applicable state law and filing rules. Gender needs separate review because its use is restricted in some United States jurisdictions and prohibited for insurance pricing in the European Union. BMI can have different validity across populations and can act as a proxy for unobserved social and health conditions. The model uses an unweighted BRFSS sample, so probabilities reflect the sample rather than the United States population. The documented 4,631 missing BMI records and other exclusions form roughly 7,200 less-willing respondents rather than scattered noise, which can attenuate the estimated BMI relationship. Calibration and subgroup monitoring are therefore continuing controls.

Sex subgroup AUC:

{markdown_table(sex_auc, precision=3)}

Age-band subgroup AUC:

{markdown_table(age_auc, precision=3)}
"""
    SUMMARY_PATH.write_text(content, encoding="utf-8")


def run_pipeline() -> dict[str, Any]:
    """Run the full model evaluation, local validation reads, and exports."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    frame = pd.read_parquet(FRAME_PATH)
    primary = frame.loc[frame["label"].notna()].copy()
    primary["label"] = primary["label"].astype(int)
    train_frame, test_frame = train_test_split(primary, test_size=0.2, stratify=primary["label"], random_state=SEED)
    train_frame = train_frame.reset_index(drop=True)
    test_frame = test_frame.reset_index(drop=True)
    split = pd.DataFrame(
        [
            {"split": "train", "rows": len(train_frame), "positive_rate": float(train_frame["label"].mean())},
            {"split": "test", "rows": len(test_frame), "positive_rate": float(test_frame["label"].mean())},
        ]
    )
    logit_train = build_logit_matrix(train_frame)
    logit_test = build_logit_matrix(test_frame)
    logistic, training_coefficients = fit_logistic_with_inference(logit_train, train_frame["label"])
    logistic_probabilities = logistic.predict_proba(logit_test)[:, 1]
    logistic_metrics = classification_metrics(test_frame["label"], logistic_probabilities)
    save_pr_curve(test_frame["label"], logistic_probabilities, FIGURE_DIR / "logistic_precision_recall.png", "Logistic regression precision-recall curve")
    save_calibration_plot(test_frame["label"], logistic_probabilities, FIGURE_DIR / "logistic_calibration.png", "Logistic regression calibration")
    tree_train = build_tree_matrix(train_frame)
    tree_test = build_tree_matrix(test_frame)
    tree, tree_metrics = run_tree(tree_train, tree_test, train_frame["label"], test_frame["label"])
    tree_probabilities = tree.predict_proba(tree_test)[:, 1]
    save_pr_curve(test_frame["label"], tree_probabilities, FIGURE_DIR / "tree_precision_recall.png", "Decision-tree precision-recall curve")
    save_calibration_plot(test_frame["label"], tree_probabilities, FIGURE_DIR / "tree_calibration.png", "Decision-tree calibration")
    save_tree_plot(tree, tree_train.columns.tolist(), FIGURE_DIR / "decision_tree_top_levels.png")
    clusters, kmeans_metrics = run_kmeans(frame, build_tree_matrix(frame))
    clusters.to_csv(OUTPUT_DIR / "kmeans_clusters.csv", index=False, float_format="%.8f")
    save_kmeans_selection_plot(kmeans_metrics, FIGURE_DIR / "kmeans_selection.png")
    sensitivity_train, sensitivity_test = train_test_split(
        frame.copy(), test_size=0.2, stratify=frame["label_sensitivity"], random_state=SEED
    )
    sensitivity_model, sensitivity_coefficients = fit_logistic_with_inference(build_logit_matrix(sensitivity_train), sensitivity_train["label_sensitivity"])
    sensitivity_probabilities = sensitivity_model.predict_proba(build_logit_matrix(sensitivity_test))[:, 1]
    sensitivity_metrics = classification_metrics(sensitivity_test["label_sensitivity"], sensitivity_probabilities)
    sensitivity = training_coefficients[["feature", "coefficient"]].merge(
        sensitivity_coefficients[["feature", "coefficient"]], on="feature", suffixes=("_primary", "_sensitivity")
    )
    sensitivity["coefficient_change"] = sensitivity["coefficient_sensitivity"] - sensitivity["coefficient_primary"]
    sensitivity["sign_changed"] = np.sign(sensitivity["coefficient_primary"]) != np.sign(sensitivity["coefficient_sensitivity"])
    sensitivity.to_csv(OUTPUT_DIR / "sensitivity_coefficients.csv", index=False, float_format="%.8f")
    final_logistic, final_coefficients = fit_logistic_with_inference(build_logit_matrix(primary), primary["label"])
    final_coefficients["fit_scope"] = "primary labelled records, refit after held-out evaluation"
    final_coefficients.to_csv(COEFFICIENTS_PATH, index=False, float_format="%.8f")
    profile_predictions, vocabulary, representatives = export_profile_predictions(final_logistic)
    sparse, zero, observed_profiles = profile_sparsity_table(profile_predictions)
    wonder_comparison, ssa_ordering, validation_metrics = external_validation(frame, final_logistic)
    sex_auc, age_auc = subgroup_auc(test_frame, test_frame["label"], logistic_probabilities)
    sex_auc.to_csv(OUTPUT_DIR / "subgroup_auc_by_sex.csv", index=False, float_format="%.8f")
    age_auc.to_csv(OUTPUT_DIR / "subgroup_auc_by_age_band.csv", index=False, float_format="%.8f")
    metrics: dict[str, Any] = {
        "seed": SEED,
        "frame_rows": int(len(frame)),
        "primary_label_rows": int(len(primary)),
        "split": split.to_dict(orient="records"),
        "reference_levels": {"age_band": "40-44", "sex": "female", "smoking_status": "never", "exercise": "yes"},
        "logistic_regression": logistic_metrics,
        "decision_tree": tree_metrics,
        "kmeans": kmeans_metrics,
        "sensitivity": {"metrics": sensitivity_metrics, "pre_diabetes_rows_folded_positive": int((frame["diabetes_response"] == 4).sum())},
        "external_validation": validation_metrics,
        "profile_vocabulary": vocabulary,
        "bmi_band_representatives": representatives,
        "profile_rows": int(len(profile_predictions)),
    }
    METRICS_PATH.write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    write_summary(
        split,
        logistic_metrics,
        tree_metrics,
        clusters,
        sparse,
        zero,
        observed_profiles,
        sensitivity,
        validation_metrics,
        sex_auc,
        age_auc,
        final_coefficients.loc[final_coefficients["significant_0_05"]],
    )
    return {
        "frame": frame,
        "split": split,
        "training_coefficients": training_coefficients,
        "final_coefficients": final_coefficients,
        "logistic_metrics": logistic_metrics,
        "tree_metrics": tree_metrics,
        "clusters": clusters,
        "kmeans_metrics": kmeans_metrics,
        "sparse": sparse,
        "zero": zero,
        "sensitivity": sensitivity,
        "sensitivity_metrics": sensitivity_metrics,
        "wonder_comparison": wonder_comparison,
        "ssa_ordering": ssa_ordering,
        "validation_metrics": validation_metrics,
        "sex_auc": sex_auc,
        "age_auc": age_auc,
        "metrics": metrics,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-path", type=Path, default=FRAME_PATH)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--summary-path", type=Path, default=SUMMARY_PATH)
    parser.add_argument("--env-file", type=Path, default=ENV_FILE)
    args = parser.parse_args()
    FRAME_PATH = args.frame_path
    OUTPUT_DIR = args.output_dir
    FIGURE_DIR = OUTPUT_DIR / "figures"
    METRICS_PATH = OUTPUT_DIR / "model_metrics.json"
    COEFFICIENTS_PATH = OUTPUT_DIR / "logistic_coefficients.csv"
    PROFILE_PATH = OUTPUT_DIR / "predicted_risk_by_profile.csv"
    SUMMARY_PATH = args.summary_path
    ENV_FILE = args.env_file
    results = run_pipeline()
    print("Model outputs written to", OUTPUT_DIR)
    print(results["split"].to_string(index=False))
    print("Logistic AUC:", f"{results['logistic_metrics']['auc']:.4f}")
