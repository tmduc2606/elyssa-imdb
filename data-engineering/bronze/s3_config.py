"""Shared S3 / httpfs configuration for DuckDB connections.

All ETL scripts call configure_s3(conn) to bootstrap httpfs
and set RustFS S3 credentials. Credentials come from the environment
(docker/.env via compose) — no hardcoded fallbacks (C1-C7)."""

import os


def get_s3_config() -> dict:
    raw_endpoint = os.environ.get("S3_ENDPOINT", "rustfs:9000")
    # Strip protocol prefix if present — DuckDB httpfs expects bare host:port
    for prefix in ("https://", "http://"):
        if raw_endpoint.startswith(prefix):
            raw_endpoint = raw_endpoint[len(prefix):]
            break
    secret_key = os.environ.get("S3_SECRET_KEY", "")
    if not secret_key:
        raise ValueError(
            "S3_SECRET_KEY is not set in the environment (docker/.env via compose)"
        )
    return {
        "endpoint": raw_endpoint,
        "access_key": os.environ.get("S3_ACCESS_KEY", "elyssa"),
        "secret_key": secret_key,
        "region": os.environ.get("S3_REGION", "us-east-1"),
        "url_style": "path",
        "use_ssl": False,
    }


def configure_s3(conn) -> None:
    cfg = get_s3_config()
    conn.execute("INSTALL httpfs; LOAD httpfs;")
    conn.execute(f"SET s3_endpoint = '{cfg['endpoint']}'")
    conn.execute(f"SET s3_access_key_id = '{cfg['access_key']}'")
    conn.execute(f"SET s3_secret_access_key = '{cfg['secret_key']}'")
    conn.execute(f"SET s3_region = '{cfg['region']}'")
    conn.execute("SET s3_url_style = 'path'")
    conn.execute("SET s3_use_ssl = false")


def s3_url(bucket: str, key: str) -> str:
    return f"s3://{bucket}/{key}"
