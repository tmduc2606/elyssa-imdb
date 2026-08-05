"""
Elyssa-IMDb | DBT Operator (spawner)

Spawns scripts/dbt_runner.py as a detached subprocess in a new session
(same pattern as run_bronze / silver ETL). The runner does the dbt command
work OUTSIDE Airflow's supervisor, which otherwise SIGKILLs any in-process
task every 300s orphan-pass cycle.

The operator does preparatory work (lock, kill stale dbt processes, clean
artifacts, run deps if needed) then spawns the runner and returns
immediately. DbtRunDoneSensor / DbtTestDoneSensor poll for completion markers.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from airflow.models import BaseOperator

RUNNER_SCRIPT = "/opt/airflow/data-engineering/scripts/dbt_runner.py"
DBT_LOCK_FILE = "/tmp/dbt_run.lock"


class DbtRunOperator(BaseOperator):
    """
    Executes a dbt command (run, test, etc.) for the Gold layer.

    Instead of running dbt synchronously, this operator:
      1. Performs setup: acquire file lock, kill stale dbt processes,
         clean dbt artifacts, run deps if needed.
      2. Spawns dbt_runner.py as a detached subprocess (start_new_session=True)
         to execute the actual dbt command.
      3. Returns immediately; a downstream sensor (DbtRunDoneSensor or
         DbtTestDoneSensor) polls for completion markers.

    The spawn pattern matches that of run_bronze.py and silver_operator.py
    to survive the scheduler's 300s orphan-pass reset.
    """

    template_fields = ("dbt_project_dir",)

    def __init__(
        self,
        dbt_project_dir: str = "/opt/airflow/data/gold",
        dbt_command: str = "run",
        dbt_target: str = "prod",
        *args,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.dbt_project_dir = dbt_project_dir
        self.dbt_command = dbt_command
        self.dbt_target = dbt_target

    def execute(self, context):
        project_dir = Path(self.dbt_project_dir)
        if not project_dir.exists():
            # Try the default location under data-engineering
            alt = Path("/opt/airflow/data-engineering/gold")
            if alt.exists():
                project_dir = alt
            else:
                raise ValueError(f"DBT project directory not found: {self.dbt_project_dir}")

        # Prepare env for dbt_runner.py
        env = dict(os.environ)
        if not env.get("GOLD_EXPORT_PG_PASSWORD"):
            # dbt needs the PG password to connect to the warehouse
            raise ValueError("GOLD_EXPORT_PG_PASSWORD environment variable is not set")

        # 1. Acquire exclusive file lock to prevent concurrent dbt runs
        lock_fd = os.open(DBT_LOCK_FILE, os.O_CREAT | os.O_WRONLY, 0o666)
        try:
            import fcntl

            fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (ImportError, IOError) as e:
            os.close(lock_fd)
            raise RuntimeError(
                f"Cannot acquire dbt lock ({DBT_LOCK_FILE}): another dbt process is running"
            ) from e

        try:
            # 2. Kill any stray dbt processes from previous runs
            # Pattern excludes this task's own process and the dbt_runner.py
            # spawner (cmdline contains "dbt_runner.py", not "dbt run/test").
            try:
                result = subprocess.run(
                    ["pgrep", "-f", "dbt (run|test|deps|compile)"],
                    capture_output=True, text=True, timeout=5
                )
                if result.stdout.strip():
                    pids = result.stdout.strip().split()
                    self.log.info(f"Found stale dbt processes: {pids}, killing them")
                    subprocess.run(
                        ["kill", "-9"] + pids, capture_output=True, timeout=5
                    )
            except Exception:
                self.log.warning("Failed to check/kill stale dbt processes")

            # 3. Clean dbt artifacts (target dir) to avoid stale state
            target_dir = project_dir / "target"
            if target_dir.exists():
                for item in target_dir.iterdir():
                    if item.suffix in (".json", ".msgblob", ".sql", ".log", ".pickle"):
                        try:
                            item.unlink()
                        except OSError:
                            pass
                partial_parse = target_dir / "partial_parse.msgpack"
                if partial_parse.exists():
                    try:
                        partial_parse.unlink()
                    except OSError:
                        pass
                # Drop any stale __dbt_tmp tables from Postgres
                try:
                    import psycopg2

                    conn = psycopg2.connect(
                        host="postgres",
                        port=5432,
                        dbname="elyssa_warehouse",
                        user="elyssa",
                        password=os.environ["GOLD_EXPORT_PG_PASSWORD"],
                    )
                    try:
                        with conn.cursor() as cur:
                            cur.execute(
                                """
                                SELECT schemaname || '.' || tablename
                                FROM pg_tables
                                WHERE tablename LIKE '___dbt_tmp%'
                                   OR tablename LIKE '%__dbt__tmp%'
                                """
                            )
                            rows = cur.fetchall()
                            for (table_name,) in rows:
                                self.log.info(f"Dropping stale dbt temp: {table_name}")
                                cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE")
                    finally:
                        conn.close()
                except Exception as e:
                    self.log.warning(f"Failed to clean dbt temp tables: {e}")
            # 4. Run dbt deps if needed
            deps_dir = project_dir / "dbt_packages"
            deps_file = project_dir / "packages.yml"
            if not deps_dir.is_dir() and deps_file.is_file():
                self.log.info("Running dbt deps (packages missing)")
                deps_cmd = [
                    "dbt",
                    "deps",
                    "--project-dir",
                    str(project_dir),
                    "--profiles-dir",
                    str(project_dir),
                ]
                deps_result = subprocess.run(
                    deps_cmd, capture_output=True, text=True, timeout=300
                )
                if deps_result.returncode != 0:
                    self.log.error(f"dbt deps failed: {deps_result.stderr}")
                    raise RuntimeError(f"dbt deps failed: {deps_result.stderr}")
                self.log.info("dbt deps succeeded")
            # 5. Spawn dbt_runner.py detached
            log_dir = Path("/opt/airflow/output/tmp")
            log_dir.mkdir(parents=True, exist_ok=True)
            log_path = log_dir / f"dbt_{self.dbt_command}.log"
            with open(log_path, "w") as lf:
                lf.write(
                    f"[{datetime.now(timezone.utc).isoformat()}] "
                    f"Spawning dbt_runner.py for {self.dbt_command}\n"
                )
            marker_dir = project_dir
            running_marker = marker_dir / f".dbt.{self.dbt_command}.running"
            completed_marker = marker_dir / f".dbt.{self.dbt_command}.completed"
            failed_marker = marker_dir / f".dbt.{self.dbt_command}.failed"
            # Clean stale markers
            for m in (running_marker, completed_marker, failed_marker):
                if m.exists():
                    m.unlink()
            # Write running marker
            running_marker.touch()
            cmd = [
                sys.executable,
                RUNNER_SCRIPT,
                "--project-dir",
                str(project_dir),
                "--target",
                self.dbt_target,
                "--command",
                self.dbt_command,
            ]
            proc = subprocess.Popen(
                cmd,
                stdout=open(log_path, "a"),
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env=env,
            )
            self.log.info(f"DBT subprocess spawned: PID={proc.pid}")
            return {"dbt_pid": proc.pid, "command": self.dbt_command}
        finally:
            # Release the lock (but keep the file for next acquisition)
            try:
                import fcntl

                fcntl.flock(lock_fd, fcntl.LOCK_UN)
            except Exception:
                pass
            os.close(lock_fd)