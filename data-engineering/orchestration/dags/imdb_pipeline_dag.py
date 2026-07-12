"""
Elyssa-IMDb Pipeline — Main DAG

Orchestrates: Sensor → Bronze ingestion → Silver ETL → Gold dbt → Neo4j sync → DQ checks
Execution order:
  0. imdb_sensor           (detect new .tsv files)
  1. bronze_ingest          (DuckDB TSV→Parquet, with quarantine)
  2. silver_transform       (DuckDB→CSV→psycopg2 COPY, parent+child normalization)
  3. gold_dbt_run           (dbt run for staging → intermediate → marts)
  4. gold_dbt_test          (dbt test for Gold validation)
  5. neo4j_sync             (sync silver tables to Neo4j graph)
  6. dq_checks              (null-rate, referential integrity, row-count)
  7. freshness_monitor      (check last_updated freshness SLA)
"""

import json
import os
import sys
from datetime import datetime, timedelta

# ─── Ensure data-engineering module is importable ───────────────────
for _p in ("/opt/airflow/data-engineering/orchestration", "/opt/airflow/data-engineering", "/opt/airflow"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

from operators.bronze_operator import BronzeIngestOperator
from operators.silver_operator import SilverTransformOperator
from operators.dbt_operator import DbtRunOperator
from operators.neo4j_operator import Neo4jSyncOperator
from operators.dq_operator import DataQualityOperator
from operators.freshness_operator import FreshnessCheckOperator
from operators.imdb_sensor import IMDbDataSensor
from operators.quarantine_operator import QuarantineCheckOperator

# ─── Retry config (exponential backoff) ─────────────────────────────
_RETRY_CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "retry.yaml"
)


def _load_retry_config() -> dict:
    try:
        import yaml
        with open(_RETRY_CONFIG_PATH) as f:
            return yaml.safe_load(f)
    except Exception:
        return {
            "max_retries": 4,
            "base_delay_s": 60,
            "max_delay_s": 1800,
            "exponential_factor": 2,
        }


_retry_cfg = _load_retry_config()

# ─── Centralized path config ────────────────────────────────────────
_PATHS_CONFIG = os.path.join(os.path.dirname(__file__), "..", "config", "paths.yaml")
_BRONZE_PATH = "/opt/airflow/output/bronze/"  # fallback default
try:
    import yaml
    with open(_PATHS_CONFIG) as _pf:
        _paths = yaml.safe_load(_pf)
    _BRONZE_PATH = _paths["bronze"]["output_path"]
except Exception:
    pass


# ─── Alerting callbacks ──────────────────────────────────────────────
def _on_failure_callback(context):
    """Business-impact alerting on task failure."""
    task_instance = context.get("task_instance")
    dag_id = context.get("dag", {}).dag_id if context.get("dag") else "unknown"
    task_id = task_instance.task_id if task_instance else "unknown"
    exception = context.get("exception")
    log_url = task_instance.get_log_url() if task_instance else ""

    severity = "HIGH" if task_id in ["bronze_ingest", "silver_transform"] else "MEDIUM"
    print(f"[ALERT:{severity}] DAG={dag_id} Task={task_id} FAILED")
    print(f"[ALERT] Exception: {exception}")
    print(f"[ALERT] Log: {log_url}")


def _on_retry_callback(context):
    """Warn on retry — early signal of transient failures."""
    task_instance = context.get("task_instance")
    if task_instance:
        print(
            f"[ALERT:WARN] Task {task_instance.task_id} retrying "
            f"(attempt {task_instance.try_number})"
        )


default_args = {
    "owner": "de-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": _retry_cfg.get("max_retries", 4),
    "retry_delay": timedelta(seconds=_retry_cfg.get("base_delay_s", 60)),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(seconds=_retry_cfg.get("max_delay_s", 1800)),
    "execution_timeout": timedelta(hours=8),
    "on_failure_callback": _on_failure_callback,
    "on_retry_callback": _on_retry_callback,
}

