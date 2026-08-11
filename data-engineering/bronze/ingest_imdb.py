# NOTE: Legacy standalone PySpark ingestion script, rewritten to run on
# DuckDB only (no Spark dependency). The canonical pipeline path is
# scripts/run_bronze.py (DuckDB + psycopg2), orchestrated by
# orchestration/dags/imdb_pipeline_dag.py. This module is retained for
# offline / ad-hoc ingestion and exercises the same bronze.quarantine
# validation and flat s3://bronze/{table}.parquet output layout.

import json
import os
import uuid
from datetime import datetime, timezone

import duckdb as _duckdb_lib

from bronze.config import SOURCE_CONFIG, DEFAULT_OUTPUT_ROOT, DEFAULT_METADATA_ROOT
from bronze.quarantine import validate_source_file, compute_file_checksum
from bronze.parquet_io import write_rows_to_parquet


def generate_batch_id() -> str:
    return uuid.uuid4().hex[:12]


def _clean_path(path: str) -> str:
    return path.replace("\\", "/")


def read_source(file_path: str, source_name: str,
                conn=None) -> list[dict]:
    """Read a tab-delimited IMDb source file as list[dict] (raw strings).

    Bronze fidelity: all columns are read as VARCHAR and \\N is preserved
    as a literal (SOURCE_CONFIG null_value is None).
    """
    cfg = SOURCE_CONFIG[source_name]
    close_conn = conn is None
    conn = conn or _duckdb_lib.connect()
    try:
        result = conn.execute(
            f"SELECT * FROM read_csv('{_clean_path(file_path)}', "
            "delim='\t', header=false, all_varchar=true, quote='', escape='')"
        )
        rows = result.fetchall()
        if len(result.description) != len(cfg["columns"]):
            raise ValueError(
                f"Column count mismatch for {source_name}: "
                f"expected {len(cfg['columns'])}, got {len(result.description)}"
            )
        return [dict(zip(cfg["columns"], row)) for row in rows]
    finally:
        if close_conn:
            conn.close()


def add_metadata(rows: list[dict], source_name: str, batch_id: str,
                 row_count: int = 0, checksum: str = "",
                 source_file: str = "") -> list[dict]:
    now_ts = datetime.now(timezone.utc).isoformat()
    out = []
    for row in rows:
        record = dict(row)
        record["_source_file"] = source_file
        record["_source_table"] = source_name
        record["_batch_id"] = batch_id
        record["_ingested_at"] = now_ts
        record["_row_count"] = row_count
        record["_checksum"] = checksum
        out.append(record)
    return out


def write_bronze(rows: list[dict], output_root: str, source_name: str) -> None:
    output_path = f"{output_root}/{source_name}.parquet"
    write_rows_to_parquet(rows, output_path)


def log_ingestion_metrics(file_path: str, source_name: str,
                          row_count: int, batch_id: str,
                          log_root: str) -> None:
    os.makedirs(log_root, exist_ok=True)
    entry = {
        "batch_id": batch_id,
        "source_table": source_name,
        "source_file": file_path,
        "row_count": row_count,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "status": "success",
    }
    with open(os.path.join(log_root, "ingestion_log.jsonl"), "a",
              encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def ingest_single_source(file_path: str, source_name: str,
                         output_root: str, batch_id: str,
                         log_root: str = DEFAULT_METADATA_ROOT) -> int:
    print(f"[{batch_id}] Ingesting {source_name} from {file_path}")

    cfg = SOURCE_CONFIG[source_name]
    expected_columns = len(cfg["columns"])
    is_valid, error_msg, _ = validate_source_file(
        file_path, source_name, expected_columns
    )
    if not is_valid:
        print(f"[{batch_id}] QUARANTINED {source_name}: {error_msg}")
        return 0

    rows = read_source(file_path, source_name)
    checksum = compute_file_checksum(file_path)
    rows = add_metadata(rows, source_name, batch_id,
                        row_count=len(rows), checksum=checksum,
                        source_file=file_path)
    write_bronze(rows, output_root, source_name)
    log_ingestion_metrics(file_path, source_name, len(rows), batch_id, log_root)
    print(f"[{batch_id}] {source_name}: {len(rows)} rows ingested")
    return len(rows)


def ingest_all(sources: dict[str, str],
               output_root: str = DEFAULT_OUTPUT_ROOT,
               log_root: str = DEFAULT_METADATA_ROOT) -> dict[str, int]:
    batch_id = generate_batch_id()
    print(f"Bronze ingestion batch: {batch_id}")
    results = {}
    for source_name, file_path in sources.items():
        if source_name not in SOURCE_CONFIG:
            print(f"Unknown source: {source_name}, skipping")
            continue
        count = ingest_single_source(file_path, source_name,
                                     output_root, batch_id, log_root)
        results[source_name] = count
    print(f"Batch {batch_id} complete. Results: {json.dumps(results)}")
    return results


if __name__ == "__main__":
    import sys

    sources = {
        "title.akas": sys.argv[1],
        "title.basics": sys.argv[2],
        "title.crew": sys.argv[3],
        "title.episode": sys.argv[4],
        "title.principals": sys.argv[5],
        "title.ratings": sys.argv[6],
        "name.basics": sys.argv[7],
    }
    ingest_all(sources)
