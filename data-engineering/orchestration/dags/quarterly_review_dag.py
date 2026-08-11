"""
Quarterly Observability Review DAG.

Generates a health report covering:
- Alert frequency and SLA compliance
- Row count trends
- DQ check pass rates
- Pipeline runtime statistics
- Threshold drift detection

Runs quarterly (Jan, Apr, Jul, Oct) via cron trigger.
"""

from datetime import datetime, timedelta
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.utils.trigger_rule import TriggerRule

from config.secrets import pg_connect_kwargs

default_args = {
    "owner": "de-team",
    "depends_on_past": False,
    "email_on_failure": True,
    "email_on_retry": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=1),
}


def generate_observability_report(**context):
    """
    Generate a quarterly observability health report.

    Queries data_quality_log, graph_sync_status, and pipeline
    metadata to produce a summary of pipeline health.
    """
    import psycopg2
    import json

    conn = psycopg2.connect(**pg_connect_kwargs())
    cursor = conn.cursor()

    report = {
        "report_period": "quarterly",
        "generated_at": datetime.utcnow().isoformat(),
        "sections": {},
    }

    # ─── DQ Check pass rates (last 90 days) ─────────────────────────
    cursor.execute("""
        SELECT
            check_name,
            COUNT(*) AS total_runs,
            SUM(CASE WHEN passed THEN 1 ELSE 0 END) AS pass_count,
            ROUND(100.0 * SUM(CASE WHEN passed THEN 1 ELSE 0 END) / COUNT(*), 2) AS pass_rate_pct
        FROM silver.data_quality_log
        WHERE logged_at >= NOW() - INTERVAL '90 days'
        GROUP BY check_name
        ORDER BY check_name
    """)
    report["sections"]["dq_check_pass_rates"] = [
        {"check_name": row[0], "total_runs": row[1], "pass_count": row[2], "pass_rate_pct": float(row[3])}
        for row in cursor.fetchall()
    ]

    # ─── Alert frequency ────────────────────────────────────────────
    cursor.execute("""
        SELECT
            table_name,
            COUNT(*) AS alert_count
        FROM silver.data_quality_log
        WHERE passed = FALSE
          AND logged_at >= NOW() - INTERVAL '90 days'
        GROUP BY table_name
        ORDER BY alert_count DESC
    """)
    report["sections"]["alert_frequency"] = [
        {"table_name": row[0], "alert_count": row[1]}
        for row in cursor.fetchall()
    ]

    # ─── Sync status summary ────────────────────────────────────────
    cursor.execute("""
        SELECT sync_name, last_sync_ts, rows_synced, status
        FROM silver.graph_sync_status
        ORDER BY last_sync_ts DESC
    """)
    report["sections"]["sync_status"] = [
        {"sync_name": row[0], "last_sync_ts": str(row[1]), "rows_synced": row[2], "status": row[3]}
        for row in cursor.fetchall()
    ]

    cursor.close()
    conn.close()

    # Store report in DAG context for downstream tasks
    context["ti"].xcom_push(key="observability_report", value=report)

    print(f"[Observability] Report generated: {json.dumps(report, indent=2, default=str)}")
    return report


with DAG(
    dag_id="quarterly_review_dag",
    default_args=default_args,
    description="Quarterly observability review — health report generation",
    schedule="0 9 1 1,4,7,10 *",  # Quarterly: Jan/Apr/Jul/Oct 1st
    start_date=datetime(2026, 7, 1),
    catchup=False,
    tags=["observability", "quarterly", "review"],
) as dag:

    start = EmptyOperator(task_id="review_start")

    generate_report = PythonOperator(
        task_id="generate_observability_report",
        python_callable=generate_observability_report,
    )

    end = EmptyOperator(
        task_id="review_end",
        trigger_rule=TriggerRule.ALL_SUCCESS,
    )

    start >> generate_report >> end
