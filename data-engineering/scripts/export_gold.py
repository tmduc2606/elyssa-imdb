#!/usr/bin/env python3
"""
Gold Export Wrapper — DuckDB postgres_scanner → Snappy Parquet → tar archive.

Usage (inside container):
    python scripts/export_gold.py

Output:
    /opt/airflow/output/gold/  — 6 Parquet files + _MANIFEST.json
    /tmp/gold_marts.tar.gz     — compressed archive for docker cp

Usage (host, after export completes):
    docker exec elyssa-airflow sh -c "cd /opt/airflow/output/gold && tar -czf /tmp/gold_marts.tar.gz *.parquet _MANIFEST.json"
    docker cp elyssa-airflow:/tmp/gold_marts.tar.gz ./tmp_gold_marts.tar.gz
    tar -xzf ./tmp_gold_marts.tar.gz -C data-science/marts/full/
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def export_gold(
    pg_host="postgres",
    pg_port=5432,
    pg_db="elyssa_warehouse",
    pg_user="elyssa",
    pg_password="elyssa_pg_2026",
    output_dir="/opt/airflow/output/gold/",
):
    import duckdb

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(":memory:")
    conn.execute("INSTALL postgres_scanner; LOAD postgres_scanner;")
    dsn = f"host={pg_host} port={pg_port} dbname={pg_db} user={pg_user} password={pg_password}"
    conn.execute(f"ATTACH '{dsn}' AS pg (TYPE POSTGRES, SCHEMA 'gold');")

    tables = [
        "dim_person",
        "dim_title",
        "fact_episode",
        "fact_performance",
        "fact_title_principal",
        "fact_title_rating",
    ]
    row_counts = {}
    for t in tables:
        path = Path(output_dir) / f"{t}.parquet"
        if t == "dim_title":
            conn.execute(f"""
                COPY (
                    SELECT * FROM pg.gold."{t}"
                    WHERE NOT (title_type = 'movie' AND (runtime_minutes IS NULL OR runtime_minutes <= 0))
                ) TO '{path}' (FORMAT PARQUET, COMPRESSION SNAPPY)
            """)
        else:
            conn.execute(
                f'COPY (SELECT * FROM pg.gold."{t}") TO \'{path}\' (FORMAT PARQUET, COMPRESSION SNAPPY)'
            )
        r = conn.execute(f'SELECT count(*) FROM pg.gold."{t}"').fetchone()[0]
        row_counts[t] = r
        print(f"[EXPORT] {t}: {r:,} rows -> {path}")

    manifest = {
        "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "tables": tables,
        "row_counts": row_counts,
    }
    manifest_path = Path(output_dir) / "_MANIFEST.json"
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)
    print(f"[EXPORT] Manifest written: {manifest_path}")

    conn.close()

    # Create tar archive for easy docker cp
    tar_path = "/tmp/gold_marts.tar.gz"
    subprocess.run(
        ["tar", "-czf", tar_path, "-C", output_dir] + [f"{t}.parquet" for t in tables] + ["_MANIFEST.json"],
        check=True,
    )
    print(f"[EXPORT] Archive created: {tar_path}")
    file_size_mb = os.path.getsize(tar_path) / (1024 * 1024)
    print(f"[EXPORT] Archive size: {file_size_mb:.1f} MB")

    host_path = "/mnt/host/data-science/marts/full/"
    if os.path.isdir("/mnt/host"):
        subprocess.run(["tar", "-xzf", tar_path, "-C", host_path], check=True)
        print(f"[EXPORT] Extracted to host: {host_path}")

    return True


def main():
    pg_password = os.environ.get("GOLD_EXPORT_PG_PASSWORD", "elyssa_pg_2026")
    success = export_gold(pg_password=pg_password)
    if not success:
        sys.exit(1)
    print("[EXPORT] Gold export complete")


if __name__ == "__main__":
    main()
