import json
import os
from datetime import datetime, timezone
from typing import Optional

WATERMARK_FILE = "bronze/logs/watermarks.json"
DEFAULT_WATERMARK = "1970-01-01T00:00:00+00:00"


def _ensure_file(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w") as f:
            json.dump({}, f)


def _load_watermarks(path: str = WATERMARK_FILE) -> dict[str, str]:
    _ensure_file(path)
    try:
        with open(path, "r") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_watermarks(data: dict[str, str], path: str = WATERMARK_FILE) -> None:
    _ensure_file(path)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def get_watermark(source_table: str, path: str = WATERMARK_FILE) -> str:
    watermarks = _load_watermarks(path)
    return watermarks.get(source_table, DEFAULT_WATERMARK)


def set_watermark(source_table: str, watermark: str,
                  path: str = WATERMARK_FILE) -> None:
    watermarks = _load_watermarks(path)
    watermarks[source_table] = watermark
    _save_watermarks(watermarks, path)


def update_watermark(source_table: str,
                     batch_watermark: Optional[str] = None,
                     path: str = WATERMARK_FILE) -> str:
    if batch_watermark:
        set_watermark(source_table, batch_watermark, path)
        return batch_watermark
    now_ts = datetime.now(timezone.utc).isoformat()
    set_watermark(source_table, now_ts, path)
    return now_ts


def get_latest_watermark_from_df(df_rows: list[dict],
                                  watermark_column: str) -> Optional[str]:
    if not df_rows or not watermark_column:
        return None
    max_watermark = None
    for row in df_rows:
        val = row.get(watermark_column)
        if val is not None and (max_watermark is None or str(val) > max_watermark):
            max_watermark = str(val)
    return max_watermark


def clear_watermark(source_table: str, path: str = WATERMARK_FILE) -> None:
    watermarks = _load_watermarks(path)
    watermarks.pop(source_table, None)
    _save_watermarks(watermarks, path)


def list_watermarks(path: str = WATERMARK_FILE) -> dict[str, str]:
    return dict(_load_watermarks(path))
