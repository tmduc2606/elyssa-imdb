"""
Backup Operator — pg_dump to RustFS/S3.

Wraps pg_dump to create scheduled backups of the Silver/Gold
PostgreSQL database, uploading the dump to S3-compatible storage.
"""

from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import Optional
import subprocess
import os
from datetime import datetime


class BackupOperator(BaseOperator):
    """
    Runs pg_dump and uploads the backup to S3-compatible storage.

    Uses pg_dump with custom format (compressed) and uploads
    to a configured S3 bucket via aws-cli or boto3.
    """

    template_fields = ("s3_bucket", "s3_prefix")

    @apply_defaults
    def __init__(
        self,
        postgres_host: str = "postgres",
        postgres_port: int = 5432,
        postgres_user: str = "elyssa",
        postgres_password: str = "elyssa_pg_2026",
        postgres_db: str = "elyssa_warehouse",
        s3_bucket: str = "elyssa-backups",
        s3_prefix: str = "pgdump/",
        s3_endpoint: str = "http://rustfs:9000",
        backup_format: str = "c",  # custom (compressed) format
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.postgres_host = postgres_host
        self.postgres_port = postgres_port
        self.postgres_user = postgres_user
        self.postgres_password = postgres_password
        self.postgres_db = postgres_db
        self.s3_bucket = s3_bucket
        self.s3_prefix = s3_prefix
        self.s3_endpoint = s3_endpoint
        self.backup_format = backup_format

    def execute(self, context):
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = f"/tmp/elyssa_backup_{timestamp}.dump"
        s3_key = f"{self.s3_prefix}elyssa_backup_{timestamp}.dump"

        # ─── Run pg_dump ──────────────────────────────────────────────
        env = os.environ.copy()
        env["PGPASSWORD"] = self.postgres_password

        cmd = [
            "pg_dump",
            "--host", self.postgres_host,
            "--port", str(self.postgres_port),
            "--username", self.postgres_user,
            "--dbname", self.postgres_db,
            "--format", self.backup_format,
            "--file", backup_file,
            "--verbose",
        ]

        self.log.info(f"Running pg_dump: {' '.join(cmd)}")
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)

        if result.returncode != 0:
            self.log.error(f"pg_dump failed: {result.stderr}")
            if os.path.exists(backup_file):
                os.remove(backup_file)
            raise RuntimeError(f"pg_dump failed: {result.stderr}")

        self.log.info(f"pg_dump complete: {result.stdout[:200]}")

        # ─── Upload to S3 ────────────────────────────────────────────
        upload_cmd = [
            "aws", "s3", "cp", backup_file,
            f"s3://{self.s3_bucket}/{s3_key}",
            "--endpoint-url", self.s3_endpoint,
        ]

        self.log.info(f"Uploading to s3://{self.s3_bucket}/{s3_key}")
        upload_result = subprocess.run(upload_cmd, capture_output=True, text=True)

        # Clean up local file regardless of upload result
        if os.path.exists(backup_file):
            os.remove(backup_file)

        if upload_result.returncode != 0:
            self.log.error(f"S3 upload failed: {upload_result.stderr}")
            raise RuntimeError(f"S3 upload failed: {upload_result.stderr}")

        self.log.info(f"Backup uploaded: s3://{self.s3_bucket}/{s3_key}")
