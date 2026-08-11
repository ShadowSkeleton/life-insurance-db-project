"""Blob-driven BRFSS change detection and deterministic Part 4 retraining."""
from __future__ import annotations

import hashlib
import json
import shlex
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from azure.storage.blob import BlobServiceClient
from dotenv import dotenv_values

PART4_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = PART4_ROOT / "python"
DEFAULT_SOURCE_PATH = "part3-analytics/curated/brfss_2024_life_risk_sample_50000.csv"
DEFAULT_DESTINATION_PREFIX = "part4-analytics/model"
DEFAULT_CONTAINER = "datalake"
LOCAL_CONTAINER = "dbsys-p3-mssql"
SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"

@dataclass
class RetrainingResult:
    retrained: bool
    source_path: str
    observed_hash: str
    byte_size: int
    profile_blob_path: str
    metrics_blob_path: str
    baseline_blob_path: str
    gate: dict[str, Any]
    metrics: dict[str, Any]
    local_profile_path: str


def _settings(env_file: Path) -> dict[str, str]:
    values = {key: value for key, value in dotenv_values(env_file).items() if value}
    if not values.get("AZURE_STORAGE_CONNECTION_STRING"):
        raise RuntimeError(f"AZURE_STORAGE_CONNECTION_STRING is missing from {env_file}")
    return values


def _docker_query(query: str) -> list[list[str]]:
    command = 'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" ' + shlex.join([
        SQLCMD, "-C", "-S", "localhost", "-U", "sa", "-d", "LifeInsuranceP3",
        "-b", "-W", "-s", "|", "-h", "-1", "-Q", query,
    ])
    result = subprocess.run(["docker", "exec", LOCAL_CONTAINER, "sh", "-c", command], check=True, text=True, capture_output=True)
    return [line.split("|") for line in result.stdout.splitlines() if line.strip() and not line.lstrip().startswith("(")]


def _latest_hash(source_path: str) -> str | None:
    escaped = source_path.replace("'", "''")
    rows = _docker_query(
        "SELECT TOP (1) ContentHash FROM dbo.DATA_SOURCE_STATE "
        f"WHERE SourcePath = '{escaped}' ORDER BY SourceStateID DESC;"
    )
    return rows[0][0].strip() if rows else None


def _metrics_gate(new: dict[str, Any], baseline: dict[str, Any] | None) -> dict[str, Any]:
    new_auc = float(new["logistic_regression"]["auc"])
    new_wonder = new["external_validation"]["wonder_spearman_by_sex"]
    new_violations = sum(not values["model_non_decreasing"] for values in new["external_validation"]["ssa_monotonic_by_sex"].values())
    direction_pass = all(float(value) > 0 for value in new_wonder.values())
    if baseline is None:
        return {"passed": direction_pass, "baseline_recorded": True, "auc": {"baseline": None, "new": new_auc, "minimum": None, "passed": True}, "wonder": {"values": new_wonder, "passed": direction_pass}, "ssa_violations": {"baseline": None, "new": new_violations, "passed": True}}
    baseline_auc = float(baseline["logistic_regression"]["auc"])
    baseline_violations = sum(not values["model_non_decreasing"] for values in baseline["external_validation"]["ssa_monotonic_by_sex"].values())
    auc_pass = new_auc >= baseline_auc - 0.02
    ssa_pass = new_violations <= baseline_violations
    return {"passed": auc_pass and direction_pass and ssa_pass, "baseline_recorded": False, "auc": {"baseline": baseline_auc, "new": new_auc, "minimum": baseline_auc - 0.02, "passed": auc_pass}, "wonder": {"values": new_wonder, "passed": direction_pass}, "ssa_violations": {"baseline": baseline_violations, "new": new_violations, "passed": ssa_pass}}


def run_retraining(*, env_file: Path, source_path: str = DEFAULT_SOURCE_PATH, destination_prefix: str = DEFAULT_DESTINATION_PREFIX, python_executable: str = sys.executable) -> RetrainingResult:
    settings = _settings(env_file)
    container = settings.get("AZURE_STORAGE_CONTAINER", DEFAULT_CONTAINER)
    service = BlobServiceClient.from_connection_string(settings["AZURE_STORAGE_CONNECTION_STRING"])
    blob = service.get_blob_client(container=container, blob=source_path)
    data = blob.download_blob().readall()
    observed_hash = hashlib.sha256(data).hexdigest()
    byte_size = len(data)
    profile_blob_path = f"{destination_prefix.rstrip('/')}/predicted_risk_by_profile.csv"
    metrics_blob_path = f"{destination_prefix.rstrip('/')}/model_metrics.json"
    baseline_blob_path = f"{destination_prefix.rstrip('/')}/baseline_metrics.json"
    local_profile = PART4_ROOT / "outputs" / "model" / "predicted_risk_by_profile.csv"
    if _latest_hash(source_path) == observed_hash:
        return RetrainingResult(False, source_path, observed_hash, byte_size, profile_blob_path, metrics_blob_path, baseline_blob_path, {"passed": True, "reason": "hash_match"}, {}, str(local_profile))
    local_source = PART4_ROOT / "data" / "curated" / Path(source_path).name
    local_source.parent.mkdir(parents=True, exist_ok=True)
    local_source.write_bytes(data)
    frame = PART4_ROOT / "data" / "processed" / "brfss_training.parquet"
    output_dir = PART4_ROOT / "outputs" / "model"
    subprocess.run([python_executable, str(PYTHON_DIR / "build_training_frame.py"), "--source-file", str(local_source), "--output-file", str(frame)], check=True)
    subprocess.run([python_executable, str(PYTHON_DIR / "train_diabetes_risk_model.py"), "--frame-path", str(frame), "--output-dir", str(output_dir), "--summary-path", str(PART4_ROOT / "docs" / "ml_model_summary.md"), "--env-file", str(env_file)], check=True)
    metrics = json.loads((output_dir / "model_metrics.json").read_text())
    baseline_client = service.get_blob_client(container=container, blob=baseline_blob_path)
    try:
        baseline = json.loads(baseline_client.download_blob().readall())
    except Exception:
        baseline = None
    gate = _metrics_gate(metrics, baseline)
    if not gate["passed"]:
        return RetrainingResult(True, source_path, observed_hash, byte_size, profile_blob_path, metrics_blob_path, baseline_blob_path, gate, metrics, str(local_profile))
    for path, payload in ((profile_blob_path, local_profile.read_bytes()), (metrics_blob_path, json.dumps(metrics, indent=2).encode()), (baseline_blob_path, json.dumps(metrics, indent=2).encode())):
        service.get_blob_client(container=container, blob=path).upload_blob(payload, overwrite=True)
    return RetrainingResult(True, source_path, observed_hash, byte_size, profile_blob_path, metrics_blob_path, baseline_blob_path, gate, metrics, str(local_profile))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--source-path", default=DEFAULT_SOURCE_PATH)
    parser.add_argument("--destination-prefix", default=DEFAULT_DESTINATION_PREFIX)
    args = parser.parse_args()
    print(json.dumps(asdict(run_retraining(env_file=args.env_file, source_path=args.source_path, destination_prefix=args.destination_prefix)), indent=2))
