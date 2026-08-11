"""
Elyssa-IMDb Pipeline — Main DAG

Orchestrates: Sensor → Bronze (standalone subprocess) → Silver ETL → Gold dbt → DQ checks
Execution order:
   0. imdb_sensor           (detect new .tsv files)
   1. run_bronze            (spawn standalone run_bronze.py via Popen with start_new_session=True)
   2. wait_bronze           (sensor polling for .completed marker)
   3. bronze_ingestion_done (checkpoint marker)
   4. silver_transform      (spawn silver_operator.py in etl-runner)
   5. wait_silver           (poll PG tables + fail fast on .silver.failed marker)
   6. silver_export         (Silver → Parquet snapshot for DS benchmarking)
   7. wait_silver_export    (sensor polling .export.completed marker)
   8. gold_dbt_run          (spawn dbt run)
   9. wait_dbt_run          (sensor polling .dbt.run.completed marker)
  10. gold_dbt_test         (spawn dbt test)
  11. wait_dbt_test         (sensor polling .dbt.test.completed marker)
  12. dq_checks             (null-rate, referential integrity, row-count, quarantine)
  13. freshness_check       (check last_updated freshness SLA)
  14. gold_export           (Gold → Parquet + _MANIFEST.json)
  15. wait_gold_export      (sensor polling gold .export.completed marker)
  16. pipeline_end
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta, timezone

# ─── Ensure data-engineering module is importable ───────────────────
for _p in ("/opt/airflow/data-engineering/orchestration", "/opt/airflow/data-engineering", "/opt/airflow"):
    if os.path.isdir(_p) and _p not in sys.path:
        sys.path.insert(0, _p)

from airflow import DAG
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator
from airflow.sensors.base import BaseSensorOperator

from pipeline_logger import get_logger

from config.secrets import pg_connect_kwargs

from operators.dbt_operator import DbtRunOperator
from operators.dbt_done_sensor import DbtDoneSensor
from operators.dq_operator import DataQualityOperator
from operators.freshness_operator import FreshnessCheckOperator
from operators.imdb_sensor import IMDbDataSensor
from operators.gold_export_operator import GoldExportOperator
from operators.gold_export_sensor import GoldExportDoneSensor
from operators.silver_export_operator import SilverExportOperator
from operators.bronze_sensor import BronzeCompletionSensor
from operators.silver_export_sensor import SilverExportDoneSensor

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
_NOTIFICATION_URL = os.environ.get("PIPELINE_NOTIFICATION_URL", "")
_STATUS_FILE = os.environ.get("PIPELINE_STATUS_FILE", "/opt/airflow/output/pipeline_status.json")


def _send_notification(status: str, dag_id: str, task_id: str = "", message: str = ""):
    """POST JSON payload to notification URL (ntfy.sh, Slack webhook, etc.)."""
    if not _NOTIFICATION_URL:
        return
    try:
        import urllib.request
        payload = json.dumps({"status": status, "dag_id": dag_id, "task_id": task_id, "message": message}).encode()
        req = urllib.request.Request(_NOTIFICATION_URL, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=5)
    except Exception as e:
        print(f"[ALERT] Failed to send notification: {e}")


def _write_status_file(status: str, dag_id: str, task_id: str = "", message: str = ""):
    """Write pipeline status to a JSON file for external monitoring."""
    try:
        os.makedirs(os.path.dirname(_STATUS_FILE), exist_ok=True)
        with open(_STATUS_FILE, "w") as f:
            json.dump({"status": status, "dag_id": dag_id, "task_id": task_id, "message": message}, f)
    except Exception as e:
        print(f"[ALERT] Failed to write status file: {e}")


def _on_success_callback(context):
    """Business-impact alerting on task success."""
    task_instance = context.get("task_instance")
    dag_id = context.get("dag", {}).dag_id if context.get("dag") else "unknown"
    task_id = task_instance.task_id if task_instance else "unknown"
    print(f"[ALERT:OK] DAG={dag_id} Task={task_id} SUCCESS")
    _write_status_file("success", dag_id, task_id)


def _on_failure_callback(context):
    """Business-impact alerting on task failure."""
    task_instance = context.get("task_instance")
    dag_id = context.get("dag", {}).dag_id if context.get("dag") else "unknown"
    task_id = task_instance.task_id if task_instance else "unknown"
    exception = context.get("exception")
    log_url = getattr(task_instance, "log_url", "") if task_instance else ""

    severity = "HIGH" if "bronze" in task_id or task_id == "silver_transform" else "MEDIUM"
    log_msg = f"[ALERT:{severity}] DAG={dag_id} Task={task_id} FAILED | Exception: {exception} | Log: {log_url}"
    print(log_msg)
    _write_status_file("failed", dag_id, task_id, str(exception))
    _send_notification("failed", dag_id, task_id, str(exception))


def _on_retry_callback(context):
    """Warn on retry — early signal of transient failures."""
    task_instance = context.get("task_instance")
    if task_instance:
        print(f"[ALERT:WARN] Task {task_instance.task_id} retrying (attempt {task_instance.try_number})")


default_args = {
    "owner": "de-team",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": _retry_cfg.get("max_retries", 4),
    "retry_delay": timedelta(seconds=_retry_cfg.get("base_delay_s", 60)),
    "retry_exponential_backoff": True,
    "max_retry_delay": timedelta(seconds=_retry_cfg.get("max_delay_s", 1800)),
    "execution_timeout": timedelta(hours=8),
    "on_success_callback": _on_success_callback,
    "on_failure_callback": _on_failure_callback,
    "on_retry_callback": _on_retry_callback,
}

# ─── Bronze: standalone subprocess (bypasses supervisor heartbeat kill) ──
# run_bronze.py is spawned with start_new_session=True so it survives
# Airflow's supervisor killing the parent process.
BRONZE_SCRIPT = "/opt/airflow/data-engineering/scripts/run_bronze.py"


def _spawn_bronze(**context):
    """Spawn run_bronze.py as detached subprocess in new session."""
    import subprocess
    # Log lives on the etl_temp volume (/opt/airflow/output/tmp) so it
    # survives container restarts and is tailable from the host via
    # `docker exec elyssa-airflow tail -f /opt/airflow/output/tmp/bronze_runner.log`
    log_path = "/opt/airflow/output/tmp/bronze_runner.log"
    with open(log_path, "w") as lf:
        lf.write(f"[{datetime.now(timezone.utc).isoformat()}] Spawning run_bronze.py\n")
    proc = subprocess.Popen(
        [sys.executable, BRONZE_SCRIPT],
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"Bronze subprocess spawned: PID={proc.pid}")
    return {"bronze_pid": proc.pid}


def _spawn_silver(**context):
    """Spawn silver_operator.py as a detached subprocess inside etl-runner.

    Uses start_new_session=True so the process survives Airflow's
    supervisor heartbeat timeout. The task returns immediately and
    SilverDoneSensor polls Postgres for completion.
    """
    import subprocess
    # Log lives on the etl_temp volume (/opt/airflow/output/tmp in airflow,
    # /opt/etl/tmp in etl-runner) so it survives container restarts and is
    # tailable from both containers: e.g.
    #   docker exec elyssa-etl-runner tail -f /opt/etl/tmp/silver_etl.log
    log_path = "/opt/airflow/output/tmp/silver_etl.log"
    with open(log_path, "w") as lf:
        lf.write(f"[{datetime.now(timezone.utc).isoformat()}] Spawning silver ETL\n")
    proc = subprocess.Popen(
        [
            "docker", "exec", "elyssa-etl-runner",
            "python", "/opt/etl/data-engineering/orchestration/operators/silver_operator.py",
        ],
        stdout=open(log_path, "a"),
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    print(f"Silver subprocess spawned: PID={proc.pid}")
    return {"silver_pid": proc.pid}


class SilverDoneSensor(BaseSensorOperator):
    """Poll Postgres until all 14 silver tables (6 parent + 8 child) have rows."""

    template_fields = ()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def execute(self, context):
        import psycopg2
        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        all_tables = [
            "title_basics", "title_akas", "title_episode",
            "title_rating", "title_principal", "name_basics",
            "title_genre", "title_director", "title_writer",
            "title_akas_type", "title_akas_attribute", "title_principal_char",
            "name_profession", "name_known_for_title",
        ]
        populated = 0
        max_attempts = 480
        attempt = 0
        # Shared etl_temp volume — same path as silver_operator's temp_root
        failed_marker = "/opt/airflow/output/tmp/.silver.failed"
        while attempt < max_attempts:
            if os.path.exists(failed_marker):
                msg = f"Silver ETL failed (marker {failed_marker} present). Check /opt/airflow/output/tmp/silver_etl.log"
                self.log.error(msg)
                try:
                    with open(failed_marker) as _f:
                        self.log.error(f"Silver failure reason: {_f.read().strip()}")
                except OSError:
                    pass
                raise RuntimeError(msg)
            try:
                pg = psycopg2.connect(**pg_connect_kwargs())
                cur = pg.cursor()
                populated = 0
                for tbl in all_tables:
                    cur.execute(
                        "SELECT n_live_tup FROM pg_stat_user_tables "
                        "WHERE schemaname='silver' AND relname=%s",
                        (tbl,),
                    )
                    row = cur.fetchone()
                    if row and row[0] > 0:
                        populated += 1
                    else:
                        cur.execute(f"SELECT 1 FROM silver.{tbl} LIMIT 1")
                        if cur.fetchone():
                            populated += 1
                cur.close()
                pg.close()
                if populated >= len(all_tables):
                    log.log_stage(
                        stage="silver_wait", batch_id=batch_id,
                        status="complete",
                        message=f"{populated}/{len(all_tables)} tables populated",
                    )
                    return
            except Exception as e:
                self.log.warning(f"Poll error: {e}")
            attempt += 1
            if attempt % 4 == 0:
                self.log.info(
                    f"Waiting for silver... ({populated}/{len(all_tables)} tables, attempt {attempt}/{max_attempts})"
                )
            time.sleep(30)
        raise RuntimeError(
            f"Silver load did not complete within timeout: {populated}/{len(all_tables)} tables populated after {max_attempts} attempts"
        )


# ─── DAG Definition ─────────────────────────────────────────────────────
with DAG(
    dag_id="imdb_pipeline",
    default_args=default_args,
    description="Elyssa IMDb Sensor → Bronze (per-table) → Silver → Gold → DQ pipeline",
    schedule=None,
    start_date=datetime(2026, 6, 1),
    catchup=False,
    tags=["imdb", "bronze", "silver", "gold"],
) as dag:

    start = EmptyOperator(task_id="pipeline_start")

    # ─── Sensor (detect new data) ─────────────────────────────────────────
    imdb_sensor = IMDbDataSensor(
        task_id="imdb_data_sensor",
        source_dir="s3://imdb-source/",
        poke_interval=300,
        timeout=3600,
        mode="reschedule",
    )

    # ─── Bronze (standalone subprocess — bypasses supervisor kill) ────────
    # run_bronze: spawns run_bronze.py as detached subprocess, exits immediately
    # The subprocess runs in its own session (start_new_session=True), so when
    # Airflow's supervisor kills this task's subprocess after heartbeat timeout,
    # the bronze script is reparented to PID 1 and continues running.
    run_bronze = PythonOperator(
        task_id="run_bronze",
        python_callable=_spawn_bronze,
        retries=0,
        execution_timeout=timedelta(seconds=30),
    )

    # wait_bronze: polls for .completed / .failed markers
    wait_bronze = BronzeCompletionSensor(
        task_id="wait_bronze",
        bronze_dir=_BRONZE_PATH,
        poke_interval=30,
        timeout=28800,
        mode="reschedule",
        retries=0,
    )

    # ─── Bronze Ingestion Complete ────────────────────────────────────────
    bronze_done = EmptyOperator(task_id="bronze_ingestion_done")

    # ─── Silver (detached subprocess in etl-runner) ──────────────────
    # Spawns silver_operator.py inside etl-runner and returns immediately.
    # SilverDoneSensor polls Postgres until all parent tables have rows.
    silver_transform = PythonOperator(
        task_id="silver_transform",
        python_callable=_spawn_silver,
        retries=0,
        execution_timeout=timedelta(seconds=30),
    )

    wait_silver = SilverDoneSensor(
        task_id="wait_silver",
        poke_interval=30,
        timeout=28800,
        mode="reschedule",
        retries=_retry_cfg.get("max_retries", 4),
        retry_delay=timedelta(seconds=_retry_cfg.get("base_delay_s", 60)),
        retry_exponential_backoff=True,
        max_retry_delay=timedelta(seconds=_retry_cfg.get("max_delay_s", 1800)),
    )

    # ─── Silver Export (Parquet snapshot for DS benchmarking, persists across Docker wipes) ─
    # Detached subprocess pattern (same as run_bronze / silver ETL): the
    # operator spawns silver_export_runner.py in a new session and returns
    # immediately; wait_silver_export polls for the .export.completed marker.
    # In-process COPY work is SIGKILLed by the scheduler's 300s orphan-pass.
    silver_export = SilverExportOperator(
        task_id="silver_export",
        output_dir="/opt/airflow/output/silver/",
        retries=0,
        execution_timeout=timedelta(seconds=30),
    )

    wait_silver_export = SilverExportDoneSensor(
        task_id="wait_silver_export",
        output_dir="/opt/airflow/output/silver/",
        poke_interval=30,
        timeout=28800,
        mode="reschedule",
        retries=0,
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

    # ─── Gold completion sensors (spawners return immediately) ───────────
    wait_dbt_run = DbtDoneSensor(
        task_id="wait_dbt_run",
        project_dir="/opt/airflow/data-engineering/gold",
        suffix="run",
        poke_interval=30,
        timeout=28800,
        mode="reschedule",
        retries=0,
    )

    wait_dbt_test = DbtDoneSensor(
        task_id="wait_dbt_test",
        project_dir="/opt/airflow/data-engineering/gold",
        suffix="test",
        poke_interval=30,
        timeout=28800,
        mode="reschedule",
        retries=0,
    )

    # ─── Data Quality (halts on threshold violations) ─────────────────────
    # Credentials are resolved from env/Airflow Connections at execute time
    # (config/secrets.py) — nothing hardcoded in the DAG (C1-C7).
    dq_checks = DataQualityOperator(
        task_id="dq_checks",
        dq_config_path="/opt/airflow/data-engineering/dq/config.yaml",
        run_gx=True,
        bronze_path=_BRONZE_PATH,
    )

    # ─── Freshness ────────────────────────────────────────────────────────
    freshness_check = FreshnessCheckOperator(
        task_id="freshness_check",
        sla_hours=24,
    )

    # ─── Gold Export (DuckDB postgres_scanner → Snappy Parquet + manifest) ─
    gold_export = GoldExportOperator(
        task_id="gold_export",
        output_dir="/opt/airflow/output/gold/",
    )

    wait_gold_export = GoldExportDoneSensor(
        task_id="wait_gold_export",
        output_dir="/opt/airflow/output/gold/",
        poke_interval=30,
        timeout=28800,
        mode="reschedule",
        retries=0,
    )

    end = EmptyOperator(task_id="pipeline_end")

    # ─── DAG Structure ────────────────────────────────────────────────────
    # Sensor → spawn bronze → wait for bronze → silver → gold → dq → freshness → gold_export → end
    # run_bronze exits immediately (spawns detached subprocess).
    # wait_bronze polls .completed marker (subprocess runs independently).
    # All spawner tasks (bronze, silver, silver_export, dbt, gold_export) are
    # followed by completion sensors — the detached subprocesses run outside
    # Airflow's supervisor, and downstream tasks must not start until the
    # actual work is done.
    start >> imdb_sensor

    imdb_sensor >> run_bronze >> wait_bronze >> bronze_done

    bronze_done >> silver_transform >> wait_silver
    wait_silver >> silver_export >> wait_silver_export

    wait_silver_export >> gold_dbt_run >> wait_dbt_run
    wait_dbt_run >> gold_dbt_test >> wait_dbt_test

    wait_dbt_test >> dq_checks >> freshness_check >> gold_export >> wait_gold_export >> end