"""
IMDb Data Sensor — Airflow sensor for new source data on S3.

Detects new .tsv.gz files in the s3://imdb-source/ bucket via boto3
list_objects_v2 (zero data transfer, no OOM risk).
Wired as upstream of bronze_ingest in the pipeline DAG.
"""

import os
import re
import sys
from datetime import datetime, timezone

import boto3
from airflow.sensors.base import BaseSensorOperator
from botocore.config import Config

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://rustfs:9000").rstrip("/")
# Access key is a username (non-secret); the secret key MUST come from the
# environment (docker/.env via compose) — no hardcoded fallback (C1-C7).
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "elyssa")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "")

_s3_client = None


def _get_s3_client():
    global _s3_client
    if not S3_SECRET_KEY:
        raise ValueError(
            "S3_SECRET_KEY is not set in the environment (docker/.env via compose)"
        )
    if _s3_client is None:
        _s3_client = boto3.client(
            "s3",
            endpoint_url=S3_ENDPOINT,
            aws_access_key_id=S3_ACCESS_KEY,
            aws_secret_access_key=S3_SECRET_KEY,
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
    return _s3_client


class IMDbDataSensor(BaseSensorOperator):
    """
    Sensor for new IMDb .tsv.gz files in the s3://imdb-source/ bucket.

    Lists objects via boto3 (metadata only, no data transfer).
    """

    template_fields = ("source_dir", "file_pattern")

    EXPECTED = 7

    def __init__(
        self,
        source_dir: str = "s3://imdb-source/",
        file_pattern: str = r"\.tsv\.gz$",
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
        self._bucket = source_dir.replace("s3://", "").rstrip("/")

    def poke(self, context):
        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

        try:
            resp = _get_s3_client().list_objects_v2(Bucket=self._bucket)
        except Exception as e:
            self.log.warning(f"S3 list failed: {e}")
            return False

        keys = resp.get("Contents", [])
        matched = [k for k in keys if re.search(self.file_pattern, k["Key"])]
        count = len(matched)

        if count >= self.EXPECTED:
            self.log.info(
                f"Detected {count}/{self.EXPECTED} source files in s3://{self._bucket}/"
            )
            log.log_stage(
                stage="imdb_sensor", batch_id=batch_id,
                status="success", row_count=count,
                message=f"Source files found: {count}/{self.EXPECTED}",
            )
            return True

        self.log.info(
            f"Waiting for source files: {count}/{self.EXPECTED} in s3://{self._bucket}/"
        )
        log.log_stage(
            stage="imdb_sensor", batch_id=batch_id,
            status="pending", row_count=count,
            message=f"Files: {count}/{self.EXPECTED}",
        )
        return False
