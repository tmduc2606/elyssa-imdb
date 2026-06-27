from airflow.models import BaseOperator


class DbtRunOperator(BaseOperator):
    """
    Executes a dbt command (run, test, etc.) for the Gold layer.

    Runs inside the dbt container via DockerOperator or subprocess.
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

    def execute(self, context):
        import subprocess
        import os

        # Resolve dbt project path
        project_dir = self.dbt_project_dir
        if not os.path.isdir(project_dir):
            # Fallback for Docker
            alt = f"/opt/airflow/data-engineering/gold"
            if os.path.isdir(alt):
                project_dir = alt

        cmd = [
            "dbt",
            self.dbt_command,
            "--project-dir", project_dir,
            "--target", self.dbt_target,
        ]
        self.log.info(f"Running dbt: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            self.log.error(f"dbt {self.dbt_command} failed: {result.stderr}")
            raise RuntimeError(f"dbt {self.dbt_command} failed: {result.stderr}")
        self.log.info(f"dbt {self.dbt_command} succeeded")
