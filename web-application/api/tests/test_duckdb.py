from __future__ import annotations

from app.dependencies import get_duckdb
from app.graphql.resolvers import _get_con


# ─── WA-25: single shared DuckDB connection ───────────────────────────
def test_duckdb_single_instance():
    """Both connection entry points must resolve to the SAME object."""
    con_a = _get_con()
    con_b = get_duckdb()
    assert con_a is con_b, "get_duckdb() must delegate to the shared _get_con() connection"


def test_duckdb_connection_lru_cached():
    assert _get_con() is _get_con(), "_get_con must be cached (single connection)"


def test_duckdb_views_exposed():
    con = _get_con()
    tables = {
        r[0] for r in con.execute("SHOW TABLES").fetchall()
    }
    assert {"dim_title", "dim_person"} <= tables