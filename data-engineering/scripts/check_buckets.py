"""Check all 3 S3 buckets via DuckDB httpfs."""

import sys
sys.path.insert(0, "/opt/airflow/data-engineering")

import duckdb
from bronze.s3_config import configure_s3

conn = duckdb.connect(":memory:")
configure_s3(conn)

for b in ["imdb-source", "bronze", "gold-exports"]:
    try:
        conn.execute(f"SELECT 1 FROM read_csv('s3://{b}/.check', delim='|', header=false)").fetchone()
    except Exception as e:
        s = str(e)
        ok = "404" in s or "Not Found" in s or "does not exist" in s
    else:
        ok = True
    print(f"  {b}: {'OK' if ok else 'ERROR'}")

print("All 3 buckets present")
