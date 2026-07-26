"""
Elyssa-IMDb | Standalone Bronze Ingestion
Runs all 7 bronze tables via DuckDB, outside Airflow's supervisor.
Status markers: .running, .completed, .failed (written to bronze_path).
"""

import os
import sys
import subprocess as _sp
import hashlib
import shutil
import time
import json
from datetime import datetime, timezone

# ─── Paths ──────────────────────────────────────────────────────────
BRONZE_PATH = "/opt/airflow/output/bronze/"
SOURCE_DIR = "/opt/airflow/data-engineering/duke/gate0/source/"
QUARANTINE_ROOT = "/opt/airflow/output/bronze/quarantine/"
DUCKDB_TEMP_ROOT = "/opt/airflow/output/tmp/"
BATCH_METADATA_FILE = os.path.join(BRONZE_PATH, ".batch_metadata.json")

STATUS_RUNNING = os.path.join(BRONZE_PATH, ".running")
STATUS_COMPLETED = os.path.join(BRONZE_PATH, ".completed")
STATUS_FAILED = os.path.join(BRONZE_PATH, ".failed")
PID_FILE = os.path.join(BRONZE_PATH, ".bronze_pid")

EXPECTED_COLUMNS = {
    "title.basics": 9,
    "title.akas": 8,
    "title.crew": 3,
    "title.episode": 4,
    "title.principals": 6,
    "title.ratings": 3,
    "name.basics": 6,
}

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
    "title.basics": "title.basics.tsv",
    "title.akas": "title.akas.tsv",
    "title.crew": "title.crew.tsv",
    "title.episode": "title.episode.tsv",
    "title.principals": "title.principals.tsv",
    "title.ratings": "title.ratings.tsv",
    "name.basics": "name.basics.tsv",
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


def ingest_table(conn, table, batch_id, pg):
    filename = SOURCE_FILES.get(table, f"{table}.tsv")
    file_path = os.path.join(SOURCE_DIR, filename)
    output_path = os.path.join(BRONZE_PATH, f"{table}.parquet")

    if not os.path.exists(file_path):
        log(f"  SKIP {table}: source file not found: {file_path}")
        return {"table": table, "rows": 0, "skipped": True}

    # Checkpoint resume
    if os.path.exists(output_path):
        existing_count = conn.execute(f"SELECT COUNT(*) FROM '{output_path}'").fetchone()[0]
        log(f"  CHECKPOINT {table}: {existing_count} rows already at {output_path}")
        return {"table": table, "rows": existing_count, "checkpoint": True}

    # Validate
    expected_cols = EXPECTED_COLUMNS.get(table)
    if expected_cols is not None:
        try:
            sys.path.insert(0, "/opt/airflow/data-engineering")
            from bronze.quarantine import validate_source_file
            is_valid, error_msg, row_count = validate_source_file(
                file_path, table, expected_cols, QUARANTINE_ROOT
            )
            if not is_valid:
                log(f"  QUARANTINE {table}: {error_msg}")
                if pg:
                    with pg.cursor() as cur:
                        quarantine_record(cur, table, file_path, error_msg, batch_id)
                return {"table": table, "rows": 0, "quarantined": True, "error": error_msg}
        except ImportError:
            log("  quarantine module not available, skipping validation")
        except Exception as e:
            log(f"  [WARN] Validation error for {table}: {e}")

    # File checksum for lineage
    file_checksum = ""
    try:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(8192), b""):
                sha256.update(chunk)
        file_checksum = sha256.hexdigest()
    except Exception:
        pass

    # wc -l for fast row counting (M4)
    try:
        result = _sp.run(["wc", "-l", file_path], capture_output=True, text=True, timeout=30)
        source_rows = int(result.stdout.strip().split()[0]) - 1
    except Exception:
        source_rows = 0
    row_count = source_rows

    now_ts = datetime.now(timezone.utc).isoformat()
    log(f"  {table}: {row_count} rows (sha256={file_checksum[:12]}...)")

    schema_def = BRONZE_SCHEMAS.get(table, {})
    if schema_def:
        cols_str = ", ".join(f"'{k}': '{v}'" for k, v in schema_def.items())
        read_csv_sql = f"read_csv(?, columns={{{cols_str}}}, delim='\\t', header=true, null_padding=true, ignore_errors=true, quote='', escape='')"
    else:
        read_csv_sql = "read_csv(?, delim='\\t', header=true, all_varchar=true, null_padding=true, ignore_errors=true, quote='', escape='')"

    fp = file_path.replace("'", "''")
    op = output_path.replace("'", "''")
    copy_sql = read_csv_sql.replace("?", f"'{fp}'")
    conn.execute(
        f"COPY ("
        f"  SELECT *, '{fp}' AS _source_file, '{table}' AS _source_table, '{batch_id}' AS _batch_id, '{now_ts}' AS _ingested_at, {row_count} AS _row_count, '{file_checksum}' AS _file_checksum "
        f"  FROM {copy_sql}"
        f") TO '{op}' (FORMAT PARQUET, COMPRESSION snappy)"
    )

    log(f"  {table} written -> {output_path}")

    # Persist batch metadata
    if pg:
        try:
            cur = pg.cursor()
            cur.execute(
                """INSERT INTO silver.batch_metadata
                   (batch_id, table_name, source_file, file_checksum, row_count, ingested_at)
                   VALUES (%s, %s, %s, %s, %s, NOW())""",
                (batch_id, table, file_path, file_checksum, row_count),
            )
        except Exception as e:
            log(f"  [WARN] Failed to persist batch metadata for {table}: {e}")

    conn.execute("CHECKPOINT")
    return {"table": table, "rows": row_count}


def run():
    log("=== Bronze Ingestion Starting ===")
    write_status(STATUS_RUNNING)
    write_pid()

    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    start_ts = time.time()
    os.makedirs(BRONZE_PATH, exist_ok=True)
    os.makedirs(QUARANTINE_ROOT, exist_ok=True)

    # ── DuckDB file-backed (M1) ─────────────────────────────────────
    if not os.path.exists(DUCKDB_TEMP_ROOT):
        os.makedirs(DUCKDB_TEMP_ROOT, exist_ok=True)
    duckdb_temp = os.path.join(DUCKDB_TEMP_ROOT, f"bronze_{batch_id}")
    duckdb_file = os.path.join(duckdb_temp, f"bronze_{batch_id}.duckdb")
    os.makedirs(duckdb_temp, exist_ok=True)

    import duckdb
    conn = duckdb.connect(str(duckdb_file))
    conn.execute("SET threads = 2")
    conn.execute("SET memory_limit = '1.5GB'")
    conn.execute("SET preserve_insertion_order = false")
    conn.execute(f"SET temp_directory = '{duckdb_temp}'")
    conn.execute("SET max_temp_directory_size = '10GB'")

    # ── PostgreSQL (quarantine + metadata) ──────────────────────────
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