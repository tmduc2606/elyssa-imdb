"""Tests for bronze/detect_delta.py (H1 delta detection, H3 hashes, H4 schema alignment)."""

import duckdb
import pytest

from bronze.detect_delta import (
    align_silver_schema,
    check_source_delta,
    fingerprint_source,
    load_hashes,
    persist_fingerprint,
)


@pytest.fixture
def conn():
    db = duckdb.connect()
    db.execute("SET threads = 1")
    yield db
    db.close()


def _write_parquet(db, path, rows, columns=("tconst", "title")):
    cols = ", ".join(columns)
    vals = ", ".join(f"({r})" for r in rows)
    db.execute(f"CREATE OR REPLACE TABLE _t AS SELECT * FROM (VALUES {vals}) AS v({cols})")
    db.execute(f"COPY _t TO '{str(path).replace(chr(92), '/')}' (FORMAT PARQUET)")
    db.execute("DROP TABLE _t")


def test_fingerprint_source_metadata(conn, tmp_path):
    src = tmp_path / "title.basics.parquet"
    _write_parquet(conn, src, ["'tt1', 'A'", "'tt2', 'B'"])
    fp = fingerprint_source(conn, str(src))
    assert fp["row_count"] == 2
    assert fp["columns"] == ["tconst", "title"]
    assert fp["row_groups"] >= 1
    assert fp["stats_md5"]


def test_check_delta_first_run_is_delta(conn, tmp_path):
    src = tmp_path / "a.parquet"
    _write_parquet(conn, src, [("'x', 'y'")])
    assert check_source_delta(conn, "title.basics", str(src)) == "DELTA"


def test_check_delta_no_delta_when_unchanged(conn, tmp_path):
    src = tmp_path / "a.parquet"
    _write_parquet(conn, src, [("'x', 'y'")])
    fp = fingerprint_source(conn, str(src))
    assert check_source_delta(conn, "title.basics", str(src), {"title.basics": fp}) == "NO_DELTA"


def test_check_delta_detects_content_change_same_rowcount(conn, tmp_path):
    src = tmp_path / "a.parquet"
    _write_parquet(conn, src, [("'x', 'y'")])
    fp = fingerprint_source(conn, str(src))
    _write_parquet(conn, src, [("'x', 'z'")])
    assert check_source_delta(conn, "title.basics", str(src), {"title.basics": fp}) == "DELTA"


def test_check_delta_detects_schema_change(conn, tmp_path):
    src = tmp_path / "a.parquet"
    _write_parquet(conn, src, [("'x', 'y'")], columns=("tconst", "title"))
    fp = fingerprint_source(conn, str(src))
    _write_parquet(conn, src, [("'x', 'y', 'w'")], columns=("tconst", "title", "extra"))
    assert check_source_delta(conn, "title.basics", str(src), {"title.basics": fp}) == "DELTA"


def test_check_delta_missing_file_is_unknown(conn, tmp_path):
    missing = tmp_path / "nope.parquet"
    assert check_source_delta(conn, "title.basics", str(missing)) == "UNKNOWN"


def test_persist_load_roundtrip_and_no_delta(conn, tmp_path):
    src = tmp_path / "name.basics.parquet"
    _write_parquet(conn, src, [("'nm1', 'A'")], columns=("nconst", "primary_name"))
    hashes_path = tmp_path / "silver_hashes.parquet"
    assert persist_fingerprint(conn, "name.basics", str(src), str(hashes_path), "b1")
    stored = load_hashes(str(hashes_path))
    assert "name.basics" in stored
    assert stored["name.basics"]["row_count"] == 1
    assert check_source_delta(conn, "name.basics", str(src), stored) == "NO_DELTA"


def test_load_hashes_missing_path_returns_empty(tmp_path):
    assert load_hashes(str(tmp_path / "missing.parquet")) == {}


class _FakePgCursor:
    def __init__(self, existing):
        self.existing = set(existing)
        self.executed = []

    def execute(self, sql, params=None):
        self.executed.append(sql)

    def fetchall(self):
        return [(c,) for c in sorted(self.existing)]


def test_align_schema_adds_missing_columns():
    cur = _FakePgCursor({"tconst", "title"})
    added, dropped = align_silver_schema(
        cur, "silver.title_akas", ["tconst", "title", "newField"],
        {"newField": "new_field"})
    assert added == ["new_field"]
    assert dropped == []
    assert any("ADD COLUMN new_field TEXT" in sql for sql in cur.executed)


def test_align_schema_warns_on_dropped_columns():
    cur = _FakePgCursor({"tconst", "title", "obsolete"})
    added, dropped = align_silver_schema(
        cur, "silver.title_akas", ["tconst", "title"])
    assert added == []
    assert dropped == ["obsolete"]
    assert all("ADD COLUMN" not in sql for sql in cur.executed)


def test_align_schema_excludes_audit_columns():
    cur = _FakePgCursor({"tconst", "attr_hash"})
    added, dropped = align_silver_schema(
        cur, "silver.title_basics", ["tconst", "attr_hash"],
        exclude={"attr_hash"})
    assert added == []
    assert dropped == []
