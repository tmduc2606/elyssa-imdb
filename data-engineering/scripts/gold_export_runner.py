"""
Elyssa-IMDb | Gold Export Runner (detached subprocess)

Exports all Gold-layer tables (6 tables) from PostgreSQL to Snappy Parquet
in a bind-mounted host directory, creates a tar archive and manifest.

Runs OUTSIDE Airflow's supervisor (spawned with start_new_session=True)
so the long DuckDB postgres_scanner COPY operations survive the scheduler's
300s orphan-pass reset.

Markers written to the output dir:
  .export.running   - started
  .export.completed - all tables exported + tar + manifest (success)
  .export.failed    - fatal error (check the log)

Usage:
  python gold_export_runner.py --output-dir /opt/airflow/output/gold/
"""

import argparse
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

import duckdb

TABLES = [
    "dim_person",
    "dim_title",
    "fact_episode",
    "fact_performance",
    "fact_title_principal",
    "fact_title_rating",
]


def _log(message: str):
    print(f"[{datetime.now(timezone.utc).isoformat()}] {message}", flush=True)


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
    conn = duckdb.connect(":memory:")
    try:
        conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
        dsn = (
            f"host={args.pg_host} port={args.pg_port} dbname={args.pg_db} "
            f"user={args.pg_user} password={pg_password}"
        )
        conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold');")
        _log(f"Connected to {args.pg_db} (schema gold), exporting {len(TABLES)} tables")

        for t in TABLES:
            path = output_dir / f"{t}.parquet"
            started = datetime.now(timezone.utc)
            try:
                if t == "dim_title":
                    where_clause = (
                        " WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))"
                    )
                else:
                    where_clause = ""
                sql = f"SELECT * FROM pg.gold.{t}{where_clause}"
                conn.execute(
                    f'COPY ({sql}) TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY)'
                )
                r = conn.execute(f'SELECT count(*) FROM pg.gold.{t}{where_clause}').fetchone()[0]
                row_counts[t] = r
                elapsed = (datetime.now(timezone.utc) - started).total_seconds()
                _log(f"Exported gold.{t}: {r:,} rows -> {path.name} ({elapsed:.0f}s)")
            except Exception as e:
                row_counts[t] = None
                _log(f"Failed to export gold.{t}: {e}")

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

    # Create tar archive
    tar_path = "/tmp/gold_marts.tar.gz"
    files_to_tar = [f.name for f in output_dir.glob("*.parquet")] + ["_MANIFEST.json"]
    try:
        subprocess.run(
            ["tar", "-czf", tar_path, "-C", str(output_dir)] + files_to_tar,
            check=True,
            capture_output=True,
            text=True,
        )
        tar_size = os.path.getsize(tar_path)
        _log(f"Tar archive created: {tar_path} ({tar_size / (1024*1024):.1f} MB)")
    except Exception as e:
        _log(f"FATAL: failed to create tar archive: {e}")
        _log(traceback.format_exc())
        failed_marker.touch()
        return 1

    if row_counts.get("dim_title") is not None:
        _log(f"dim_title rows after filter: {row_counts['dim_title']:,}")

    running_marker.unlink(missing_ok=True)
    completed_marker.touch()
    _log("SUCCESS: .export.completed marker written")
    return 0


if __name__ == "__main__":
    sys.exit(main())