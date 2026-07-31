"""
Elyssa-IMDb | Standalone Bronze Ingestion (S3-Centric)
Runs all 7 bronze tables via DuckDB, outside Airflow's supervisor.
Reads TSV from s3://imdb-source/, writes Parquet to s3://bronze/
and to local bind mount /opt/airflow/output/bronze/ for DS notebook.
"""

import os
import sys
import hashlib
import shutil
import time
import json
from datetime import datetime, timezone

BRONZE_PATH = "/opt/airflow/output/bronze/"
S3_BRONZE_PATH = "s3://bronze/"
SOURCE_DIR = "s3://imdb-source/"
QUARANTINE_ROOT = "/opt/airflow/output/bronze/quarantine/"
DUCKDB_TEMP_ROOT = "/opt/airflow/output/tmp/"
BATCH_METADATA_FILE = os.path.join(BRONZE_PATH, ".batch_metadata.json")

STATUS_RUNNING = os.path.join(BRONZE_PATH, ".running")
STATUS_COMPLETED = os.path.join(BRONZE_PATH, ".completed")
STATUS_FAILED = os.path.join(BRONZE_PATH, ".failed")
PID_FILE = os.path.join(BRONZE_PATH, ".bronze_pid")

BRONZE_SCHEMAS = {
    "title.basics": {
        "tconst": "VARCHAR", "titleType": "VARCHAR", "primaryTitle": "VARCHAR",
        "originalTitle": "VARCHAR", "isAdult": "VARCHAR", "startYear": "VARCHAR",
        "endYear": "VARCHAR", "runtimeMinutes": "VARCHAR", "genres": "VARCHAR",
    },
    "title.akas": {
        "titleId": "VARCHAR", "ordering": "VARCHAR", "title": "VARCHAR",
        "region": "VARCHAR", "language": "VARCHAR", "types": "VARCHAR",
        "attributes": "VARCHAR", "isOriginalTitle": "VARCHAR",
    },
    "title.crew": {"tconst": "VARCHAR", "directors": "VARCHAR", "writers": "VARCHAR"},
    "title.episode": {"tconst": "VARCHAR", "parentTconst": "VARCHAR", "seasonNumber": "VARCHAR", "episodeNumber": "VARCHAR"},
    "title.principals": {"tconst": "VARCHAR", "ordering": "VARCHAR", "nconst": "VARCHAR", "category": "VARCHAR", "job": "VARCHAR", "characters": "VARCHAR"},
    "title.ratings": {"tconst": "VARCHAR", "averageRating": "VARCHAR", "numVotes": "VARCHAR"},
    "name.basics": {"nconst": "VARCHAR", "primaryName": "VARCHAR", "birthYear": "VARCHAR", "deathYear": "VARCHAR", "primaryProfession": "VARCHAR", "knownForTitles": "VARCHAR"},
}

SOURCE_FILES = {
    "title.basics": "title.basics.tsv.gz",
    "title.akas": "title.akas.tsv.gz",
    "title.crew": "title.crew.tsv.gz",
    "title.episode": "title.episode.tsv.gz",
    "title.principals": "title.principals.tsv.gz",
    "title.ratings": "title.ratings.tsv.gz",
    "name.basics": "name.basics.tsv.gz",
}

BRONZE_TABLES = [
    "title.basics",
    "title.akas",
    "title.crew",
    "title.episode",
    "title.principals",
    "title.ratings",
    "name.basics",
]


def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)


def write_pid():
    os.makedirs(BRONZE_PATH, exist_ok=True)
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def write_status(marker: str):
    for m in [STATUS_RUNNING, STATUS_COMPLETED, STATUS_FAILED]:
        if os.path.exists(m):
            os.remove(m)
    with open(marker, "w") as f:
        f.write(datetime.now(timezone.utc).isoformat())


def quarantine_record(pg_cursor, table, file_path, error, batch_id):
    try:
        pg_cursor.execute(
            """INSERT INTO silver.quarantine
               (table_name, batch_id, check_name, error_message, quarantined_at)
               VALUES (%s, %s, %s, %s, NOW())""",
            (table, batch_id, "bronze_file_validation", error),
        )
    except Exception as e:
        log(f"  [WARN] Failed to log quarantine to PostgreSQL: {e}")


