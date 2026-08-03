"""
Elyssa-IMDb | Gold Export Completion Sensor

Polls for .export.completed / .export.failed markers written by the
detached gold_export_runner.py subprocess (spawned by GoldExportOperator).
"""

import os

from airflow.exceptions import AirflowException
from airflow.sensors.base import BaseSensorOperator


class GoldExportDoneSensor(BaseSensorOperator):

    template_fields = ("output_dir",)

    def __init__(
        self,
        output_dir: str = "/opt/airflow/output/gold/",
        *args,
        **kwargs,
    ):
        # Note: the output_dir here is the directory containing the markers and parquet files.
        # The gold export writes parquet + _MANIFEST.json directly into the bind-mounted dir
        # (no tar anymore); we only need to monitor the output dir for markers.
        super().__init__(*args, **kwargs)
        self.output_dir = output_dir

    def poke(self, context):
        completed = os.path.join(self.output_dir, ".export.completed")
        failed = os.path.join(self.output_dir, ".export.failed")

        if os.path.exists(failed):
            raise AirflowException(
                f"Gold export failed! Check {self.output_dir.replace('/output', '/output/tmp')}/gold_export.log"
            )

        if os.path.exists(completed):
            self.log.info("Gold export completed marker found")
            return True

        self.log.debug("Gold export still running")
        return False