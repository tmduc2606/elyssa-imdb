import fcntl
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from airflow.models import BaseOperator

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger

DBT_LOCK_FILE = "/tmp/dbt_run.lock"


class DbtRunOperator(BaseOperator):
    """
    Executes a dbt command (run, test, etc.) for the Gold layer.

    Uses a file lock to prevent multiple concurrent dbt processes.
    Cleans stale dbt artifacts and kills leftover processes before starting.
    """

    template_fields = ("dbt_project_dir",)

    def __init__(
        self,
        dbt_project_dir: str = "/opt/dbt/imdb_gold",
        dbt_command: str = "run",
        dbt_target: str = "prod",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.dbt_project_dir = dbt_project_dir
        self.dbt_command = dbt_command
        self.dbt_target = dbt_target

    def _kill_stale_dbt(self):
        """Kill any leftover dbt processes from previous failed runs."""
        try:
            result = subprocess.run(
                ["pgrep", "-f", "dbt"],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip():
                pids = result.stdout.strip().split()
                self.log.info(f"Found stale dbt processes: {pids}, killing them")
                subprocess.run(["kill", "-9"] + pids, capture_output=True, timeout=5)
        except Exception:
            pass

    def _clean_dbt_artifacts(self, project_dir: str):
        """Remove stale dbt temp tables and partial parse cache."""
        target_dir = Path(project_dir) / "target"
        if target_dir.exists():
            for p in target_dir.iterdir():
                if p.suffix in (".json", ".msgpack", ".sql"):
                    p.unlink(missing_ok=True)
        partial_parse = Path(project_dir) / "target" / "partial_parse.msgpack"
        if partial_parse.exists():
            partial_parse.unlink()
        # Drop stale __dbt_tmp temp tables from PostgreSQL
        try:
            import psycopg2
            pg = psycopg2.connect(
                host="postgres", port=5432,
                user="elyssa", password="elyssa_pg_2026",
                dbname="elyssa_warehouse",
            )
            pg.autocommit = True
            cur = pg.cursor()
            cur.execute("""
                SELECT schemaname || '.' || tablename
                FROM pg_tables
                WHERE tablename LIKE '___dbt_tmp%'
                   OR tablename LIKE '%__dbt__tmp%'
            """)
            for row in cur.fetchall():
                self.log.info(f"Dropping stale dbt temp: {row[0]}")
                cur.execute(f"DROP TABLE IF EXISTS {row[0]} CASCADE")
            cur.close()
            pg.close()
        except Exception as e:
            self.log.warning(f"Failed to clean dbt temp tables: {e}")

    def execute(self, context):
        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage=f"dbt_{self.dbt_command}", batch_id=batch_id,
                      status="started", message=f"dbt {self.dbt_command} --target {self.dbt_target}")

        # Resolve dbt project path
        project_dir = self.dbt_project_dir
        if not os.path.isdir(project_dir):
            alt = "/opt/airflow/data-engineering/gold"
            if os.path.isdir(alt):
                project_dir = alt

        # Acquire exclusive file lock to prevent concurrent dbt runs
        with open(DBT_LOCK_FILE, "w") as lock_f:
            try:
                fcntl.flock(lock_f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except IOError:
                raise RuntimeError(
                    f"Cannot acquire dbt lock — another dbt process is running "
                    f"(lock file: {DBT_LOCK_FILE})"
                )

            # Kill stale dbt processes and clean artifacts
            self._kill_stale_dbt()
            self._clean_dbt_artifacts(project_dir)

            # Auto-run dbt deps if packages are missing
            packages_dir = os.path.join(project_dir, "dbt_packages")
            packages_yml = os.path.join(project_dir, "packages.yml")
            needs_deps = (
                not os.path.isdir(packages_dir)
                or (os.path.isdir(packages_dir) and not os.listdir(packages_dir))
            )
            if os.path.isfile(packages_yml) and needs_deps:
                deps_cmd = [
                    "dbt", "deps",
                    "--project-dir", project_dir,
                    "--profiles-dir", project_dir,
                ]
                self.log.info(f"Packages missing, running dbt deps: {' '.join(deps_cmd)}")
                deps_result = subprocess.run(deps_cmd, capture_output=True, text=True)
                if deps_result.returncode != 0:
                    self.log.error(f"dbt deps failed: {deps_result.stderr}")
                    log.log_error(stage="dbt_deps", batch_id=batch_id,
                                  error=f"dbt deps failed: {deps_result.stderr[-500:]}")
                    raise RuntimeError(f"dbt deps failed: {deps_result.stderr}")
                self.log.info(f"dbt deps succeeded")

            cmd = [
                "dbt",
                self.dbt_command,
                "--project-dir", project_dir,
                "--profiles-dir", project_dir,
                "--target", self.dbt_target,
                "--no-partial-parse",
            ]
            # For run command, use full-refresh if first run after schema changes
            if self.dbt_command == "run":
                cmd.append("--full-refresh")

            self.log.info(f"Running dbt: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=14400)
            elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)

            if result.returncode != 0:
                self.log.error(f"dbt {self.dbt_command} failed: {result.stderr}")
                log.log_error(stage=f"dbt_{self.dbt_command}", batch_id=batch_id,
                              error=f"dbt {self.dbt_command} failed: {result.stderr[-500:]}")
                raise RuntimeError(f"dbt {self.dbt_command} failed: {result.stderr}")
            self.log.info(f"dbt {self.dbt_command} succeeded")
            log.log_stage(stage=f"dbt_{self.dbt_command}", batch_id=batch_id,
                          status="complete", duration_ms=elapsed,
                          message=f"dbt {self.dbt_command} succeeded")
