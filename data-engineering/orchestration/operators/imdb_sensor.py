"""
IMDb Data Sensor — Airflow sensor for new source data on S3.

Detects new .tsv.gz files in the s3://imdb-source/ bucket via DuckDB httpfs.
Wired as upstream of bronze_ingest in the pipeline DAG.
"""

import os
import sys
from datetime import datetime, timezone
from airflow.sensors.base import BaseSensorOperator

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class IMDbDataSensor(BaseSensorOperator):
    """
    Sensors for new IMDb .tsv.gz files in the s3://imdb-source/ bucket.

    Uses DuckDB httpfs with glob pattern to detect source files.
    Returns True when at least one matching file exists, False otherwise.
    """

    template_fields = ("source_dir", "file_pattern")

    def __init__(
        self,
        source_dir: str = "s3://imdb-source/",
        file_pattern: str = "*.tsv.gz",
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
        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        glob_pattern = os.path.join(self.source_dir, self.file_pattern)

        import duckdb
        conn = duckdb.connect(":memory:")
        sys.path.insert(0, "/opt/airflow/data-engineering")
        try:
            from bronze.s3_config import configure_s3
            configure_s3(conn)
        except Exception:
            pass
        try:
            count = conn.execute(
                f"SELECT count(*) FROM read_csv('{glob_pattern}', delim='\\t', header=true, all_varchar=true, ignore_errors=true)"
            ).fetchone()[0]
        except Exception as e:
            self.log.warning(f"S3 source check failed: {e}")
            conn.close()
            return False
        conn.close()

        if count > 0:
            self.log.info(f"Detected source files at {glob_pattern} ({count} rows accessible)")
            log.log_stage(stage="imdb_sensor", batch_id=batch_id,
                          status="success", row_count=count,
                          message=f"Source files found at {glob_pattern}")
            return True

        self.log.info(f"No source files at {glob_pattern}")
        log.log_stage(stage="imdb_sensor", batch_id=batch_id,
                      status="pending",
                      message=f"No files at {glob_pattern}, will retry")
        return False
