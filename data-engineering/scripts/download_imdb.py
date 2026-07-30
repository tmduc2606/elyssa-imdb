#!/usr/bin/env python3
"""Download IMDb .tsv.gz files directly to RustFS S3 via HTTP PUT (streaming).

Usage:
    python scripts/download_imdb.py

Requires: requests library (pip install requests)
S3 endpoint defaults to http://rustfs:9000, overridden by S3_ENDPOINT env var.
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://rustfs:9000").rstrip("/")
BUCKET = "imdb-source"
BASE_URL = "https://datasets.imdbws.com"

FILES = [
    "title.basics.tsv.gz",
    "title.akas.tsv.gz",
    "title.crew.tsv.gz",
    "title.episode.tsv.gz",
    "title.principals.tsv.gz",
    "title.ratings.tsv.gz",
    "name.basics.tsv.gz",
]


def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)


def download_and_upload(filename: str) -> dict:
    url = f"{BASE_URL}/{filename}"
    put_url = f"{S3_ENDPOINT}/{BUCKET}/{filename}"
    log(f"Downloading {url}")

    sha256 = hashlib.sha256()
    total_bytes = 0
    start = time.time()

    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    def content_iter():
        nonlocal total_bytes
        for chunk in resp.iter_content(chunk_size=65536):
            if chunk:
                sha256.update(chunk)
                total_bytes += len(chunk)
                yield chunk

    put_resp = requests.put(put_url, data=content_iter(), timeout=600)
    put_resp.raise_for_status()

    elapsed = time.time() - start
    digest = sha256.hexdigest()
    rate_mbps = (total_bytes / (1024 * 1024)) / elapsed if elapsed > 0 else 0

    log(f"  {filename}: {total_bytes / (1024*1024):.1f} MB, "
        f"sha256={digest[:16]}..., {elapsed:.1f}s ({rate_mbps:.1f} MB/s)")

    return {
        "filename": filename,
        "size_bytes": total_bytes,
        "sha256": digest,
        "elapsed_s": round(elapsed, 1),
        "rate_mbps": round(rate_mbps, 1),
    }


def main():
    log(f"IMDb Download → {S3_ENDPOINT}/{BUCKET}/")
    log(f"Source: {BASE_URL}")
    log(f"Files: {len(FILES)}")

    results = []
    total_bytes = 0
    total_time = 0.0
    failures = []

    for fname in FILES:
        try:
            meta = download_and_upload(fname)
            results.append(meta)
            total_bytes += meta["size_bytes"]
            total_time += meta["elapsed_s"]
        except Exception as e:
            log(f"  FAILED {fname}: {e}")
            failures.append({"filename": fname, "error": str(e)})

    meta = {
        "batch_id": datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S"),
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "source_url": BASE_URL,
        "s3_endpoint": S3_ENDPOINT,
        "bucket": BUCKET,
        "files": results,
        "failures": failures,
        "summary": {
            "total_files": len(results),
            "total_bytes": total_bytes,
            "total_size_gb": round(total_bytes / (1024 ** 3), 2),
            "total_time_s": round(total_time, 1),
            "failures": len(failures),
        },
    }

    meta_url = f"{S3_ENDPOINT}/{BUCKET}/download_metadata.json"
    try:
        resp = requests.put(meta_url, data=json.dumps(meta, indent=2), timeout=30)
        resp.raise_for_status()
        log(f"Metadata written to {meta_url}")
    except Exception as e:
        log(f"WARN: Could not write metadata: {e}")

    total_gb = total_bytes / (1024 ** 3)
    log(f"Download complete: {len(results)} files, {total_gb:.2f} GB, "
        f"{total_time:.1f}s total, {len(failures)} failures")

    if failures:
        log(f"FAILURES: {len(failures)} files failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
