from airflow.models import BaseOperator
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class FreshnessCheckOperator(BaseOperator):
    """
    Checks that the most recent ingested_at timestamp in each
    Silver table is within the SLA window.

    Raises AlertFreshnessViolation if any table is stale.
    """

    template_fields = ("jdbc_url",)

    @staticmethod
    def _resolve_reference_time(context):
        """Resolve the run's reference (logical) time from the most reliable source.

        Airflow 3.3.0 stores logical_date/data_interval_start as NULL for
        CLI-triggered manual runs (observed on 5/5 runs), so context dates
        cannot be trusted on their own. Resolution order:
          1. dag_run.data_interval_start  (scheduled runs, canonical)
          2. dag_run.logical_date         (if populated)
          3. run_id suffix for manual__ runs (trigger timestamp; most
             reliable for CLI-triggered runs)
          4. dag_run.run_after            (queue time; always populated)
          5. dag_run.start_date           (when the scheduler adopted it)
          6. wall-clock now               (last resort, never silent)
        Returns (datetime, source_label) so the caller can log provenance.
        """
        run = context.get("dag_run")
        if run is not None:
            for attr in ("data_interval_start", "logical_date", "run_after", "start_date"):
                value = getattr(run, attr, None)
                if value is not None:
                    return value, attr
        run_id = context.get("run_id")
        if run_id is None and run is not None:
            run_id = getattr(run, "run_id", None)
        if run_id and run_id.startswith("manual__"):
            try:
                return datetime.fromisoformat(run_id.split("manual__", 1)[1]), "run_id"
            except ValueError:
                pass
        return datetime.now(timezone.utc), "wall-clock"

    def __init__(
        self,
        jdbc_url: str = "",
        jdbc_user: str = "",
        jdbc_password: str = "",
        sla_hours: int = 24,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password
        self.sla_hours = sla_hours

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

        log.log_stage(stage="freshness_check", batch_id=batch_id, status="started",
                      message=f"SLA threshold: {self.sla_hours}h")

        freshness_script = "/opt/airflow/data-engineering/scripts/freshness.py"
        if not os.path.isfile(freshness_script):
            alt = "/opt/airflow/scripts/freshness.py"
            if os.path.isfile(alt):
                freshness_script = alt

        ref_ts, ref_source = self._resolve_reference_time(context)
        self.log.info(f"Reference time resolved from {ref_source}: {ref_ts.isoformat()}")

        cmd = [
            "python", freshness_script,
            "--jdbc-url", self.jdbc_url,
            "--jdbc-user", self.jdbc_user,
            "--jdbc-password", self.jdbc_password,
            "--sla-hours", str(self.sla_hours),
            "--reference-time", ref_ts.isoformat(),
        ]
        self.log.info(f"Running freshness check: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
        if result.returncode != 0:
            self.log.error(f"Freshness check failed: {result.stderr}")
            log.log_error(stage="freshness_check", batch_id=batch_id,
                          error=f"Freshness SLA violation: {result.stderr[-500:]}")
            raise RuntimeError(f"Freshness check failed: {result.stderr}")
        self.log.info(f"Freshness check passed: {result.stdout[:500]}")
        log.log_stage(stage="freshness_check", batch_id=batch_id,
                      status="complete", duration_ms=elapsed,
                      message="Freshness SLA met")
