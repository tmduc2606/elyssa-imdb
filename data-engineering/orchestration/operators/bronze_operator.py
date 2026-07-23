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
        source_dir: str = "/opt/airflow/data-engineering/duke/gate0/source/",
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

        conn = duckdb.connect(":memory:")
        conn.execute("SET threads = 2")
        conn.execute("SET memory_limit = '700MB'")
        conn.execute("SET preserve_insertion_order = false")

        # M4: Set DuckDB temp_directory to volume-backed path
        temp_root = "/opt/airflow/output/tmp/"
        if not os.path.exists(temp_root):
            temp_root = "/tmp/"
        duckdb_temp = os.path.join(temp_root, "duckdb_spill")
        os.makedirs(duckdb_temp, exist_ok=True)
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
                file_path = os.path.join(self.source_dir, filename)

                if not os.path.exists(file_path):
                    self.log.warning(f"Source file not found: {file_path}, skipping {table}")
                    continue

                output_path = os.path.join(self.bronze_path, f"{table}.parquet")
                if os.path.exists(output_path):
                    existing_count = conn.execute(f"SELECT COUNT(*) FROM '{output_path}'").fetchone()[0]
                    self.log.info(f"  {table}: CHECKPOINT (already exists at {output_path}, {existing_count} rows)")
                    total_rows += existing_count
                    processed.append({"table": table, "rows": existing_count, "checkpoint": True})
                    continue

                # ── Validate file before processing ────────────────────────
                expected_cols = self.EXPECTED_COLUMNS.get(table)
                if expected_cols is not None:
                    try:
                        sys.path.insert(0, "/opt/airflow/data-engineering")
                        from bronze.quarantine import validate_source_file

                        is_valid, error_msg, row_count = validate_source_file(
                            file_path, table, expected_cols, self.quarantine_root
                        )
                        if not is_valid:
                            self.log.warning(f"QUARANTINE {table}: {error_msg}")
                            quarantined.append({"table": table, "error": error_msg})
                            if pg:
                                with pg.cursor() as cur:
                                    self._quarantine_record(cur, table, file_path, error_msg, batch_id)
                            continue
                    except ImportError:
                        self.log.info("quarantine module not available, skipping validation")
                    except Exception as e:
                        self.log.warning(f"Validation error for {table}: {e}")

                # ── Process valid file ─────────────────────────────────────
                now_ts = datetime.now(timezone.utc).isoformat()

                # ── Compute file checksum for lineage ───────────────────────
                file_checksum = ""
                try:
                    import hashlib
                    sha256 = hashlib.sha256()
                    with open(file_path, "rb") as fh:
                        for chunk in iter(lambda: fh.read(8192), b""):
                            sha256.update(chunk)
                    file_checksum = sha256.hexdigest()
                except Exception:
                    pass

                schema_def = self.BRONZE_SCHEMAS.get(table, {})
                if schema_def:
                    cols_str = ", ".join(f"'{k}': '{v}'" for k, v in schema_def.items())
                    read_csv_sql = f"read_csv(?, columns={{{cols_str}}}, delim='\\t', header=true, null_padding=true, ignore_errors=true, quote='', escape='')"
                else:
                    read_csv_sql = "read_csv(?, delim='\\t', header=true, all_varchar=true, null_padding=true, ignore_errors=true, quote='', escape='')"

                row_count = conn.execute(
                    f"SELECT COUNT(*) FROM {read_csv_sql}",
                    [file_path]
                ).fetchone()[0]

                # Log skip count: compare ingested rows vs file line count
                file_lines = 0
                try:
                    with open(file_path, "r", encoding="utf-8", errors="replace") as _f:
                        for _f_line in _f:
                            file_lines += 1
                    source_rows = max(0, file_lines - 1)  # subtract header
                    skipped = source_rows - row_count
                    if skipped > 0:
                        self.log.warning(f"  {table}: {skipped} rows skipped (malformed/ragged) out of {source_rows} source rows")
                except Exception:
                    pass

                self.log.info(f"  {table}: {row_count} rows (sha256={file_checksum[:12]}...)")

                # Inline file paths in SQL (internal/trusted — avoids ? conflict in COPY subquery)
                fp = file_path.replace("'", "''")
                op = output_path.replace("'", "''")
                copy_sql = read_csv_sql.replace("?", f"'{fp}'")
                conn.execute(
                    f"COPY ("
                    f"  SELECT *, '{fp}' AS _source_file, '{table}' AS _source_table, '{batch_id}' AS _batch_id, '{now_ts}' AS _ingested_at, {row_count} AS _row_count, '{file_checksum}' AS _file_checksum "
                    f"  FROM {copy_sql}"
                    f") TO '{op}' (FORMAT PARQUET, COMPRESSION snappy)"
                )

                total_rows += row_count
                processed.append({"table": table, "rows": row_count})
                self.log.info(f"  {table} written -> {output_path}")
                log.log_stage(stage="bronze_ingest", batch_id=batch_id,
                              status="success", row_count=row_count,
                              message=f"{table} -> {output_path}")

                # ── Persist batch metadata (checksum lineage) ───────────
                if pg:
                    try:
                        meta_cursor = pg.cursor()
                        meta_cursor.execute(
                            """INSERT INTO silver.batch_metadata
                               (batch_id, table_name, source_file, file_checksum, row_count, ingested_at)
                               VALUES (%s, %s, %s, %s, %s, NOW())""",
                            (batch_id, table, file_path, file_checksum, row_count)
                        )
                    except Exception as e:
                        self.log.warning(f"Failed to persist batch metadata for {table}: {e}")

                # Per-table cleanup: flush DuckDB temp to free space between large tables
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
            # M4: Clean up DuckDB temp files
            try:
                import shutil
                if os.path.exists(duckdb_temp):
                    shutil.rmtree(duckdb_temp, ignore_errors=True)
            except Exception as e:
                self.log.warning(f"Failed to clean up DuckDB temp directory: {e}")
            if pg:
                pg.close()