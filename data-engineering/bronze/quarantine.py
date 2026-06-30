"""
Quarantine validator for Bronze ingestion.

Validates each source file before ingestion. Rejects files with:
- Column count mismatch
- Corrupt gzip (unreadable)
- Zero rows

Quarantined records are written to bronze/quarantine/ with error metadata.
"""

import gzip
import hashlib
import json
import os
from datetime import datetime, timezone
from typing import Optional


def compute_file_checksum(file_path: str) -> str:
    """Compute SHA-256 checksum of a file's contents."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def validate_gzip(file_path: str) -> tuple[bool, Optional[str]]:
    """Check if a .tsv.gz file is corrupt."""
    if not file_path.endswith(".gz"):
        return True, None
    try:
        with gzip.open(file_path, "rt", encoding="utf-8") as f:
            f.read(1024)
        return True, None
    except (gzip.BadGzipFile, OSError, EOFError) as e:
        return False, f"Corrupt gzip: {e}"


def validate_row_count(file_path: str, expected_columns: int, delimiter: str = "\t") -> tuple[bool, Optional[str], int]:
    """Validate that the file has the expected column count and at least one row."""
    import gzip
    try:
        opener = gzip.open if file_path.endswith(".gz") else open
        with opener(file_path, "rt", encoding="utf-8") as f:
            first_line = f.readline().strip()
            if not first_line:
                return False, "File is empty (no header/data)", 0
            actual_columns = len(first_line.split(delimiter))
            if actual_columns != expected_columns:
                return False, f"Column count mismatch: expected {expected_columns}, got {actual_columns}", 0
            # Count remaining rows
            row_count = 1
            for _ in f:
                row_count += 1
            return True, None, row_count
    except Exception as e:
        return False, f"Read error: {e}", 0


def quarantine_file(
    file_path: str,
    source_name: str,
    error_message: str,
    quarantine_root: str = "bronze/quarantine",
) -> str:
    """Write a quarantined file record with error metadata."""
    os.makedirs(quarantine_root, exist_ok=True)
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    checksum = compute_file_checksum(file_path)

    quarantine_record = {
        "quarantine_id": f"{source_name}_{batch_id}",
        "source_name": source_name,
        "original_file": file_path,
        "checksum": checksum,
        "error_message": error_message,
        "quarantined_at": datetime.now(timezone.utc).isoformat(),
        "original_record": None,
    }

    quarantine_path = os.path.join(quarantine_root, f"{source_name}_{batch_id}.json")
    with open(quarantine_path, "w", encoding="utf-8") as f:
        json.dump(quarantine_record, f, indent=2)

    return quarantine_path


def validate_source_file(
    file_path: str,
    source_name: str,
    expected_columns: int,
    quarantine_root: str = "bronze/quarantine",
) -> tuple[bool, Optional[str], int]:
    """
    Full validation of a source file.
    Returns: (is_valid, error_message, row_count)
    """
    # 1. Check gzip integrity
    gz_ok, gz_err = validate_gzip(file_path)
    if not gz_ok:
        quarantine_file(file_path, source_name, gz_err, quarantine_root)
        return False, gz_err, 0

    # 2. Check row count and column count
    rc_ok, rc_err, row_count = validate_row_count(file_path, expected_columns)
    if not rc_ok:
        quarantine_file(file_path, source_name, rc_err, quarantine_root)
        return False, rc_err, 0

    return True, None, row_count
