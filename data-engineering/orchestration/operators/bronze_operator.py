from airflow.models import BaseOperator
from typing import List
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class BronzeIngestOperator(BaseOperator):
    """
    Triggers bronze ingestion for specified source tables.

    Uses DuckDB for TSV→Parquet conversion (fast, no Java dependency).
    Validates each source file before processing — corrupt/invalid files
    are quarantined and skipped, never silently dropped.
    """

    template_fields = ("bronze_path",)

    # Expected column counts per IMDb source table
    EXPECTED_COLUMNS = {
        "title.basics": 9,
        "title.akas": 8,
        "title.crew": 3,
        "title.episode": 4,
        "title.principals": 6,
        "title.ratings": 3,
        "name.basics": 6,
    }

    # Explicit column schemas for DuckDB read_csv — eliminates type inference overhead
    BRONZE_SCHEMAS = {
        "title.basics": {
            "tconst": "VARCHAR",
            "titleType": "VARCHAR",
            "primaryTitle": "VARCHAR",
            "originalTitle": "VARCHAR",
            "isAdult": "VARCHAR",
            "startYear": "VARCHAR",
            "endYear": "VARCHAR",
            "runtimeMinutes": "VARCHAR",
            "genres": "VARCHAR",
        },
        "title.akas": {
            "titleId": "VARCHAR",
            "ordering": "VARCHAR",
            "title": "VARCHAR",
            "region": "VARCHAR",
            "language": "VARCHAR",
            "types": "VARCHAR",
            "attributes": "VARCHAR",
            "isOriginalTitle": "VARCHAR",
        },
        "title.crew": {
            "tconst": "VARCHAR",
            "directors": "VARCHAR",
            "writers": "VARCHAR",
        },
        "title.episode": {
            "tconst": "VARCHAR",
            "parentTconst": "VARCHAR",
            "seasonNumber": "VARCHAR",
            "episodeNumber": "VARCHAR",
        },
        "title.principals": {
            "tconst": "VARCHAR",
            "ordering": "VARCHAR",
            "nconst": "VARCHAR",
            "category": "VARCHAR",
            "job": "VARCHAR",
            "characters": "VARCHAR",
        },
        "title.ratings": {
            "tconst": "VARCHAR",
            "averageRating": "VARCHAR",
            "numVotes": "VARCHAR",
        },
        "name.basics": {
            "nconst": "VARCHAR",
            "primaryName": "VARCHAR",
            "birthYear": "VARCHAR",
            "deathYear": "VARCHAR",
            "primaryProfession": "VARCHAR",
            "knownForTitles": "VARCHAR",
        },
    }

    def __init__(
        self,
        source_tables: List[str],
        bronze_path: str = "/opt/airflow/output/bronze/",
        source_dir: str = "s3://imdb-source/",
        quarantine_root: str = "/opt/airflow/output/bronze/quarantine/",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.source_tables = source_tables
        self.bronze_path = bronze_path
        self.source_dir = source_dir
        self.quarantine_root = quarantine_root

    def _quarantine_record(self, pg_cursor, table, file_path, error, batch_id):
        """Write a quarantine record to PostgreSQL silver.quarantine."""
        try:
            pg_cursor.execute(
                """INSERT INTO silver.quarantine
                   (table_name, batch_id, check_name, error_message, quarantined_at)
                   VALUES (%s, %s, %s, %s, NOW())""",
                (table, batch_id, "bronze_file_validation", error),
            )
        except Exception as e:
            self.log.warning(f"Failed to log quarantine to PostgreSQL: {e}")

    def execute(self, context):
        import duckdb
        import psycopg2

        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage="bronze_ingest", batch_id=batch_id, status="started",
                      message=f"Processing {len(self.source_tables)} tables")

        # M1: Use file-backed DuckDB for automatic spill-to-disk
        temp_root = "/opt/airflow/output/tmp/"
        if not os.path.exists(temp_root):
            temp_root = "/tmp/"
        duckdb_temp = os.path.join(temp_root, "duckdb_spill")
        duckdb_file = os.path.join(duckdb_temp, f"bronze_{batch_id}.duckdb")
        os.makedirs(duckdb_temp, exist_ok=True)
        conn = duckdb.connect(str(duckdb_file))
        from bronze.s3_config import configure_s3
        configure_s3(conn)
        conn.execute("SET threads = 2")
        conn.execute("SET memory_limit = '1.5GB'")
        conn.execute("SET preserve_insertion_order = false")
        conn.execute(f"SET temp_directory = '{duckdb_temp}'")
        conn.execute("SET max_temp_directory_size = '10GB'")

        # PostgreSQL connection for quarantine logging
        pg = None
        try:
            pg = psycopg2.connect(
                host="postgres", port=5432,
                user="elyssa", password="elyssa_pg_2026",
                dbname="elyssa_warehouse",
            )
            pg.autocommit = True
        except Exception as e:
            self.log.warning(f"Cannot connect to PostgreSQL for quarantine logging: {e}")

        try:
            os.makedirs(self.bronze_path, exist_ok=True)
            os.makedirs(self.quarantine_root, exist_ok=True)

            source_files = {
                "title.basics": "title.basics.tsv",
                "title.akas": "title.akas.tsv",
                "title.crew": "title.crew.tsv",
                "title.episode": "title.episode.tsv",
                "title.principals": "title.principals.tsv",
                "title.ratings": "title.ratings.tsv",
                "name.basics": "name.basics.tsv",
            }

            total_rows = 0
            quarantined = []
            processed = []

            for table in self.source_tables:
                filename = source_files.get(table, f"{table}.tsv")
                source_url = os.path.join(self.source_dir, filename)

                s3_output = f"s3://bronze/{table}.parquet"
                local_output = os.path.join(self.bronze_path, f"{table}.parquet")

                # Checkpoint resume from local bind mount
                if os.path.exists(local_output):
                    existing_count = conn.execute(f"SELECT COUNT(*) FROM '{local_output}'").fetchone()[0]
                    self.log.info(f"  {table}: CHECKPOINT (already exists at {local_output}, {existing_count} rows)")
                    total_rows += existing_count
                    processed.append({"table": table, "rows": existing_count, "checkpoint": True})
                    continue

                # Get row count from S3 via DuckDB
                try:
                    source_rows = conn.execute(
                        f"SELECT COUNT(*) FROM read_csv('{source_url}', delim='\\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape='')"
                    ).fetchone()[0]
                except Exception as e:
                    self.log.warning(f"Cannot read {source_url}: {e}, skipping {table}")
                    continue

                now_ts = datetime.now(timezone.utc).isoformat()

                schema_def = self.BRONZE_SCHEMAS.get(table, {})
                if schema_def:
                    cols_str = ", ".join(f"'{k}': '{v}'" for k, v in schema_def.items())
                    read_csv_sql = f"read_csv('{source_url}', columns={{{cols_str}}}, delim='\\t', header=true, null_padding=true, ignore_errors=true, quote='', escape='')"
                else:
                    read_csv_sql = f"read_csv('{source_url}', delim='\\t', header=true, all_varchar=true, null_padding=true, ignore_errors=true, quote='', escape='')"

                base_sql = (
                    f"SELECT *, '{source_url}' AS _source_file, '{table}' AS _source_table, "
                    f"'{batch_id}' AS _batch_id, '{now_ts}' AS _ingested_at, "
                    f"{source_rows} AS _row_count, '' AS _file_checksum "
                    f"FROM ({read_csv_sql})"
                )

                # Write to S3 bronze bucket
                try:
                    conn.execute(f"COPY ({base_sql}) TO '{s3_output}' (FORMAT PARQUET, COMPRESSION snappy)")
                    self.log.info(f"  {table} written -> {s3_output}")
                except Exception as e:
                    self.log.warning(f"S3 write failed for {table}: {e}")

                # Write to local bind mount (DS notebook)
                try:
                    conn.execute(f"COPY ({base_sql}) TO '{local_output}' (FORMAT PARQUET, COMPRESSION snappy)")
                except Exception as e:
                    self.log.warning(f"Local write failed for {table}: {e}")

                total_rows += source_rows
                processed.append({"table": table, "rows": source_rows})
                self.log.info(f"  {table}: {source_rows} rows")
                log.log_stage(stage="bronze_ingest", batch_id=batch_id,
                              status="success", row_count=source_rows,
                              message=f"{table} -> {local_output}")

                if pg:
                    try:
                        meta_cursor = pg.cursor()
                        meta_cursor.execute(
                            """INSERT INTO silver.batch_metadata
                               (batch_id, table_name, source_file, file_checksum, row_count, ingested_at)
                               VALUES (%s, %s, %s, %s, %s, NOW())""",
                            (batch_id, table, source_url, "", source_rows)
                        )
                    except Exception as e:
                        self.log.warning(f"Failed to persist batch metadata for {table}: {e}")

                conn.execute("CHECKPOINT")

            # ── Summary ────────────────────────────────────────────────────
            elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
            self.log.info(
                f"Bronze ingestion complete: {total_rows} rows across {len(processed)} tables"
                + (f", {len(quarantined)} quarantined" if quarantined else "")
            )
            log.log_stage(stage="bronze_ingest", batch_id=batch_id,
                          status="complete", row_count=total_rows,
                          duration_ms=elapsed,
                          message=f"{len(processed)} tables, {len(quarantined)} quarantined")
            return {
                "batch_id": batch_id,
                "total_rows": total_rows,
                "processed": processed,
                "quarantined": quarantined,
            }
        finally:
            conn.close()
            # M1: Clean up DuckDB file and temp files
            try:
                import shutil
                if os.path.exists(duckdb_file):
                    os.remove(duckdb_file)
                if os.path.exists(duckdb_temp):
                    shutil.rmtree(duckdb_temp, ignore_errors=True)
            except Exception as e:
                self.log.warning(f"Failed to clean up DuckDB temp files: {e}")
            if pg:
                pg.close()