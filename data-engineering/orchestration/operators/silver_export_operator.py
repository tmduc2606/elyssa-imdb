"""
Elyssa-IMDb | Silver Export Operator (spawner)

Spawns scripts/silver_export_runner.py as a detached subprocess in a new
session (same pattern as run_bronze / silver ETL). The runner does the
long DuckDB postgres_scanner COPY work OUTSIDE Airflow's supervisor, which
otherwise SIGKILLs any in-process task every 300s orphan-pass cycle.

The task returns immediately; SilverExportDoneSensor polls the
.export.completed / .export.failed markers.
"""

import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from airflow.models import BaseOperator

RUNNER_SCRIPT = "/opt/airflow/data-engineering/scripts/silver_export_runner.py"
LOG_PATH = "/opt/airflow/output/tmp/silver_export.log"


class SilverExportOperator(BaseOperator):
    """
    Spawns the silver parquet export as a detached subprocess.

    The bind mount at /opt/airflow/output/silver/ maps to
    data-science/marts/silver/ on the host, surviving Docker wipes.
    """

    template_fields = ("output_dir",)

    def __init__(
        self,
        pg_host="postgres",
        pg_port=5432,
        pg_db="elyssa_warehouse",
        pg_user="elyssa",
        pg_password_env="GOLD_EXPORT_PG_PASSWORD",
        output_dir="/opt/airflow/output/silver/",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.pg_host = pg_host
        self.pg_port = pg_port
        self.pg_db = pg_db
        self.pg_user = pg_user
        self.pg_password_env = pg_password_env
        self.output_dir = output_dir

    def execute(self, context):
        Path(LOG_PATH).parent.mkdir(parents=True, exist_ok=True)
        with open(LOG_PATH, "w") as lf:
            lf.write(
                f"[{datetime.now(timezone.utc).isoformat()}] "
                f"Spawning silver export runner -> {self.output_dir}\n"
            )
        env = dict(os.environ)
        if not env.get(self.pg_password_env):
            raise ValueError(f"{self.pg_password_env} environment variable is not set")

        cmd = [
            sys.executable,
            RUNNER_SCRIPT,
            "--output-dir",
            self.output_dir,
            "--pg-host",
            self.pg_host,
            "--pg-port",
            str(self.pg_port),
            "--pg-db",
            self.pg_db,
            "--pg-user",
            self.pg_user,
        ]
        proc = subprocess.Popen(
            cmd,
            stdout=open(LOG_PATH, "a"),
            stderr=subprocess.STDOUT,
            start_new_session=True,
            env=env,
        )
        print(f"Silver export subprocess spawned: PID={proc.pid}")
        return {"silver_export_pid": proc.pid}
