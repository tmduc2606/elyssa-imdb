"""
Elyssa-IMDb | Silver Export Completion Sensor

Polls for .export.completed / .export.failed markers written by the
detached silver_export_runner.py subprocess (spawned by SilverExportOperator).
"""

import os

from airflow.exceptions import AirflowException
from airflow.sensors.base import BaseSensorOperator


class SilverExportDoneSensor(BaseSensorOperator):

    template_fields = ("output_dir",)

    def __init__(
        self,
        output_dir: str = "/opt/airflow/output/silver/",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.output_dir = output_dir

    def poke(self, context):
        completed = os.path.join(self.output_dir, ".export.completed")
        failed = os.path.join(self.output_dir, ".export.failed")

        if os.path.exists(completed):
            self.log.info("Silver export completed marker found")
            return True

        if os.path.exists(failed):
            raise AirflowException(
                "Silver export failed! Check /opt/airflow/output/tmp/silver_export.log"
            )

        self.log.debug("Silver export still running")
        return False
