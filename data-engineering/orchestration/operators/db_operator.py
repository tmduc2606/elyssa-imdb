from airflow.models import BaseOperator
from airflow.utils.decorators import apply_defaults
from typing import Optional, List


class DatabaseIngestOperator(BaseOperator):
    """
    Ingests data from PostgreSQL (Silver) or DuckDB into Bronze Parquet.

    Supports full-load and incremental (watermark-based) ingestion.
    Delegates to bronze/db_reader.py and bronze/watermark.py.
    """

    template_fields = ("bronze_path", "source_type")

    @apply_defaults
    def __init__(
        self,
        source_tables: List[str],
        source_type: str = "postgresql",
        bronze_path: str = "/data/bronze/db/",
        connection_string: Optional[str] = None,
        incremental: bool = False,
        watermark_path: str = "/data/bronze/logs/watermarks.json",
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
        self.log.info(
            f"DB ingestion: {len(self.source_tables)} tables, "
            f"source={self.source_type}, incremental={self.incremental}"
        )

        from bronze.db_reader import DatabaseReader, DuckDBReader, DB_SOURCE_TABLES, DUCKDB_PARQUET_SOURCES
        from bronze.watermark import get_watermark, set_watermark, get_latest_watermark_from_df

        if self.source_type == "duckdb":
            tables_config = DUCKDB_PARQUET_SOURCES
            reader = DuckDBReader()
        else:
            tables_config = DB_SOURCE_TABLES
            reader = DatabaseReader()

        try:
            total_rows = 0
            for table_name in self.source_tables:
                table_def = tables_config.get(table_name)
                if not table_def:
                    self.log.warning(f"Unknown table: {table_name}, skipping")
                    continue

                batch_id = f"db_{context['ds_nodash']}_{context['run_id'][:8]}"

                if self.incremental:
                    last_wm = get_watermark(
                        table_def.source_table,
                        path=self.watermark_path,
                    )
                    self.log.info(f"  {table_name}: watermark={last_wm}")
                    df = reader.read_incremental(table_def, last_wm, batch_id)
                else:
                    df = reader.read_table(table_def, batch_id)

                row_count = df.count()
                if row_count > 0:
                    output_path = f"{self.bronze_path}/{table_name}"
                    df \
                        .repartition(1) \
                        .write \
                        .mode("append") \
                        .format("parquet") \
                        .option("compression", "snappy") \
                        .save(output_path)

                    if self.incremental and table_def.watermark_column:
                        new_wm = context.get("ts") or "1970-01-01T00:00:00+00:00"
                        set_watermark(
                            table_def.source_table,
                            str(new_wm),
                            path=self.watermark_path,
                        )

                total_rows += row_count
                self.log.info(f"  {table_name}: {row_count} rows ingested")

            self.log.info(f"DB ingestion complete: {total_rows} total rows")
        finally:
            if self.source_type == "duckdb":
                reader.close()