with DAG(
    dag_id="imdb_pipeline",
    default_args=default_args,
    description="Elyssa IMDb Sensor → Bronze → Silver → Gold → Neo4j → DQ pipeline",
    schedule=None,
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["imdb", "bronze", "silver", "gold", "neo4j"],
) as dag:

    start = EmptyOperator(task_id="pipeline_start")

    # ─── Sensor (detect new data) ─────────────────────────────────────────
    imdb_sensor = IMDbDataSensor(
        task_id="imdb_data_sensor",
        source_dir="/opt/airflow/data-engineering/duke/gate0/source/",
        file_pattern="*.tsv",
        poke_interval=300,
        timeout=3600,
        mode="reschedule",
    )

    # ─── Bronze (TSV → Parquet, with quarantine) ──────────────────────────
    bronze_ingest = BronzeIngestOperator(
        task_id="bronze_ingest",
        source_tables=[
            "title.basics", "title.akas", "title.crew",
            "title.episode", "title.principals", "title.ratings",
            "name.basics",
        ],
        bronze_path=_BRONZE_PATH,
    )

    # ─── Bronze Ingestion Complete ────────────────────────────────────────
    bronze_done = EmptyOperator(task_id="bronze_ingestion_done")

    # ─── Quarantine Check (post-bronze validation) ────────────────────────
    quarantine_check = QuarantineCheckOperator(
        task_id="quarantine_check",
        jdbc_url="postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user="elyssa",
        jdbc_password="elyssa_pg_2026",
        fail_threshold=1000,
    )

    # ─── Silver (parent + child normalization) ────────────────────────────
    silver_transform = SilverTransformOperator(
        task_id="silver_transform",
        bronze_path=_BRONZE_PATH,
        jdbc_url="postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user="elyssa",
        jdbc_password="elyssa_pg_2026",
    )

    # ─── Gold (dbt run + test) ────────────────────────────────────────────
    gold_dbt_run = DbtRunOperator(
        task_id="gold_dbt_run",
        dbt_project_dir="/opt/airflow/data-engineering/gold",
        dbt_target="prod",
    )

    gold_dbt_test = DbtRunOperator(
        task_id="gold_dbt_test",
        dbt_project_dir="/opt/airflow/data-engineering/gold",
        dbt_command="test",
        dbt_target="prod",
    )

    # ─── Neo4j ────────────────────────────────────────────────────────────
    neo4j_sync = Neo4jSyncOperator(
        task_id="neo4j_sync",
        neo4j_uri="bolt://neo4j:7687",
        neo4j_user="neo4j",
        neo4j_password="elyssa_neo_2026",
        tables_to_sync=["title_basics", "name_basics", "title_principal"],
    )

    # ─── Data Quality (halts on threshold violations) ─────────────────────
    dq_checks = DataQualityOperator(
        task_id="dq_checks",
        jdbc_url="postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user="elyssa",
        jdbc_password="elyssa_pg_2026",
        dq_config_path="/opt/airflow/data-engineering/dq/config.yaml",
        run_gx=True,
        bronze_path=_BRONZE_PATH,
    )

    # ─── Freshness ────────────────────────────────────────────────────────
    freshness_check = FreshnessCheckOperator(
        task_id="freshness_check",
        jdbc_url="postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user="elyssa",
        jdbc_password="elyssa_pg_2026",
        sla_hours=24,
    )

    end = EmptyOperator(task_id="pipeline_end")

    # ─── DAG Structure ────────────────────────────────────────────────────
    # Sensor → bronze → quarantine_check → silver → gold → neo4j → dq → freshness → end
    # gold_dbt_test depends on gold_dbt_run (tests run against fresh Gold tables)
    # db_ingest REMOVED from critical path (Phase 1 optimization A3) — was a no-op copy
    start >> imdb_sensor >> bronze_ingest >> bronze_done
    bronze_done >> quarantine_check >> silver_transform
    silver_transform >> gold_dbt_run >> [gold_dbt_test, neo4j_sync]
    gold_dbt_test >> dq_checks
    neo4j_sync >> dq_checks >> freshness_check >> end