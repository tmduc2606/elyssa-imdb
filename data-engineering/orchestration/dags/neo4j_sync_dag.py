"""
Neo4j Sync DAG — Separate DAG for graph synchronization.

Runs after the main pipeline completes successfully.
Triggered by trigger_rule="all_success" from the main DAG's
gold_dbt_run task.
"""

import os
import sys
from datetime import datetime, timedelta

# ─── Ensure orchestration module is importable ─────────────────────
for _p in ("/opt/airflow/data-engineering/orchestration", "/opt/airflow/data-engineering", "/opt/airflow"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

from operators.neo4j_operator import Neo4jSyncOperator

default_args = {
    "owner": "de-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=2),
    "max_retry_delay": timedelta(minutes=30),
    "execution_timeout": timedelta(hours=2),
}

with DAG(
    dag_id="neo4j_sync_dag",
    default_args=default_args,
    description="Neo4j graph sync — runs after main pipeline gold refresh",
    schedule=None,  # Triggered by main DAG
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["neo4j", "graph", "sync"],
) as dag:

    start = EmptyOperator(task_id="sync_start")

    neo4j_sync = Neo4jSyncOperator(
        task_id="neo4j_sync",
        neo4j_uri="{{ conn.neo4j.uri }}",
        neo4j_user="{{ conn.neo4j.login }}",
        neo4j_password="{{ conn.neo4j.password }}",
        tables_to_sync=["title_basics", "name_basics", "title_principal"],
    )

    end = EmptyOperator(
        task_id="sync_end",
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    start >> neo4j_sync >> end
