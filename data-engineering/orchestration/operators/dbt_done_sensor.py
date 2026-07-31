"""
Elyssa-IMDb | DBT Completion Sensor

Polls for .dbt.{suffix}.completed / .dbt.{suffix}.failed markers written by
the detached dbt_runner.py subprocess (spawned by DbtRunOperator).
"""

import os

from airflow.exceptions import AirflowException
from airflow.sensors.base import BaseSensorOperator


class DbtDoneSensor(BaseSensorOperator):
    """
    Waits for a dbt command (run or test) to finish by checking for
    completion markers in the dbt project directory.

    :param project_dir: Path to the dbt project (containing the .dbt.* markers)
    :param suffix: Either "run" or "test" to indicate which dbt command to wait for
    """

    template_fields = ("project_dir", "suffix")

    def __init__(
        self,
        project_dir: str,
        suffix: str,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.project_dir = project_dir
        self.suffix = suffix

    def poke(self, context):
        completed = os.path.join(self.project_dir, f".dbt.{self.suffix}.completed")
        failed = os.path.join(self.project_dir, f".dbt.{self.suffix}.failed")

        if os.path.exists(failed):
            raise AirflowException(
                f"DBT {self.suffix} failed! Check {self.project_dir}/dbt_{self.suffix}.log"
            )

        if os.path.exists(completed):
            self.log.info(f"DBT {self.suffix} completed marker found")
            return True

        self.log.debug(f"DBT {self.suffix} still running")
        return False