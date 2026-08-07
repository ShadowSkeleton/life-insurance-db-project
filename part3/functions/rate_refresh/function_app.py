# Jingrui Feng (jf4446) - database systems project part 3 - monthly rate refresh function
"""Monthly Azure Functions entry point for the existing rate-refresh core.

The deployment package is produced by build_package.py, which copies the one
authoritative python/etl/run_rate_refresh.py source into the function root as
rate_refresh_core.py. No pricing logic is implemented here.
"""

from __future__ import annotations

import logging
import os
import tempfile
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import azure.functions as func
from azure.storage.blob import BlobServiceClient

from rate_refresh_core import run


app = func.FunctionApp()
# Monthly at 02:00 UTC: WONDER, SSA, and BRFSS publish annually, so a daily
# refresh would usually recompute unchanged inputs and needlessly wake Azure SQL.
SCHEDULE = "0 0 2 1 * *"
MODEL_BLOB_PATH = "part3-analytics/model/predicted_risk_by_profile.csv"


def required_setting(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Function App setting {name} is required.")
    return value


def download_model(destination: Path) -> None:
    container = os.environ.get("AZURE_STORAGE_CONTAINER", "datalake")
    blob_path = os.environ.get("MODEL_BLOB_PATH", MODEL_BLOB_PATH)
    client = BlobServiceClient.from_connection_string(required_setting("AZURE_STORAGE_CONNECTION_STRING"))
    with destination.open("wb") as handle:
        handle.write(client.get_blob_client(container=container, blob=blob_path).download_blob().readall())


@app.timer_trigger(schedule=SCHEDULE, arg_name="timer", use_monitor=True)
def publish_rate_book(timer: func.TimerRequest) -> None:
    if timer.past_due:
        logging.warning("The scheduled refresh is running after its scheduled time.")
    with tempfile.TemporaryDirectory(prefix="p3-model-") as directory:
        profile_path = Path(directory) / "predicted_risk_by_profile.csv"
        download_model(profile_path)
        result = run(
            datetime.now(timezone.utc).date(),
            wonder_cohort_source_year=int(os.environ.get("WONDER_COHORT_SOURCE_YEAR", "2023")),
            loading_factor=Decimal(os.environ.get("LOADING_FACTOR", "1.50")),
            undiagnosed_fraction=Decimal(os.environ.get("UNDIAGNOSED_FRACTION", "0.20")),
            azure=True,
            profile_path=profile_path,
        )
    logging.info(
        "Published rate version %s from refresh run %s using WONDER cohort %s.",
        result["rate_version_id"], result["run_id"], result["wonder_cohort_source_year"],
    )
