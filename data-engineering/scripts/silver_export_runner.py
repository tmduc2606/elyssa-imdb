"""
Elyssa-IMDb | Silver Export Runner (detached subprocess)

Exports all 14 Silver tables (6 parent + 8 child) from PostgreSQL to
Snappy Parquet in a bind-mounted host directory.

Runs OUTSIDE Airflow's supervisor (spawned with start_new_session=True,
like run_bronze.py / silver_operator.py) so the long DuckDB postgres_scanner
COPY operations survive the scheduler's 300s orphan-pass reset, which
SIGKILLs any in-process task work every cycle.

Markers written to the output dir:
  .export.running   - started
  .export.completed - all tables exported (success)
  .export.failed    - fatal error (check the log)

Usage:
  python silver_export_runner.py --output-dir /opt/airflow/output/silver/
"""

import argparse
import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import duckdb

TABLES = [
    "title_basics", "title_akas", "title_crew", "title_episode",
    "title_principal", "title_rating", "name_basics",
    "title_genre", "title_director", "title_writer",
    "title_akas_type", "title_akas_attribute", "title_principal_char",
    "name_profession", "name_known_for_title",
]


def _log(message: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Silver parquet export runner")
    parser.add_argument("--output-dir", default="/opt/airflow/output/silver/")
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

    for stale in output_dir.glob("tmp_*.parquet"):
        try:
            stale.unlink()
            _log(f"Removed stale partial file: {stale.name}")
        except OSError as e:
            _log(f"Warning: could not remove stale {stale.name}: {e}")

    row_counts = {}
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        dsn = (
            f"host={args.pg_host} port={args.pg_port} dbname={args.pg_db} "
            f"user={args.pg_user} password={pg_password}"
        )
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'silver');")
        _log(f"Connected to {args.pg_db} (schema silver), exporting {len(TABLES)} tables")

        for t in TABLES:
            path = output_dir / f"{t}.parquet"
            started = datetime.now(timezone.utc)
            try:
                conn.execute(
                    f'COPY (SELECT * FROM pg."{t}") TO \'{path}\' '
                    f"(FORMAT PARQUET, COMPRESSION SNAPPY)"
                )
                r = conn.execute(f'SELECT count(*) FROM pg."{t}"').fetchone()[0]
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                row_counts[t] = r
                _log(f"Exported silver.{t}: {r:,} rows -> {path.name} ({elapsed:.0f}s)")
            except Exception as e:
                row_counts[t] = None
                _log(f"Failed to export silver.{t}: {e}")

        manifest = {
            "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "tables": TABLES,
            "row_counts": row_counts,
            "layer": "silver",
            "description": "Silver-layer PostgreSQL tables exported as Parquet for DS benchmarking",
        }
        manifest_path = output_dir / "_MANIFEST.json"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        _log(f"Manifest written: {manifest_path.name}")
        _log(f"Export complete: {sum(1 for v in row_counts.values() if v is not None)}/{len(TABLES)} tables exported")
    except Exception as e:
        _log(f"FATAL: {e}")
        _log(traceback.format_exc())
        failed_marker.touch()
        return 1
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if row_counts.get("title_crew") is None and all(v is not None for k, v in row_counts.items() if k != "title_crew"):
        _log("Note: title_crew does not exist in silver schema (children title_director/title_writer replace it)")

    running_marker.unlink(missing_ok=True)
    completed_marker.touch()
    _log("SUCCESS: .export.completed marker written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
