"""Shared S3 / httpfs configuration for DuckDB connections.
    
All ETL scripts call configure_s3(conn) to bootstrap httpfs
and set RustFS S3 credentials. Environment variables override defaults."""

import os


def get_s3_config() -> dict:
    return {
        "endpoint": os.environ.get("S3_ENDPOINT", "rustfs:9000"),
        "access_key": os.environ.get("S3_ACCESS_KEY", "elyssa"),
        "secret_key": os.environ.get("S3_SECRET_KEY", "elyssa_s3_2026"),
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
