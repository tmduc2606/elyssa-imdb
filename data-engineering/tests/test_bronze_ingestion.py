"""Bronze ingestion logic tests — DuckDB-based, no Spark."""

import hashlib
import json
import os
import pathlib

import duckdb
import pytest

from bronze.ingest_imdb import (
    generate_batch_id, add_metadata, read_source,
    write_bronze, log_ingestion_metrics, ingest_single_source, ingest_all,
)
from bronze.quarantine import validate_source_file, compute_file_checksum

RATINGS_LINES = [
    "tt0000001\t6.3\t154",
    "tt0000002\t5.9\t120",
    "tt0000003\t\\N\t89",
]


def _write_file(tmp_path: pathlib.Path, name: str, lines: list[str]) -> str:
    path = tmp_path / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return str(path)


class TestGenerateBatchId:
    def test_returns_12_hex(self):
        bid = generate_batch_id()
        assert len(bid) == 12
        assert all(c in "0123456789abcdef" for c in bid)

    def test_unique(self):
        ids = {generate_batch_id() for _ in range(100)}
        assert len(ids) == 100


class TestAddMetadata:
    def test_metadata_columns_added(self):
        rows = [{"tconst": "tt0000001"}, {"tconst": "tt0000002"}]
        out = add_metadata(rows, "title.ratings", "batch_test",
                           row_count=42, checksum="abc123def456",
                           source_file="/data/ratings.tsv.gz")
        assert len(out) == 2
        for r in out:
            assert r["_source_table"] == "title.ratings"
            assert r["_batch_id"] == "batch_test"
            assert r["_ingested_at"] is not None
            assert r["_row_count"] == 42
            assert r["_checksum"] == "abc123def456"
            assert r["_source_file"] == "/data/ratings.tsv.gz"
        assert out[0]["tconst"] == "tt0000001"

    def test_input_not_mutated(self):
        rows = [{"tconst": "tt1"}]
        add_metadata(rows, "title.ratings", "b1")
        assert "tconst" in rows[0]
        assert "_batch_id" not in rows[0]

    def test_empty_input(self):
        assert add_metadata([], "title.ratings", "b1") == []


class TestReadSource:
    def test_reads_rows_and_columns(self, tmp_path):
        path = _write_file(tmp_path, "ratings.tsv", RATINGS_LINES)
        rows = read_source(path, "title.ratings")
        assert len(rows) == 3
        assert list(rows[0].keys()) == ["tconst", "averageRating", "numVotes"]
        assert rows[0]["tconst"] == "tt0000001"
        assert rows[0]["averageRating"] == "6.3"

    def test_preserves_null_marker(self, tmp_path):
        path = _write_file(tmp_path, "ratings.tsv", RATINGS_LINES)
        rows = read_source(path, "title.ratings")
        assert rows[2]["averageRating"] == "\\N"

    def test_column_count_mismatch_raises(self, tmp_path):
        path = _write_file(tmp_path, "bad.tsv", ["tt0000001\t6.3"])
        with pytest.raises(ValueError, match="Column count mismatch"):
            read_source(path, "title.ratings")

    def test_missing_file_raises(self, tmp_path):
        with pytest.raises(Exception):
            read_source(str(tmp_path / "nope.tsv"), "title.ratings")


class TestQuarantine:
    def test_valid_file(self, tmp_path):
        path = _write_file(tmp_path, "valid.tsv", RATINGS_LINES)
        is_valid, error_msg, pre_count = validate_source_file(
            path, "title.ratings", 3)
        assert is_valid is True
        assert error_msg == ""
        assert pre_count == 3

    def test_missing_file(self):
        is_valid, error_msg, pre_count = validate_source_file(
            "/nonexistent/path.tsv", "title.ratings", 3)
        assert is_valid is False
        assert "not found" in error_msg
        assert pre_count == 0

    def test_empty_file(self, tmp_path):
        path = _write_file(tmp_path, "empty.tsv", [])
        is_valid, error_msg, _ = validate_source_file(
            path, "title.ratings", 3)
        assert is_valid is False
        assert "Empty" in error_msg

    def test_column_count_mismatch(self, tmp_path):
        path = _write_file(tmp_path, "bad.tsv", ["tt0000001\t6.3"])
        is_valid, error_msg, _ = validate_source_file(
            path, "title.ratings", 3)
        assert is_valid is False
        assert "Column count mismatch" in error_msg

    def test_checksum_is_sha256(self, tmp_path):
        path = _write_file(tmp_path, "c.tsv", ["a\tb"])
        checksum = compute_file_checksum(path)
        expected = hashlib.sha256(b"a\tb\n").hexdigest()
        assert checksum == expected

    def test_checksum_deterministic(self, tmp_path):
        path = _write_file(tmp_path, "c.tsv", ["a\tb"])
        assert compute_file_checksum(path) == compute_file_checksum(path)


