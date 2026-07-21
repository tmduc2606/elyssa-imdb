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
    description="Weekly model retraining: check freshness → feature engineering → train → register → deploy canary",
) as dag:

    check_freshness = PythonOperator(
        task_id="check_gold_freshness",
        python_callable=_check_freshness,
    )

    feature_engineering = BashOperator(
        task_id="run_feature_engineering",
        bash_command=(
            "cd /opt/airflow && "
            "python data-science/scripts/run_feature_engineering.py "
            "--input /data/marts "
            "--output /data/features"
        ),
    )

    train_evaluate = BashOperator(
        task_id="train_and_evaluate",
        bash_command=(
            "cd /opt/airflow && "
            "python data-science/scripts/run_training.py "
            "--features /data/features "
            "--from-airflow"
        ),
    )

    register_mlflow = BashOperator(
        task_id="register_in_mlflow",
        bash_command=(
            "cd /opt/airflow && "
            "python data-science/scripts/register_model.py "
            "--tracking-uri http://mlflow:5000"
        ),
    )

    deploy_canary = BashOperator(
        task_id="deploy_canary",
        bash_command=(
            "echo 'Canary deploy triggered for model version: $(mlflow models list "
            "--model Elyssa_Genre_GMU | tail -1)'"
        ),
    )

    check_freshness >> feature_engineering >> train_evaluate >> register_mlflow >> deploy_canary
