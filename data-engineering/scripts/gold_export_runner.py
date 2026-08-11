"""
Elyssa-IMDb | Gold Export Runner (detached subprocess)

Exports all Gold-layer tables (6 tables) from PostgreSQL to Snappy Parquet
in a bind-mounted host directory, plus a manifest. Row counts are read from
the parquet footers (pyarrow metadata) — no COUNT(*) re-scan (P0-2).
Tables are exported in parallel with 2 workers (O4), each worker using its
own DuckDB connection.

Runs OUTSIDE Airflow's supervisor (spawned with start_new_session=True)
so the long DuckDB postgres_scanner COPY operations survive the scheduler's
300s orphan-pass reset.

Markers written to the output dir:
  .export.running   - started
  .export.completed - all tables exported + manifest (success)
  .export.failed    - fatal error (check the log)

Usage:
  python gold_export_runner.py --output-dir /opt/airflow/output/gold/
"""

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

import duckdb
from pyarrow.parquet import read_metadata

TABLES = [
    "dim_person",
    "dim_title",
    "fact_episode",
    "fact_performance",
    "fact_title_principal",
    "fact_title_rating",
]

EXPORT_WORKERS = 2


def _log(message: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def _where_clause(table: str) -> str:
    if table == "dim_title":
        return (
            " WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))"
        )
    return ""


def _export_one(conn_info: dict, table: str, output_dir: Path) -> int:
    """Export a single table on its own DuckDB connection (worker-safe)."""
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        dsn = (
            f"host={conn_info['host']} port={conn_info['port']} "
            f"dbname={conn_info['dbname']} user={conn_info['user']} "
            f"password={conn_info['password']}"
        )
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold');")
        path = output_dir / f"{table}.parquet"
        sql = f"SELECT * FROM pg.gold.{table}{_where_clause(table)}"
        conn.execute(
            f"COPY ({sql}) TO '{path}' (FORMAT PARQUET, COMPRESSION SNAPPY)"
        )
        # P0-2: footer-only row count (no post-export COUNT(*) re-scan)
        return read_metadata(path).num_rows
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Gold parquet export runner")
    parser.add_argument("--output-dir", default="/opt/airflow/output/gold/")
    parser.add_argument("--pg-host", default="postgres")
    parser.add_argument("--pg-port", type=int, default=5432)
    parser.add_argument("--pg-db", default="elyssa_warehouse")
    parser.add_argument("--pg-user", default="elyssa")
    args = parser.parse_args()

    pg_password = os.environ.get("GOLD_EXPORT_PG_PASSWORD", "")
    if not pg_password:
        _log("FATAL: GOLD_EXPORT_PG_PASSWORD environment variable is not set")
        return 1

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    running_marker = output_dir / ".export.running"
    completed_marker = output_dir / ".export.completed"
    failed_marker = output_dir / ".export.failed"

    for marker in (completed_marker, failed_marker):
        if marker.exists():
            marker.unlink()
    running_marker.touch()

    # Remove any stale temporary parquet files from previous interrupted runs
    for stale in output_dir.glob("tmp_*.parquet"):
        try:
            stale.unlink()
            _log(f"Removed stale partial file: {stale.name}")
        except OSError as e:
            _log(f"Warning: could not remove stale {stale.name}: {e}")

    row_counts = {}
    conn_info = {
        "host": args.pg_host,
        "port": args.pg_port,
        "dbname": args.pg_db,
        "user": args.pg_user,
        "password": pg_password,
    }
    _log(f"Connected to {args.pg_db} (schema gold), exporting {len(TABLES)} tables "
         f"with {EXPORT_WORKERS} workers")

    with ThreadPoolExecutor(max_workers=EXPORT_WORKERS,
                            thread_name_prefix="gold-export") as executor:
        futures = {
            executor.submit(_export_one, conn_info, t, output_dir): t
            for t in TABLES
        }
        for future in as_completed(futures):
            table = futures[future]
            started = datetime.now(timezone.utc)
            try:
                count = future.result()
                row_counts[table] = count
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                _log(f"Exported gold.{table}: {count:,} rows -> {table}.parquet ({elapsed:.0f}s)")
            except Exception as e:
                row_counts[table] = None
                _log(f"Failed to export gold.{table}: {e}")

    # Write manifest
    manifest = {
        "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": TABLES,
        "row_counts": row_counts,
        "layer": "gold",
        "description": "Gold-layer PostgreSQL tables exported as Parquet for DS benchmarking",
    }
    manifest_path = output_dir / "_MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    _log(f"Manifest written: {manifest_path.name}")

    if row_counts.get("dim_title") is not None:
        _log(f"dim_title rows after filter: {row_counts['dim_title']:,}")

    running_marker.unlink(missing_ok=True)
    completed_marker.touch()
    _log("SUCCESS: .export.completed marker written")
    return 0


if __name__ == "__main__":
    sys.exit(main())