class TestWriteAndLog:
    def test_write_bronze_creates_parquet(self, tmp_path):
        rows = add_metadata(
            [{"tconst": "tt1", "averageRating": "7.1", "numVotes": "5"}],
            "title.ratings", "batch1", row_count=1)
        write_bronze(rows, str(tmp_path), "title.ratings")
        parquet_file = tmp_path / "title.ratings.parquet"
        assert parquet_file.exists()
        count = duckdb.execute(
            f"SELECT COUNT(*) FROM read_parquet('{str(parquet_file).replace(chr(92), '/')}')"
        ).fetchone()[0]
        assert count == 1

    def test_write_bronze_empty_is_noop(self, tmp_path):
        write_bronze([], str(tmp_path), "title.ratings")
        assert not (tmp_path / "title.ratings.parquet").exists()

    def test_log_ingestion_metrics_appends_jsonl(self, tmp_path):
        log_root = str(tmp_path / "logs")
        log_ingestion_metrics("/data/ratings.tsv", "title.ratings", 3,
                              "batch1", log_root)
        log_ingestion_metrics("/data/ratings.tsv", "title.ratings", 3,
                              "batch1", log_root)
        with open(os.path.join(log_root, "ingestion_log.jsonl")) as f:
            lines = f.read().strip().splitlines()
        assert len(lines) == 2
        entry = json.loads(lines[0])
        assert entry["source_table"] == "title.ratings"
        assert entry["row_count"] == 3
        assert entry["batch_id"] == "batch1"


class TestIngestSingleSource:
    def test_happy_path(self, tmp_path):
        src = _write_file(tmp_path, "ratings.tsv", RATINGS_LINES)
        out_root = str(tmp_path / "out")
        log_root = str(tmp_path / "logs")
        count = ingest_single_source(src, "title.ratings", out_root, "batch1",
                                     log_root)
        assert count == 3
        assert os.path.exists(os.path.join(out_root, "title.ratings.parquet"))
        assert os.path.exists(os.path.join(log_root, "ingestion_log.jsonl"))

    def test_quarantines_bad_file(self, tmp_path):
        src = _write_file(tmp_path, "bad.tsv", ["tt1\t6.3"])
        out_root = str(tmp_path / "out")
        count = ingest_single_source(src, "title.ratings", out_root, "batch1")
        assert count == 0
        assert not os.path.exists(os.path.join(out_root, "title.ratings.parquet"))


class TestIngestAll:
    def test_ingest_all_with_subset(self, tmp_path):
        ratings = _write_file(tmp_path, "ratings.tsv", RATINGS_LINES)
        basics = _write_file(tmp_path, "basics.tsv", [
            "tt0000001\tshort\tCarmencita\tCarmencita\t0\t1894\t\\N\t1\tDocumentary",
        ])
        out_root = str(tmp_path / "out")
        results = ingest_all(
            {"title.ratings": ratings, "title.basics": basics},
            output_root=out_root,
        )
        assert results == {"title.ratings": 3, "title.basics": 1}
        assert os.path.exists(os.path.join(out_root, "title.ratings.parquet"))
        assert os.path.exists(os.path.join(out_root, "title.basics.parquet"))

    def test_unknown_source_skipped(self, tmp_path):
        results = ingest_all({"unknown.table": "/x.tsv"}, output_root=str(tmp_path))
        assert results == {}
