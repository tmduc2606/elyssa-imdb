#!/usr/bin/env python3
"""Download IMDb .tsv.gz files to RustFS S3 via boto3 (AWS V4 signing).

Usage:
    python scripts/download_imdb.py

Requires: boto3, requests
S3 endpoint defaults to http://rustfs:9000, overridden by S3_ENDPOINT env var.
"""

import hashlib
import io
import json
import os
import time
from datetime import datetime, timezone

import boto3
import requests
from botocore.config import Config

S3_ENDPOINT = os.environ.get("S3_ENDPOINT", "http://rustfs:9000").rstrip("/")
S3_ACCESS_KEY = os.environ.get("S3_ACCESS_KEY", "elyssa")
S3_SECRET_KEY = os.environ.get("S3_SECRET_KEY", "elyssa_s3_2026")
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

s3_client = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_ACCESS_KEY,
    aws_secret_access_key=S3_SECRET_KEY,
    config=Config(signature_version="s3v4"),
    region_name="us-east-1",
)


def log(msg: str):
    ts = datetime.now(timezone.utc).isoformat()
    print(f"[{ts}] {msg}", flush=True)


def download_and_upload(filename: str) -> dict:
    url = f"{BASE_URL}/{filename}"
    log(f"Downloading {url}")

    sha256 = hashlib.sha256()
    total_bytes = 0
    start = time.time()

    resp = requests.get(url, stream=True, timeout=300)
    resp.raise_for_status()

    buf = io.BytesIO()
    for chunk in resp.iter_content(chunk_size=65536):
        if chunk:
            buf.write(chunk)
            sha256.update(chunk)
            total_bytes += len(chunk)

    buf.seek(0)
    s3_client.put_object(Bucket=BUCKET, Key=filename, Body=buf)
    buf.close()

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

    try:
        s3_client.put_object(
            Bucket=BUCKET,
            Key="download_metadata.json",
            Body=json.dumps(meta, indent=2).encode(),
        )
        log(f"Metadata written to s3://{BUCKET}/download_metadata.json")
    except Exception as e:
        log(f"WARN: Could not write metadata: {e}")

    total_gb = total_bytes / (1024 ** 3)
    log(f"Download complete: {len(results)} files, {total_gb:.2f} GB, "
        f"{total_time:.1f}s total, {len(failures)} failures")

    if failures:
        log(f"FAILURES: {len(failures)} files failed")
        sys.exit(1)


if __name__ == "__main__":
    import sys
    main()
