"""
IMDb Data Sensor — Airflow FileSensor for new source data.

Monitors the source directory for new .tsv.gz files.
Replaces clock-based scheduling with data-driven triggers.
"""

import os
import glob
from typing import Optional


class DataFileSensor:
    """
    Lightweight file sensor that checks for new data files.

    For local filesystem: uses glob pattern matching on .tsv.gz files.
    For S3/RustFS: would use boto3 with prefix listing (production mode).

    Returns True when files matching the pattern exist, False otherwise.
    """

    def __init__(
        self,
        source_dir: str,
        file_pattern: str = "*.tsv.gz",
        poke_interval: int = 300,
        timeout: int = 3600,
    ):
        self.source_dir = source_dir
        self.file_pattern = file_pattern
        self.poke_interval = poke_interval
        self.timeout = timeout

    def poke(self) -> bool:
        """Check if any new data files exist in the source directory."""
        search_path = os.path.join(self.source_dir, self.file_pattern)
        files = glob.glob(search_path)
        return len(files) > 0

    def get_new_files(self) -> list[str]:
        """Return list of matching file paths."""
        search_path = os.path.join(self.source_dir, self.file_pattern)
        return glob.glob(search_path)


def create_airflow_file_sensor_tasks(dag, source_dir: str = "/data/source/imdb/"):
    """
    Create Airflow FileSensor tasks for the pipeline.

    Returns a list of sensor tasks that can be wired as upstream
    of bronze_ingest.
    """
    try:
        from airflow.sensors.filesystem import FileSensor
        sensor = FileSensor(
            task_id="imdb_data_sensor",
            filepath=os.path.join(source_dir, "*.tsv.gz"),
            fs_conn_id="fs_default",
            poke_interval=300,
            timeout=3600,
            mode="reschedule",
        )
        return [sensor]
    except ImportError:
        # Airflow not installed — return empty list (will be retried at runtime)
        return []


if __name__ == "__main__":
    sensor = DataFileSensor("/data/source/imdb/")
    if sensor.poke():
        print(f"[Sensor] New files detected: {sensor.get_new_files()}")
    else:
        print("[Sensor] No new files. Waiting...")
