from airflow.models import BaseOperator
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class DataQualityOperator(BaseOperator):
    """
    Runs data quality checks defined in the DQ config file.

    Queries Silver PostgreSQL for null-rates, referential integrity,
    row-count variance, and logs results to data_quality_log.
    """

    template_fields = ("jdbc_url",)

    def __init__(
        self,
        jdbc_url: str = "",
        jdbc_user: str = "",
        jdbc_password: str = "",
        dq_config_path: str = "/opt/airflow/data-engineering/dq/config.yaml",
        dq_script: str = "/opt/airflow/data-engineering/dq/run_checks.py",
        run_gx: bool = False,
        gx_script: str = "/opt/airflow/data-engineering/dq/great_expectations/bronze_suite.py",
        bronze_path: str = "/opt/airflow/output/bronze/",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password
        self.dq_config_path = dq_config_path
        self.dq_script = dq_script
        self.run_gx = run_gx
        self.gx_script = gx_script
        self.bronze_path = bronze_path

    def execute(self, context):
        import subprocess
        import os

        # C1-C7: resolve credentials from env/Airflow Connections when not
        # explicitly passed by the caller (never hardcoded).
        import sys as _sys
        _sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
        from config.secrets import pg_user, pg_password, pg_host, pg_port, pg_db
        self.jdbc_user = self.jdbc_user or pg_user()
        self.jdbc_password = self.jdbc_password or pg_password()
        self.jdbc_url = self.jdbc_url or (
            f"postgresql://{self.jdbc_user}:{self.jdbc_password}@{pg_host()}:{pg_port()}/{pg_db()}"
        )

        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage="dq_checks", batch_id=batch_id, status="started",
                      message="Running data quality checks")

        # Resolve DQ script path
        dq_script = self.dq_script
        if not os.path.isfile(dq_script):
            alt = "/opt/airflow/data-engineering/dq/run_checks.py"
            if os.path.isfile(alt):
                dq_script = alt

        config_path = self.dq_config_path
        if not os.path.isfile(config_path):
            alt = "/opt/airflow/data-engineering/dq/config.yaml"
            if os.path.isfile(alt):
                config_path = alt

        cmd = [
            "python", dq_script,
            "--config", config_path,
            "--jdbc-url", self.jdbc_url,
            "--jdbc-user", self.jdbc_user,
            "--jdbc-password", self.jdbc_password,
        ]
        self.log.info(f"Running DQ checks: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
        if result.returncode != 0:
            self.log.error(f"DQ checks failed: {result.stderr}")
            log.log_error(stage="dq_checks", batch_id=batch_id,
                          error=f"DQ checks failed: {result.stderr[-500:]}")
            raise RuntimeError(f"DQ checks failed: {result.stderr}")
        self.log.info(f"DQ checks passed: {result.stdout[:500]}")
        log.log_stage(stage="dq_checks", batch_id=batch_id,
                      status="complete", duration_ms=elapsed,
                      message="All data quality checks passed")

        # ── Optional: Great Expectations validation ─────────────────────────
        if self.run_gx:
            gx_start = datetime.now(timezone.utc)
            log.log_stage(stage="gx_validation", batch_id=batch_id, status="started",
                          message="Running Great Expectations Bronze validation")

            gx_script = self.gx_script
            if not os.path.isfile(gx_script):
                alt = "/opt/airflow/data-engineering/dq/great_expectations/bronze_suite.py"
                if os.path.isfile(alt):
                    gx_script = alt

            gx_cmd = ["python", gx_script, self.bronze_path]
            self.log.info(f"Running GX: {' '.join(gx_cmd)}")
            gx_result = subprocess.run(gx_cmd, capture_output=True, text=True)
            gx_elapsed = int((datetime.now(timezone.utc) - gx_start).total_seconds() * 1000)
            if gx_result.returncode != 0:
                self.log.warning(f"GX validation failed (non-fatal): {gx_result.stderr[:300]}")
                log.log_stage(stage="gx_validation", batch_id=batch_id,
                              status="warning", duration_ms=gx_elapsed,
                              message=f"GX issues: {gx_result.stderr[:200]}")
            else:
                self.log.info("GX validation passed")
                log.log_stage(stage="gx_validation", batch_id=batch_id,
                              status="complete", duration_ms=gx_elapsed,
                              message="All GX expectations passed")
