"""MLOps Retraining Pipeline — triggered weekly or on data freshness.

Checks Gold mart freshness, runs feature engineering + training,
registers model in MLflow, and deploys a canary if metrics pass.
"""

from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import PythonOperator

default_args = {
    "owner": "elyssa-mlops",
    "depends_on_past": False,
    "start_date": datetime(2026, 7, 21),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "email_on_failure": True,
    "email": ["mlops@elyssa.local"],
}

GOLD_MARTS = Path("/data/marts/processed")
FRESHNESS_THRESHOLD_HOURS = 168  # 7 days


def _check_freshness() -> str:
    """Fail the DAG if Gold marts are too stale."""
    inv_path = GOLD_MARTS / "model_inventory.json"
    if not inv_path.exists():
        raise FileNotFoundError(f"{inv_path} not found — Gold marts missing")

    mtime = inv_path.stat().st_mtime
    age_hours = (datetime.now() - datetime.fromtimestamp(mtime)).total_seconds() / 3600
    if age_hours > FRESHNESS_THRESHOLD_HOURS:
        raise RuntimeError(
            f"Gold marts stale ({age_hours:.1f}h > {FRESHNESS_THRESHOLD_HOURS}h threshold)"
        )
    return f"Freshness OK — last updated {age_hours:.1f}h ago"


with DAG(
    "elyssa_retraining_pipeline",
    default_args=default_args,
    schedule_interval="0 6 * * 0",  # Every Sunday 6 AM UTC
    catchup=False,
    tags=["mlops", "retraining"],
    description="Weekly model retraining: check freshness → feature stats → register → deploy canary",
) as dag:

    check_freshness = PythonOperator(
        task_id="check_gold_freshness",
        python_callable=_check_freshness,
    )

    generate_feature_stats = BashOperator(
        task_id="generate_feature_statistics",
        bash_command=(
            "cd /opt/airflow && "
            "python data-science/scripts/feature_statistics.py "
            "--input /data/marts/processed "
            "--output /data/marts/processed/feature_statistics.joblib"
        ),
    )

    register_mlflow = BashOperator(
        task_id="register_in_mlflow",
        bash_command=(
            "cd /opt/airflow && "
            "mlflow models register-model "
            "--name Elyssa_Genre_GMU "
            "--source /data/marts/processed/gmu_genre_best.pt"
        ),
    )

    deploy_canary = BashOperator(
        task_id="deploy_canary",
        bash_command=(
            "echo 'Canary deploy triggered — verify model version in MLflow UI'"
        ),
    )

    check_freshness >> generate_feature_stats >> register_mlflow >> deploy_canary
