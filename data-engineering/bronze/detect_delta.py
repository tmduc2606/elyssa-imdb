"""Bronze source delta detection (H1) + Silver schema alignment (H4).

Cheap, metadata-only fingerprinting of a bronze parquet source:
- row count, column list, row-group count (parquet_metadata)
- stats_md5: hash of per-column min/max/null-count statistics — content
  sensitive without a full data scan (changes when values change).

Fingerprints are persisted to a `silver_hashes.parquet` sidecar (H3) so a
rerun can detect that a source has not changed and skip the SCD2/load
stage entirely.

Guarantees:
- First run / missing fingerprint -> DELTA (full processing).
- Any fingerprint mismatch -> DELTA (full processing).
- Any error -> UNKNOWN, and callers MUST fall back to full processing
  (never silently drop data).
- Fingerprints are persisted by the caller AFTER the transaction that
  loaded the table commits — a failed run never freezes a stale hash.
"""

import json
import os
import uuid
from datetime import datetime, timezone

HASHES_TABLE_COLUMNS = [
    "table_name", "row_count", "row_groups", "columns",
    "stats_md5", "checked_at", "batch_id",
]


def _batch_id() -> str:
    return uuid.uuid4().hex[:12]


def fingerprint_source(conn, parquet_url: str) -> dict:
    """Metadata-only fingerprint of a parquet source (no data scan)."""
    url = parquet_url.replace("\\", "/")
    meta_rows = conn.execute(
        f"""
        SELECT row_group_id, max(row_group_num_rows) AS row_group_num_rows
        FROM parquet_metadata('{url}')
        GROUP BY row_group_id
        """
    ).fetchall()
    row_count = sum(r[1] for r in meta_rows)
    columns = [r[0] for r in conn.execute(
        f"DESCRIBE SELECT * FROM read_parquet('{url}')").fetchall()]
    stats_md5 = conn.execute(
        f"""
        SELECT md5(group_concat(m ORDER BY m)) FROM (
            SELECT DISTINCT md5(concat_ws('|', path_in_schema, type,
                    COALESCE(CAST(stats_min AS VARCHAR), ''),
                    COALESCE(CAST(stats_max AS VARCHAR), ''),
                    CAST(stats_null_count AS VARCHAR))) AS m
            FROM parquet_metadata('{url}')
        )
        """
    ).fetchone()[0]
    return {
        "row_count": int(row_count),
        "row_groups": len(meta_rows),
        "columns": columns,
        "stats_md5": stats_md5 or "",
    }


def load_hashes(hashes_path: str) -> dict[str, dict]:
    """Load persisted fingerprints; {} when absent or unreadable."""
    if not hashes_path or not os.path.exists(hashes_path):
        return {}
    import duckdb

    conn = duckdb.connect()
    try:
        rows = conn.execute(
            f"SELECT table_name, row_count, row_groups, columns, stats_md5 "
            f"FROM read_parquet('{hashes_path.replace(chr(92), '/')}')"
        ).fetchall()
        return {
            r[0]: {
                "row_count": int(r[1]),
                "row_groups": int(r[2]),
                "columns": json.loads(r[3]),
                "stats_md5": r[4],
            }
            for r in rows
        }
    except Exception:
        return {}
    finally:
        conn.close()


def persist_fingerprint(conn, table_name: str, parquet_url: str,
                        hashes_path: str, batch_id: str = "") -> bool:
    """Compute the current fingerprint and persist it (H3).

    Call only AFTER the table's load transaction has committed.
    """
    if not hashes_path:
        return False

    try:
        current = fingerprint_source(conn, parquet_url)
        previous = load_hashes(hashes_path)
        previous[table_name] = current
        checked_at = datetime.now(timezone.utc).isoformat()
        parent = os.path.dirname(hashes_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        conn.execute(
            f"CREATE TEMP TABLE _hashes ({', '.join(c + ' VARCHAR' for c in HASHES_TABLE_COLUMNS)})"
        )
        rows = [[
            table_name,
            str(current["row_count"]),
            str(current["row_groups"]),
            json.dumps(current["columns"]),
            str(current["stats_md5"]),
            checked_at,
            batch_id or _batch_id(),
        ]]
        conn.executemany(
            "INSERT INTO _hashes VALUES (?, ?, ?, ?, ?, ?, ?)", rows)
        conn.execute(
            f"COPY _hashes TO '{hashes_path.replace(chr(92), '/')}' "
            "(FORMAT PARQUET, COMPRESSION SNAPPY)"
        )
        return True
    except Exception:
        return False
    finally:
        try:
            conn.execute("DROP TABLE IF EXISTS _hashes")
        except Exception:
            pass


def check_source_delta(conn, table_name: str, parquet_url: str,
                       hashes: dict | None = None) -> str:
    """Return 'NO_DELTA', 'DELTA', or 'UNKNOWN' for a bronze source.

    No persistence — callers persist (H3) after their load commits.
    'UNKNOWN' means fingerprinting failed; callers must process fully.
    """
    try:
        current = fingerprint_source(conn, parquet_url)
        previous = (hashes or {}).get(table_name)
        if previous is None:
            return "DELTA"
        if (
            previous.get("row_count") == current["row_count"]
            and previous.get("row_groups") == current["row_groups"]
            and previous.get("columns") == current["columns"]
            and previous.get("stats_md5") == current["stats_md5"]
        ):
            return "NO_DELTA"
        return "DELTA"
    except Exception:
        return "UNKNOWN"


def align_silver_schema(pg_cursor, dst_table: str, bronze_columns: list[str],
                        column_map: dict[str, str] | None = None,
                        exclude: set[str] | None = None) -> tuple[list[str], list[str]]:
    """H4: ADD-only schema alignment of a silver table to bronze columns.

    Returns (added, dropped). Missing bronze columns are added as TEXT
    (never inferred types). Columns in silver but absent from bronze are
    returned as 'dropped' for the caller to warn about — never dropped.
    """
    schema, table = dst_table.split(".", 1)
    pg_cursor.execute(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_schema = %s AND table_name = %s",
        (schema, table),
    )
    existing = {r[0] for r in pg_cursor.fetchall()}
    exclude = exclude or set()
    added = []
    for col in bronze_columns:
        snake = (column_map or {}).get(col, col)
        if snake in existing or snake in exclude:
            continue
        pg_cursor.execute(f"ALTER TABLE {dst_table} ADD COLUMN {snake} TEXT")
        added.append(snake)
    snake_set = {(column_map or {}).get(c, c) for c in bronze_columns} | exclude
    dropped = sorted(existing - snake_set)
    return added, dropped
