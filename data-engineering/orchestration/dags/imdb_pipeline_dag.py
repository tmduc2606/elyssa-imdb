"""
Elyssa-IMDb Pipeline — Main DAG

Orchestrates: Bronze ingestion → Silver ETL → Gold dbt → Neo4j sync → DQ checks
Execution order:
  1. bronze_ingest          (7 parallel sensors → PySpark jobs)
  2. silver_transform       (schema enforcer → array normalizer → SCD2 → upsert)
  3. gold_dbt               (dbt run for staging → intermediate → marts)
  4. neo4j_sync             (sync silver tables to Neo4j graph)
  5. data_quality           (Great Expectations + row-count checks)
  6. freshness_monitor      (check last_updated freshness SLA)
"""

import json
import os
import sys
from datetime import datetime, timedelta

# ─── Ensure data-engineering module is importable ───────────────────
# Inside Docker, dags are at /opt/airflow/dags/ and data-engineering
# is mounted at /opt/airflow/data-engineering/. We need either
# /opt/airflow or /opt/airflow/data-engineering on sys.path so that
# `from bronze.*` and `from operators.*` resolve correctly.
for _p in ("/opt/airflow/data-engineering", "/opt/airflow"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from airflow import DAG
from airflow.operators.dummy import DummyOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.external_task import ExternalTaskSensor

from operators.bronze_operator import BronzeIngestOperator
from operators.silver_operator import SilverTransformOperator
from operators.dbt_operator import DbtRunOperator
from operators.neo4j_operator import Neo4jSyncOperator
from operators.dq_operator import DataQualityOperator
from operators.freshness_operator import FreshnessCheckOperator
from operators.db_operator import DatabaseIngestOperator
from sensors.imdb_sensor import DataFileSensor

# ─── Load retry config ──────────────────────────────────────────────
_RETRY_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "retry.yaml"
)
def _load_retry_config() -> dict:
    try:
        import yaml
        with open(_RETRY_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    except Exception:
        return {"max_retries": 4, "base_delay_s": 60, "max_delay_s": 1800, "exponential_factor": 2}

_retry_cfg = _load_retry_config()


# ─── Alerting callbacks ──────────────────────────────────────────────
def _on_failure_callback(context):
    """Business-impact alerting on task failure."""
    task_instance = context.get("task_instance")
    dag_id = context.get("dag", {}).dag_id if context.get("dag") else "unknown"
    task_id = task_instance.task_id if task_instance else "unknown"
    exception = context.get("exception")
    log_url = task_instance.log_url if task_instance else ""

    severity = "HIGH" if task_id in ["bronze_ingest", "silver_transform"] else "MEDIUM"
    print(f"[ALERT:{severity}] DAG={dag_id} Task={task_id} FAILED")
    print(f"[ALERT] Exception: {exception}")
    print(f"[ALERT] Log: {log_url}")


def _on_retry_callback(context):
    """Warn on retry — early signal of transient failures."""
    task_instance = context.get("task_instance")
    if task_instance:
        print(f"[ALERT:WARN] Task {task_instance.task_id} retrying (attempt {task_instance.try_number})")


default_args = {
    "owner": "de-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": _retry_cfg.get("max_retries", 4),
    "retry_delay": timedelta(seconds=_retry_cfg.get("base_delay_s", 60)),
    "max_retry_delay": timedelta(seconds=_retry_cfg.get("max_delay_s", 1800)),
    "execution_timeout": timedelta(hours=4),
    "on_failure_callback": _on_failure_callback,
    "on_retry_callback": _on_retry_callback,
}

with DAG(
    dag_id="imdb_pipeline",
    default_args=default_args,
    description="Elyssa IMDb Bronze → Silver → Gold → Neo4j → DQ pipeline",
    schedule=None,
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["imdb", "bronze", "silver", "gold", "neo4j"],
) as dag:

    start = EmptyOperator(task_id="pipeline_start")

    # ─── Bronze (TSV) ───────────────────────────────────────────────────────
    bronze_ingest = BronzeIngestOperator(
        task_id="bronze_ingest",
        source_tables=[
            "title.basics", "title.akas", "title.crew",
            "title.episode", "title.principals", "title.ratings",
            "name.basics",
        ],
        bronze_path="/data/bronze/",
    )

    # ─── Bronze (Database) ───────────────────────────────────────────────────
    db_ingest = DatabaseIngestOperator(
        task_id="db_ingest",
        source_tables=[
            "title.basics", "title.akas", "title.crew",
            "title.episode", "title.principals", "title.ratings",
            "name.basics",
        ],
        source_type="postgresql",
        bronze_path="/data/bronze/db/",
        incremental=True,
    )

    # ─── Bronze Ingestion Complete ───────────────────────────────────────────
    bronze_done = EmptyOperator(task_id="bronze_ingestion_done")

    # ─── Silver ──────────────────────────────────────────────────────────────
    silver_transform = SilverTransformOperator(
        task_id="silver_transform",
        bronze_path="/data/bronze/",
        jdbc_url="{{ conn.postgres_silver.host }}",
        jdbc_user="{{ conn.postgres_silver.login }}",
        jdbc_password="{{ conn.postgres_silver.password }}",
    )

    # ─── Gold ────────────────────────────────────────────────────────────────
    gold_dbt_run = DbtRunOperator(
        task_id="gold_dbt_run",
        dbt_project_dir="/opt/dbt/imdb_gold",
        dbt_target="prod",
    )

    gold_dbt_test = DbtRunOperator(
        task_id="gold_dbt_test",
        dbt_project_dir="/opt/dbt/imdb_gold",
        dbt_command="test",
        dbt_target="prod",
    )

    # ─── Neo4j ───────────────────────────────────────────────────────────────
    neo4j_sync = Neo4jSyncOperator(
        task_id="neo4j_sync",
        neo4j_uri="{{ conn.neo4j.uri }}",
        neo4j_user="{{ conn.neo4j.login }}",
        neo4j_password="{{ conn.neo4j.password }}",
        tables_to_sync=["title_basics", "name_basics", "title_principal"],
    )

    # ─── Data Quality ────────────────────────────────────────────────────────
    dq_checks = DataQualityOperator(
        task_id="dq_checks",
        jdbc_url="{{ conn.postgres_silver.host }}",
        jdbc_user="{{ conn.postgres_silver.login }}",
        jdbc_password="{{ conn.postgres_silver.password }}",
        dq_config_path="/opt/dq/config.yaml",
    )

    # ─── Freshness ──────────────────────────────────────────────────────────
    freshness_check = FreshnessCheckOperator(
        task_id="freshness_check",
        jdbc_url="{{ conn.postgres_silver.host }}",
        jdbc_user="{{ conn.postgres_silver.login }}",
        jdbc_password="{{ conn.postgres_silver.password }}",
        sla_hours=24,
    )

    end = EmptyOperator(task_id="pipeline_end")

    # ─── DAG Structure ───────────────────────────────────────────────────────
    start >> [bronze_ingest, db_ingest] >> bronze_done >> silver_transform >> [gold_dbt_run, gold_dbt_test]
    gold_dbt_run >> neo4j_sync >> dq_checks >> freshness_check >> end
    gold_dbt_test >> dq_checks
