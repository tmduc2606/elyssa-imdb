# NOTE: This PySpark script is a parallel implementation to the DuckDB
# Airflow operators (orchestration/operators/bronze_operator.py).
# The canonical pipeline path is via DuckDB Airflow operators.
# Canonical path: orchestration/operators/bronze_operator.py

from datetime import datetime, timezone
import hashlib
import json
import uuid
import os
import sys

# ─── Ensure bronze module is importable ────────────────────────────
# When run via spark-submit, the working directory may not be on sys.path.
# Resolve from __file__: this file is in data-engineering/bronze/, so
# the parent (data-engineering/) needs to be on sys.path.
_de_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _de_root not in sys.path:
    sys.path.insert(0, _de_root)

from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, lit, when, current_timestamp, input_file_name
import pyspark.sql.types as T

from bronze.config import SOURCE_CONFIG, DEFAULT_OUTPUT_ROOT, DEFAULT_METADATA_ROOT
from bronze.quarantine import validate_source_file, compute_file_checksum

SPARK_APP_NAME = "ElyssaBronzeIngestion"

def create_spark_session(app_name: str = SPARK_APP_NAME) -> SparkSession:
    return SparkSession.builder \
        .appName(app_name) \
        .config("spark.sql.adaptive.enabled", "true") \
        .config("spark.sql.parquet.compression.codec", "snappy") \
        .config("spark.sql.session.timeZone", "UTC") \
        .getOrCreate()

def generate_batch_id() -> str:
    return uuid.uuid4().hex[:12]

def read_source(spark: SparkSession, file_path: str, source_name: str) -> DataFrame:
    cfg = SOURCE_CONFIG[source_name]
    reader = spark.read \
        .option("sep", cfg["delimiter"]) \
        .option("header", "false") \
        .option("emptyValue", "")
    if cfg.get("null_value") is not None:
        reader = reader.option("nullValue", cfg["null_value"])
    df = reader.csv(file_path)
    if len(df.columns) != len(cfg["columns"]):
        raise ValueError(
            f"Column count mismatch for {source_name}: "
            f"expected {len(cfg['columns'])}, got {len(df.columns)}"
        )
    for i, name in enumerate(cfg["columns"]):
        df = df.withColumnRenamed(f"_c{i}", name)
    return df

def add_metadata(df: DataFrame, source_name: str, batch_id: str,
                 row_count: int = 0, checksum: str = "") -> DataFrame:
    now_ts = datetime.now(timezone.utc).isoformat()
    return df \
        .withColumn("_source_file", input_file_name()) \
        .withColumn("_source_table", lit(source_name)) \
        .withColumn("_batch_id", lit(batch_id)) \
        .withColumn("_ingested_at", lit(now_ts)) \
        .withColumn("_row_count", lit(row_count)) \
        .withColumn("_checksum", lit(checksum))

def write_bronze(df: DataFrame, output_root: str, source_name: str) -> None:
    output_path = f"{output_root}/{source_name}"
    df \
        .repartition(1) \
        .write \
        .mode("append") \
        .format("parquet") \
        .option("compression", "snappy") \
        .save(output_path)

def log_ingestion_metrics(spark: SparkSession, file_path: str, source_name: str,
                          row_count: int, batch_id: str, log_root: str) -> None:
    row = spark.createDataFrame([{
        "batch_id": batch_id,
        "source_table": source_name,
        "source_file": file_path,
        "row_count": row_count,
        "ingested_at": datetime.now(timezone.utc).isoformat(),
        "status": "success"
    }])
    log_path = f"{log_root}/ingestion_log"
    row.write.mode("append").json(log_path)

def ingest_single_source(spark: SparkSession, file_path: str, source_name: str,
                         output_root: str, batch_id: str, log_root: str) -> int:
    print(f"[{batch_id}] Ingesting {source_name} from {file_path}")

    cfg = SOURCE_CONFIG[source_name]
    expected_columns = len(cfg["columns"])
    is_valid, error_msg, pre_count = validate_source_file(
        file_path, source_name, expected_columns
    )
    if not is_valid:
        print(f"[{batch_id}] QUARANTINED {source_name}: {error_msg}")
        return 0

    df = read_source(spark, file_path, source_name)
    checksum = compute_file_checksum(file_path)
    df = add_metadata(df, source_name, batch_id, row_count=0, checksum=checksum)
    row_count = df.count()
    write_bronze(df, output_root, source_name)
    log_ingestion_metrics(spark, file_path, source_name, row_count, batch_id, log_root)
    print(f"[{batch_id}] {source_name}: {row_count} rows ingested")
    return row_count

def ingest_all(sources: dict[str, str], output_root: str = DEFAULT_OUTPUT_ROOT,
               log_root: str = DEFAULT_METADATA_ROOT) -> dict[str, int]:
    batch_id = generate_batch_id()
    print(f"Bronze ingestion batch: {batch_id}")
    spark = create_spark_session()
    results = {}
    try:
        for source_name, file_path in sources.items():
            if source_name not in SOURCE_CONFIG:
                print(f"Unknown source: {source_name}, skipping")
                continue
            count = ingest_single_source(spark, file_path, source_name, output_root, batch_id, log_root)
            results[source_name] = count
    finally:
        spark.stop()
    print(f"Batch {batch_id} complete. Results: {json.dumps(results)}")
    return results

if __name__ == "__main__":
    import sys
    sources = {
        "title.akas": sys.argv[1],
        "title.basics": sys.argv[2],
        "title.crew": sys.argv[3],
        "title.episode": sys.argv[4],
        "title.principals": sys.argv[5],
        "title.ratings": sys.argv[6],
        "name.basics": sys.argv[7],
    }
    ingest_all(sources)
