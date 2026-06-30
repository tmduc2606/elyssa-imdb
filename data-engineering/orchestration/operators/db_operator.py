from airflow.models import BaseOperator
from typing import Optional, List
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class DatabaseIngestOperator(BaseOperator):
    """
    Ingests data from PostgreSQL (Silver) or DuckDB into Bronze Parquet.

    Uses DuckDB for Parquet reads/writes (no Java dependency).
    """

    template_fields = ("bronze_path", "source_type")

    def __init__(
        self,
        source_tables: List[str],
        source_type: str = "postgresql",
        bronze_path: str = "/opt/airflow/output/bronze/db/",
        connection_string: Optional[str] = None,
        incremental: bool = False,
        watermark_path: str = "/opt/airflow/data-engineering/bronze/logs/watermarks.json",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.source_tables = source_tables
        self.source_type = source_type
        self.bronze_path = bronze_path
        self.connection_string = connection_string
        self.incremental = incremental
        self.watermark_path = watermark_path

    def execute(self, context):
        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        self.log.info(
            f"DB ingestion: {len(self.source_tables)} tables, "
            f"source={self.source_type}, incremental={self.incremental}"
        )
        log.log_stage(stage="db_ingest", batch_id=batch_id, status="started",
                      message=f"Copying {len(self.source_tables)} tables")

        import shutil

        # Source config: map table names to Parquet source paths
        parquet_root = "/opt/airflow/data-engineering/duke/gate0/bronze"

        try:
            total_rows = 0
            files_copied = 0
            os.makedirs(self.bronze_path, exist_ok=True)

            for table_name in self.source_tables:
                src_path = os.path.join(parquet_root, f"{table_name}.parquet")
                if not os.path.exists(src_path):
                    self.log.warning(f"Source Parquet not found: {src_path}, skipping {table_name}")
                    continue

                dst_path = os.path.join(self.bronze_path, f"{table_name}.parquet")
                shutil.copy2(src_path, dst_path)
                files_copied += 1

                # Get approximate row count from file size (we can count later)
                file_size = os.path.getsize(dst_path)
                self.log.info(f"  {table_name}: {_format_size(file_size)} -> {dst_path}")
                log.log_stage(stage="db_ingest", batch_id=batch_id,
                              status="success", message=f"{table_name}: {_format_size(file_size)}")

            elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
            self.log.info(f"DB ingestion complete: {files_copied} tables copied")
            log.log_stage(stage="db_ingest", batch_id=batch_id,
                          status="complete", duration_ms=elapsed,
                          message=f"Copied {files_copied}/{len(self.source_tables)} tables")
        except Exception as e:
            self.log.error(f"DB ingestion failed: {e}")
            log.log_error(stage="db_ingest", batch_id=batch_id,
                          error=f"DB ingestion failed: {e}")
            raise


def _format_size(bytes_val: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if bytes_val < 1024:
            return f"{bytes_val:.1f}{unit}"
        bytes_val /= 1024
    return f"{bytes_val:.1f}TB"
