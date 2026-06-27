from airflow.models import BaseOperator


class FreshnessCheckOperator(BaseOperator):
    """
    Checks that the most recent ingested_at timestamp in each
    Silver table is within the SLA window.

    Raises AlertFreshnessViolation if any table is stale.
    """

    template_fields = ("jdbc_url",)

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

        # Resolve freshness script path
        freshness_script = "/opt/monitor/freshness.py"
        if not os.path.isfile(freshness_script):
            alt = "/opt/airflow/data-engineering/scripts/freshness.py"
            if os.path.isfile(alt):
                freshness_script = alt

        cmd = [
            "python", freshness_script,
            "--jdbc-url", self.jdbc_url,
            "--jdbc-user", self.jdbc_user,
            "--jdbc-password", self.jdbc_password,
            "--sla-hours", str(self.sla_hours),
        ]
        self.log.info(f"Running freshness check: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"Freshness check failed: {result.stderr}")
            raise RuntimeError(f"Freshness check failed: {result.stderr}")
        self.log.info(f"Freshness check passed: {result.stdout[:500]}")
