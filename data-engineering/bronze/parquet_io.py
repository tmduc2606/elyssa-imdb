"""Shared helper to write list[dict] rows to Parquet via DuckDB.

Used by the legacy standalone scripts (ingest_imdb.py, db_reader.py).
Avoids a Spark dependency: rows are staged into a temp table and
exported with COPY ... TO (FORMAT PARQUET, COMPRESSION SNAPPY).
"""

import os

import duckdb as _duckdb_lib


def _clean_path(path: str) -> str:
    return path.replace("\\", "/")


def write_rows_to_parquet(rows: list[dict], parquet_path: str) -> None:
    """Write rows to a single snappy Parquet file. No-op for empty rows."""
    if not rows:
        return
    conn = _duckdb_lib.connect()
    try:
        if not parquet_path.startswith("s3://"):
            parent = os.path.dirname(parquet_path)
            if parent:
                os.makedirs(parent, exist_ok=True)
        cols = list(rows[0].keys())
        col_defs = ", ".join(f'"{c}" VARCHAR' for c in cols)
        placeholders = ", ".join(["?"] * len(cols))
        conn.execute(f"CREATE TEMP TABLE _out ({col_defs})")
        conn.executemany(
            f"INSERT INTO _out VALUES ({placeholders})",
            [[r.get(c) for c in cols] for r in rows],
        )
        conn.execute(
            f"COPY _out TO '{_clean_path(parquet_path)}' "
            "(FORMAT PARQUET, COMPRESSION SNAPPY)"
        )
    finally:
        conn.close()
