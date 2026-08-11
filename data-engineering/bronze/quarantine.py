"""Source-file validation and quarantine helpers (pure Python, no PySpark).

Used by the legacy standalone ingestion script (ingest_imdb.py):
- validate_source_file: checks existence, non-emptiness, and column-count
  sanity of the first non-empty line, and returns a full row pre-count.
- compute_file_checksum: streaming SHA-256 of the raw file bytes.
"""

import hashlib
import os
from typing import Tuple


def validate_source_file(
    file_path: str,
    source_name: str,
    expected_columns: int,
) -> Tuple[bool, str, int]:
    """Return (is_valid, error_msg, pre_count).

    A file is quarantined (is_valid=False) when it is missing, empty, or
    when the first non-empty line does not match the expected column count.
    """
    if not os.path.exists(file_path):
        return False, f"File not found: {file_path}", 0

    row_count = 0
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            if not line.strip():
                continue
            row_count += 1
            if row_count == 1:
                actual = line.count("\t") + 1
                if actual != expected_columns:
                    return False, (
                        f"Column count mismatch for {source_name}: "
                        f"expected {expected_columns}, got {actual}"
                    ), 0

    if row_count == 0:
        return False, f"Empty file: {file_path}", 0

    return True, "", row_count


def compute_file_checksum(file_path: str) -> str:
    """Streaming SHA-256 hex digest of the file contents."""
    digest = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
