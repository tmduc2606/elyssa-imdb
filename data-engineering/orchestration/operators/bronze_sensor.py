"""
Elyssa-IMDb | Bronze Completion Sensor
Polls for .completed / .failed markers written by run_bronze.py.
"""

import os
from airflow.sensors.base import BaseSensorOperator
from airflow.exceptions import AirflowException


class BronzeCompletionSensor(BaseSensorOperator):

    template_fields = ("bronze_dir",)

    def __init__(
        self,
        bronze_dir: str = "/opt/airflow/output/bronze/",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.bronze_dir = bronze_dir

    def poke(self, context):
        completed = os.path.join(self.bronze_dir, ".completed")
        failed = os.path.join(self.bronze_dir, ".failed")
        running = os.path.join(self.bronze_dir, ".running")

        if os.path.exists(completed):
            self.log.info("Bronze completed marker found")
            return True

        if os.path.exists(failed):
            raise AirflowException("Bronze ingestion failed! Check run_bronze.py logs.")

        if os.path.exists(running):
            self.log.debug("Bronze still running (marker found)")
        else:
            self.log.debug("No bronze markers yet")

        return False