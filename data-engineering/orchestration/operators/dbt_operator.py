from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults


class DbtRunOperator(BaseOperator):
    """
    Executes a dbt command (run, test, etc.) for the Gold layer.

    Runs inside the dbt container via DockerOperator or subprocess.
    """

    template_fields = ("dbt_project_dir",)

    @apply_defaults
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

    def execute(self, context):
        import subprocess
        cmd = [
            "dbt",
            self.dbt_command,
            "--project-dir", self.dbt_project_dir,
            "--target", self.dbt_target,
        ]
        self.log.info(f"Running dbt: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"dbt {self.dbt_command} failed: {result.stderr}")
            raise RuntimeError(f"dbt {self.dbt_command} failed: {result.stderr}")
        self.log.info(f"dbt {self.dbt_command} succeeded")
