from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import duckdb

from app.config import get_settings


@lru_cache
def get_duckdb() -> duckdb.DuckDBPyConnection:
    settings = get_settings()
    con = duckdb.connect()
    for parquet in sorted(Path(settings.gold_marts_path).glob("*.parquet")):
        stem = parquet.stem
        con.execute(f"CREATE VIEW IF NOT EXISTS {stem} AS SELECT * FROM read_parquet('{parquet}')")
    return con