def _s3_object_exists(bucket: str, key: str) -> bool:
    """Cheap metadata-only check whether an object exists in RustFS."""
    try:
        import boto3
        from botocore.config import Config
        endpoint = os.environ.get("S3_ENDPOINT", "http://rustfs:9000").rstrip("/")
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=os.environ.get("S3_ACCESS_KEY", "elyssa"),
            aws_secret_access_key=os.environ.get("S3_SECRET_KEY", "elyssa_s3_2026"),
            config=Config(signature_version="s3v4"),
            region_name="us-east-1",
        )
        client.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def ingest_table(conn, table, batch_id, pg):
    filename = SOURCE_FILES.get(table, f"{table}.tsv.gz")
    source_url = f"{SOURCE_DIR}{filename}"
    s3_output = f"{S3_BRONZE_PATH}{table}.parquet"
    local_output = os.path.join(BRONZE_PATH, f"{table}.parquet")
    marker_path = os.path.join(BRONZE_PATH, f".{table}.completed")

    # Checkpoint resume from marker file (avoids loading full Parquet for count)
    # S3 copy is validated too: RustFS stores data container-locally, so a
    # Docker cleanup can wipe s3://bronze/ while the bind-mounted local copy
    # and marker survive. If the S3 object is missing, re-ingest both copies.
    if os.path.exists(marker_path) and os.path.exists(local_output):
        if _s3_object_exists("bronze", f"{table}.parquet"):
            try:
                with open(marker_path, "r") as f:
                    marker = json.load(f)
                existing_count = marker.get("rows", 0)
                # Verify the S3 parquet row count matches the marker. A marker
                # can be written with the correct source count while the actual
                # Parquet artifact is incomplete (e.g. read_csv quote handling
                # silently dropping rows) — head_object existence alone is not
                # enough. Any mismatch forces a re-ingest.
                try:
                    s3_rows = conn.execute(
                        f"SELECT COUNT(*) FROM read_parquet('{s3_output}')"
                    ).fetchone()[0]
                    local_rows = conn.execute(
                        f"SELECT COUNT(*) FROM read_parquet('{local_output}')"
                    ).fetchone()[0]
                except Exception as e:
                    log(f"  CHECKPOINT {table}: cannot verify row counts ({e}) — re-ingesting")
                    s3_rows = local_rows = -1
                if s3_rows == existing_count and local_rows == existing_count:
                    log(f"  CHECKPOINT {table}: {existing_count} rows already processed (marker + S3 verified)")
                    return {"table": table, "rows": existing_count, "checkpoint": True}
                log(f"  CHECKPOINT {table}: row-count mismatch — S3={s3_rows:,} local={local_rows:,} vs marker={existing_count:,} — re-ingesting")
            except Exception:
                pass  # Fall through to reprocess if marker is corrupt
        else:
            log(f"  CHECKPOINT {table}: local copy found but s3://bronze/{table}.parquet is MISSING — re-ingesting")

    # Row count via DuckDB from S3 (fast range request — no full download)
    try:
        source_rows = conn.execute(
            f"SELECT COUNT(*) FROM read_csv('{source_url}', delim='\\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape='')"
        ).fetchone()[0]
    except Exception as e:
        log(f"  SKIP {table}: cannot read from {source_url}: {e}")
        return {"table": table, "rows": 0, "skipped": True, "error": str(e)}

    now_ts = datetime.now(timezone.utc).isoformat()

    schema_def = BRONZE_SCHEMAS.get(table, {})
    if schema_def:
        cols_str = ", ".join(f"'{k}': '{v}'" for k, v in schema_def.items())
        # quote='' escape='' is critical: IMDb TSV fields contain literal "
        # (e.g. '"Rome brûle" (Portrait de Shirley Clarke)'). With the default
        # quote handling, such rows mis-parse and ignore_errors=true silently
        # DROPS them (82% loss observed on title.basics). Reading line-based
        # preserves every row.
        read_csv_sql = f"read_csv('{source_url}', columns={{{cols_str}}}, delim='\\t', header=true, null_padding=true, ignore_errors=true, quote='', escape='')"
    else:
        read_csv_sql = f"read_csv('{source_url}', delim='\\t', header=true, all_varchar=true, null_padding=true, ignore_errors=true, quote='', escape='')"

    base_sql = (
        f"SELECT *, '{source_url}' AS _source_file, '{table}' AS _source_table, "
        f"'{batch_id}' AS _batch_id, '{now_ts}' AS _ingested_at, "
        f"{source_rows} AS _row_count, '' AS _file_checksum "
        f"FROM {read_csv_sql}"
    )

    # Stream directly to Parquet without materializing a temp table
    # Write to S3 bronze bucket (pipeline hot path)
    try:
        conn.execute(
            f"COPY ({base_sql}) TO '{s3_output}' (FORMAT PARQUET, COMPRESSION snappy)"
        )
        log(f"  {table} written -> {s3_output}")
    except Exception as e:
        log(f"  [WARN] S3 write failed for {table}: {e}")

    # Write to local bind mount (DS notebook consumption)
    try:
        conn.execute(
            f"COPY ({base_sql}) TO '{local_output}' (FORMAT PARQUET, COMPRESSION snappy)"
        )
        log(f"  {table} written -> {local_output}")
    except Exception as e:
        log(f"  [WARN] Local write failed for {table}: {e}")

    # Compute checksum from local Parquet for lineage
    file_checksum = ""
    try:
        sha256 = hashlib.sha256()
        with open(local_output, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha256.update(chunk)
        file_checksum = sha256.hexdigest()
    except Exception:
        pass

    log(f"  {table}: {source_rows} rows (sha256={file_checksum[:12]}...)")

    # Write checkpoint marker after successful ingestion
    try:
        with open(marker_path, "w") as f:
            json.dump({"rows": source_rows, "checksum": file_checksum, "batch_id": batch_id}, f)
    except Exception as e:
        log(f"  [WARN] Failed to write checkpoint marker for {table}: {e}")

    if pg:
        try:
            cur = pg.cursor()
            cur.execute(
                """INSERT INTO silver.batch_metadata
                   (batch_id, table_name, source_file, file_checksum, row_count, ingested_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())""",
                (batch_id, table, source_url, file_checksum, source_rows),
            )
        except Exception as e:
            log(f"  [WARN] Failed to persist batch metadata for {table}: {e}")

    conn.execute("CHECKPOINT")
    return {"table": table, "rows": source_rows}


def run():
    log("=== Bronze Ingestion Starting (S3-Centric) ===")
    write_status(STATUS_RUNNING)
    write_pid()

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    start_ts = time.time()
    os.makedirs(BRONZE_PATH, exist_ok=True)
    os.makedirs(QUARANTINE_ROOT, exist_ok=True)

    if not os.path.exists(DUCKDB_TEMP_ROOT):
        os.makedirs(DUCKDB_TEMP_ROOT, exist_ok=True)
    duckdb_temp = os.path.join(DUCKDB_TEMP_ROOT, f"bronze_{batch_id}")
    duckdb_file = os.path.join(duckdb_temp, f"bronze_{batch_id}.duckdb")
    os.makedirs(duckdb_temp, exist_ok=True)

    import duckdb
    conn = duckdb.connect(str(duckdb_file))
    sys.path.insert(0, "/opt/airflow/data-engineering")
    from bronze.s3_config import configure_s3
    configure_s3(conn)
    conn.execute("SET threads = 2")
    conn.execute("SET memory_limit = '1.5GB'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute(f"SET temp_directory = '{duckdb_temp}'")
    conn.execute("SET max_temp_directory_size = '1.25GB'")

    pg = None
    try:
        import psycopg2
        pg = psycopg2.connect(
            host="postgres", port=5432,
            user="elyssa", password="elyssa_pg_2026",
            dbname="elyssa_warehouse",
        )
        pg.autocommit = True
    except Exception as e:
        log(f"[WARN] Cannot connect to PostgreSQL: {e}")

    try:
        total_rows = 0
        results = []

        for table in BRONZE_TABLES:
            result = ingest_table(conn, table, batch_id, pg)
            results.append(result)
            total_rows += result.get("rows", 0)

        elapsed = time.time() - start_ts
        log(f"=== Bronze complete: {total_rows} rows across {len(results)} tables in {elapsed:.1f}s ===")

        batch_meta = {
            "batch_id": batch_id,
            "total_rows": total_rows,
            "tables": results,
            "elapsed_seconds": elapsed,
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(BATCH_METADATA_FILE, "w") as f:
            json.dump(batch_meta, f, indent=2)

        write_status(STATUS_COMPLETED)
        return 0

    except Exception as e:
        log(f"[FATAL] Bronze ingestion failed: {e}")
        import traceback
        traceback.print_exc()
        write_status(STATUS_FAILED)
        return 1

    finally:
        conn.close()
        try:
            if os.path.exists(duckdb_file):
                os.remove(duckdb_file)
            if os.path.exists(duckdb_temp):
                shutil.rmtree(duckdb_temp, ignore_errors=True)
        except Exception as e:
            log(f"[WARN] Failed to clean DuckDB temp: {e}")
        if pg:
            pg.close()


if __name__ == "__main__":
    sys.exit(run())