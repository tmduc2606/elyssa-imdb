from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults


class DataQualityOperator(BaseOperator):
    """
    Runs data quality checks defined in the DQ config file.

    Queries Silver PostgreSQL for null-rates, referential integrity,
    row-count variance, and logs results to data_quality_log.
    """

    template_fields = ("jdbc_url",)

    @apply_defaults
    def __init__(
        self,
        jdbc_url: str = "",
        jdbc_user: str = "",
        jdbc_password: str = "",
        dq_config_path: str = "/opt/dq/config.yaml",
        dq_script: str = "/opt/dq/run_checks.py",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password
        self.dq_config_path = dq_config_path
        self.dq_script = dq_script

    def execute(self, context):
        import subprocess
        cmd = [
            "python", self.dq_script,
            "--config", self.dq_config_path,
            "--jdbc-url", self.jdbc_url,
            "--jdbc-user", self.jdbc_user,
            "--jdbc-password", self.jdbc_password,
        ]
        self.log.info(f"Running DQ checks: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"DQ checks failed: {result.stderr}")
            raise RuntimeError(f"DQ checks failed: {result.stderr}")
        self.log.info(f"DQ checks passed: {result.stdout[:500]}")
