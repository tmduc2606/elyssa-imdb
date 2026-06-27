from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults


class FreshnessCheckOperator(BaseOperator):
    """
    Checks that the most recent ingested_at timestamp in each
    Silver table is within the SLA window.

    Raises AlertFreshnessViolation if any table is stale.
    """

    template_fields = ("jdbc_url",)

    @apply_defaults
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
        cmd = [
            "python", "/opt/monitor/freshness.py",
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
