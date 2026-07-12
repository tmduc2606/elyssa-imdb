"""
IMDb Data Sensor — Airflow sensor for new source data.

Detects new .tsv files in the source directory.
Wired as upstream of bronze_ingest in the pipeline DAG.
"""

import os
import glob
from airflow.sensors.base import BaseSensorOperator


class IMDbDataSensor(BaseSensorOperator):
    """
    Sensors for new IMDb .tsv files in the source directory.

    Returns True when at least one .tsv file matching the pattern exists
    and has non-zero size, False otherwise.
    """

    template_fields = ("source_dir", "file_pattern")

    def __init__(
        self,
        source_dir: str = "/opt/airflow/data-engineering/duke/gate0/source/",
        file_pattern: str = "*.tsv",
        poke_interval: int = 300,
        timeout: int = 3600,
        mode: str = "reschedule",
        *args,
        **kwargs,
    ):
        super().__init__(
            poke_interval=poke_interval,
            timeout=timeout,
            mode=mode,
            *args,
            **kwargs,
        )
        self.source_dir = source_dir
        self.file_pattern = file_pattern

    def poke(self, context):
        search_path = os.path.join(self.source_dir, self.file_pattern)
        files = glob.glob(search_path)
        # Filter to non-zero size files
        valid = [f for f in files if os.path.getsize(f) > 0]
        if valid:
            self.log.info(f"Detected {len(valid)} source file(s): {[os.path.basename(f) for f in valid]}")
            ti = context.get("task_instance")
            if ti:
                ti.xcom_push(key="source_files", value=valid)
            return True
        self.log.info(f"No source files found matching {search_path}")
        return False
