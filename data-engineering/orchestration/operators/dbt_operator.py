from airflow.models import BaseOperator
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


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

        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage=f"dbt_{self.dbt_command}", batch_id=batch_id,
                      status="started", message=f"dbt {self.dbt_command} --target {self.dbt_target}")

        # Resolve dbt project path
        project_dir = self.dbt_project_dir
        if not os.path.isdir(project_dir):
            # Fallback for Docker
            alt = f"/opt/airflow/data-engineering/gold"
            if os.path.isdir(alt):
                project_dir = alt

        # Auto-run dbt deps if packages are missing
        packages_dir = os.path.join(project_dir, "dbt_packages")
        packages_yml = os.path.join(project_dir, "packages.yml")
        needs_deps = (
            not os.path.isdir(packages_dir)  # directory missing
            or (os.path.isdir(packages_dir) and not os.listdir(packages_dir))  # empty dir
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
        ]
        self.log.info(f"Running dbt: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True)
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
