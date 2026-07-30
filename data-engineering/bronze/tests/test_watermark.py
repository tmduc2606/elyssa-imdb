import json
import os
import tempfile
import pytest

from bronze.watermark import (
    get_watermark, set_watermark, update_watermark, clear_watermark,
    list_watermarks, get_latest_watermark_from_df, DEFAULT_WATERMARK,
)


class TestWatermark:
    @pytest.fixture
    def wm_path(self):
        with tempfile.TemporaryDirectory() as d:
            yield os.path.join(d, "test_watermarks.json")

    def test_default_watermark_is_epoch(self):
        assert DEFAULT_WATERMARK == "1970-01-01T00:00:00+00:00"

    def test_get_watermark_returns_default_for_unknown(self, wm_path):
        assert get_watermark("unknown.table", wm_path) == DEFAULT_WATERMARK

    def test_set_and_get_watermark(self, wm_path):
        set_watermark("silver.title_basics", "2026-06-26T12:00:00+00:00", wm_path)
        result = get_watermark("silver.title_basics", wm_path)
        assert result == "2026-06-26T12:00:00+00:00"

    def test_set_watermark_overwrites(self, wm_path):
        set_watermark("silver.title_basics", "2026-06-26T10:00:00+00:00", wm_path)
        set_watermark("silver.title_basics", "2026-06-26T15:00:00+00:00", wm_path)
        result = get_watermark("silver.title_basics", wm_path)
        assert result == "2026-06-26T15:00:00+00:00"

    def test_multiple_tables_independent(self, wm_path):
        set_watermark("silver.title_basics", "ts1", wm_path)
        set_watermark("silver.name_basics", "ts2", wm_path)
        assert get_watermark("silver.title_basics", wm_path) == "ts1"
        assert get_watermark("silver.name_basics", wm_path) == "ts2"

    def test_clear_watermark_removes_entry(self, wm_path):
        set_watermark("silver.title_basics", "some_ts", wm_path)
        clear_watermark("silver.title_basics", wm_path)
        assert get_watermark("silver.title_basics", wm_path) == DEFAULT_WATERMARK

    def test_list_watermarks_returns_all(self, wm_path):
        set_watermark("t1", "ts1", wm_path)
        set_watermark("t2", "ts2", wm_path)
        all_wm = list_watermarks(wm_path)
        assert all_wm == {"t1": "ts1", "t2": "ts2"}

    def test_update_watermark_with_value(self, wm_path):
        result = update_watermark("silver.title_basics",
                                   "2026-06-26T12:00:00+00:00", wm_path)
        assert result == "2026-06-26T12:00:00+00:00"
        assert get_watermark("silver.title_basics", wm_path) == result

    def test_update_watermark_without_value(self, wm_path):
        result = update_watermark("silver.title_basics", None, wm_path)
        assert isinstance(result, str)
        assert result.endswith("+00:00") or result.endswith("Z") or "+" in result
        assert get_watermark("silver.title_basics", wm_path) == result

    def test_get_latest_watermark_from_df(self):
        rows = [
            {"tconst": "tt1", "ingested_at": "2026-06-26T10:00:00+00:00"},
            {"tconst": "tt2", "ingested_at": "2026-06-26T12:00:00+00:00"},
            {"tconst": "tt3", "ingested_at": "2026-06-26T11:00:00+00:00"},
        ]
        latest = get_latest_watermark_from_df(rows, "ingested_at")
        assert latest == "2026-06-26T12:00:00+00:00"

    def test_get_latest_watermark_empty_list(self):
        assert get_latest_watermark_from_df([], "ingested_at") is None

    def test_get_latest_watermark_none_values(self):
        rows = [
            {"tconst": "tt1", "ingested_at": None},
            {"tconst": "tt2", "ingested_at": "2026-06-26T12:00:00+00:00"},
        ]
        latest = get_latest_watermark_from_df(rows, "ingested_at")
        assert latest == "2026-06-26T12:00:00+00:00"

    def test_get_latest_watermark_all_none(self):
        rows = [
            {"tconst": "tt1", "ingested_at": None},
            {"tconst": "tt2", "ingested_at": None},
        ]
        assert get_latest_watermark_from_df(rows, "ingested_at") is None

    def test_watermark_file_created_automatically(self, wm_path):
        assert os.path.exists(wm_path) is False
        get_watermark("test", wm_path)
        assert os.path.exists(wm_path) is True

    def test_corrupted_watermark_file_returns_default(self, wm_path):
        os.makedirs(os.path.dirname(wm_path), exist_ok=True)
        with open(wm_path, "w") as f:
            f.write("not valid json{")
        result = get_watermark("test", wm_path)
        assert result == DEFAULT_WATERMARK

    def test_watermark_persistence(self, wm_path):
        set_watermark("t1", "v1", wm_path)
        set_watermark("t2", "v2", wm_path)
        loaded = list_watermarks(wm_path)
        assert loaded == {"t1": "v1", "t2": "v2"}


class TestWatermarkCleanup:
    @pytest.fixture
    def wm_path(self):
        with tempfile.TemporaryDirectory() as d:
            yield os.path.join(d, "test_watermarks.json")

    def test_clear_nonexistent_does_not_error(self, wm_path):
        clear_watermark("nonexistent.table", wm_path)
        assert True

    def test_clear_on_empty_file(self, wm_path):
        os.makedirs(os.path.dirname(wm_path), exist_ok=True)
        with open(wm_path, "w") as f:
            json.dump({}, f)
        clear_watermark("anything", wm_path)
        assert list_watermarks(wm_path) == {}
