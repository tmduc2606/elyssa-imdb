from __future__ import annotations

from functools import lru_cache

import duckdb


@lru_cache
def get_duckdb() -> duckdb.DuckDBPyConnection:
    """Deprecated alias — returns the single shared DuckDB connection.

    WA-25: deduplicated with ``app.graphql.resolvers._get_con`` so the API
    never opens a second connection to the Gold marts. Kept as a thin alias
    for backwards-compatible imports; all query paths use ``_get_con``.
    """
    from app.graphql.resolvers import _get_con

    return _get_con()
