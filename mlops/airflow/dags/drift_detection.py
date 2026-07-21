"""Drift Detection DAG — runs daily, compares current feature distributions
to training baseline, and alerts if KL divergence threshold exceeded.
"""

from datetime import datetime, timedelta

import numpy as np
from airflow import DAG
from airflow.operators.python import PythonOperator
from joblib import load
from scipy.stats import entropy

default_args = {
    "owner": "elyssa-mlops",
    "depends_on_past": False,
    "start_date": datetime(2026, 7, 21),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

KLD_THRESHOLD = 0.1
BASELINE_PATH = "/data/marts/processed/feature_statistics.joblib"
CURRENT_DATA_PATH = "/data/marts/processed/"


def _compute_current_statistics() -> dict:
    """Compute feature distributions from current Gold data."""
    import pandas as pd

    tab_cols = [
        "start_year", "runtime_minutes", "average_rating", "num_votes",
        "num_persons", "actor_count", "director_count",
    ]
    df = pd.read_parquet(CURRENT_DATA_PATH + "dim_title.parquet", columns=tab_cols)
    stats: dict = {"columns": tab_cols, "probs": {}}
    for col in tab_cols:
        hist, _ = np.histogram(df[col].dropna(), bins=20, density=True)
        stats["probs"][col] = hist + 1e-10
        stats["probs"][col] /= stats["probs"][col].sum()
    return stats


def _detect_drift() -> None:
    """Compare baseline vs. current feature distributions."""
    try:
        baseline = load(BASELINE_PATH)
    except FileNotFoundError:
        raise FileNotFoundError(f"Baseline not found at {BASELINE_PATH} — run training first")

    current = _compute_current_statistics()
    drifted_features = []

    for feature in baseline["columns"]:
        if feature not in current["probs"]:
            continue
        kl_div = entropy(baseline["probs"][feature], current["probs"][feature])
        if kl_div > KLD_THRESHOLD:
            drifted_features.append((feature, float(kl_div)))

    if drifted_features:
        msg = "Drift detected:\n" + "\n".join(
            f"  {feat}: KL={kl:.4f}" for feat, kl in drifted_features
        )
        raise ValueError(msg)

    print(f"Drift check passed — {len(baseline['columns'])} features within threshold")


with DAG(
    "elyssa_drift_detection",
    default_args=default_args,
    schedule_interval="0 8 * * *",  # Daily at 8 AM UTC
    catchup=False,
    tags=["mlops", "monitoring"],
    description="Daily drift detection: compare feature distributions to training baseline",
) as dag:

    detect_drift = PythonOperator(
        task_id="detect_feature_drift",
        python_callable=_detect_drift,
    )

    detect_drift
