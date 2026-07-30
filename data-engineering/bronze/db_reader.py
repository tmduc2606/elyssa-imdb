from datetime import datetime, timezone
from typing import Optional, Generator
import json
import uuid

from pyspark.sql import SparkSession, DataFrame, Row
from pyspark.sql.functions import lit
from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, ShortType,
    DecimalType, BooleanType, DateType,
)
import duckdb as _duckdb_lib
import psycopg2
import psycopg2.extras

from bronze.db_configs import (
    DatabaseConnection, SourceTableDef, DuckDBConfig,
    POSTGRESQL_CONFIG, DUCKDB_CONFIG, DB_SOURCE_TABLES,
    DUCKDB_PARQUET_SOURCES,
    DEFAULT_DB_OUTPUT_ROOT, DEFAULT_DB_METADATA_ROOT,
)
from bronze.db_schema_map import (
    map_row_to_bronze, get_bronze_columns, get_db_columns,
    DB_TO_BRONZE_COLUMN_MAP,
)

PG_TYPE_MAP: dict[str, type] = {
    "int2": ShortType,
    "int4": IntegerType,
    "int8": IntegerType,
    "numeric": lambda: DecimalType(12, 2),
    "float4": lambda: DecimalType(6, 2),
    "float8": lambda: DecimalType(12, 2),
    "bool": BooleanType,
    "date": DateType,
    "varchar": StringType,
    "text": StringType,
    "name": StringType,
    "bpchar": StringType,
    "timestamptz": StringType,
    "timestamp": StringType,
}


def _generate_batch_id() -> str:
    return uuid.uuid4().hex[:12]


def _get_pg_type(col_type_oid: int, conn) -> str:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT typname FROM pg_type WHERE oid = %s",
            (col_type_oid,),
        )
        row = cur.fetchone()
        return row[0] if row else "text"


def infer_spark_schema(conn, table_schema: str, table_name: str,
                       source_name: str) -> StructType:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT a.attname, a.atttypid, a.attnotnull
            FROM pg_catalog.pg_attribute a
            JOIN pg_catalog.pg_class c ON a.attrelid = c.oid
            JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = %s
              AND c.relname = %s
              AND a.attnum > 0
              AND NOT a.attisdropped
            ORDER BY a.attnum
            """,
            (table_schema, table_name),
        )
        pg_columns = cur.fetchall()

    bronze_col_map = DB_TO_BRONZE_COLUMN_MAP.get(source_name, {})
    fields = []
    for col_name, col_type_oid, not_null in pg_columns:
        if col_name not in bronze_col_map:
            continue
        type_name = _get_pg_type(col_type_oid, conn)
        spark_type_cls = PG_TYPE_MAP.get(type_name, StringType)
        spark_type = spark_type_cls() if callable(spark_type_cls) else spark_type_cls
        is_nullable = not not_null
        bronze_name = bronze_col_map[col_name]
        fields.append(StructField(bronze_name, spark_type, is_nullable))

    return StructType(fields)


class DatabaseReader:
    def __init__(
        self,
        connection_config: Optional[DatabaseConnection] = None,
        spark: Optional[SparkSession] = None,
    ):
        self.config = connection_config or POSTGRESQL_CONFIG
        self.spark = spark or SparkSession.builder \
            .appName("ElyssaDBReader") \
            .config("spark.sql.adaptive.enabled", "true") \
            .getOrCreate()

    def _connect(self):
        return psycopg2.connect(
            host=self.config.host,
            port=self.config.port,
            dbname=self.config.database,
            user=self.config.user,
            password=self.config.password,
        )

    def get_row_count(self, table_def: SourceTableDef) -> int:
        conn = self._connect()
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {table_def.source_table}")
                return cur.fetchone()[0]
        finally:
            conn.close()

    def read_table_batches(
        self, table_def: SourceTableDef,
    ) -> Generator[list[dict], None, None]:
        conn = self._connect()
        try:
            col_list = ", ".join(table_def.columns)
            query = f"SELECT {col_list} FROM {table_def.source_table} ORDER BY {table_def.id_column}"
            with conn.cursor(name="bronze_cursor", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.itersize = table_def.batch_size
                cur.execute(query)
                batch = []
                for row in cur:
                    batch.append(dict(row))
                    if len(batch) >= table_def.batch_size:
                        yield batch
                        batch = []
                if batch:
                    yield batch
        finally:
            conn.close()

    def read_table(
        self, table_def: SourceTableDef,
        batch_id: str,
    ) -> DataFrame:
        bronze_name = table_def.bronze_name
        rows = []
        for batch in self.read_table_batches(table_def):
            for row in batch:
                bronze_row = map_row_to_bronze(row, bronze_name)
                rows.append(bronze_row)

        if not rows:
            return self.spark.createDataFrame(
                [], self._empty_schema(bronze_name),
            )

        conn = self._connect()
        try:
            spark_schema = infer_spark_schema(
                conn, self.config.schema,
                table_def.source_table.split(".")[-1],
                bronze_name,
            )
        finally:
            conn.close()

        df = self.spark.createDataFrame(rows, schema=spark_schema)
        return self._add_metadata(df, bronze_name, batch_id)

    def read_incremental(
        self, table_def: SourceTableDef,
        last_watermark: Optional[str],
        batch_id: str,
    ) -> DataFrame:
        if not table_def.watermark_column or not last_watermark:
            return self.read_table(table_def, batch_id)

        bronze_name = table_def.bronze_name
        conn = self._connect()
        try:
            col_list = ", ".join(table_def.columns)
            query = (
                f"SELECT {col_list} FROM {table_def.source_table} "
                f"WHERE {table_def.watermark_column} > %s "
                f"ORDER BY {table_def.id_column}"
            )
            rows = []
            with conn.cursor(name="incremental_cursor", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.itersize = table_def.batch_size
                cur.execute(query, (last_watermark,))
                for row in cur:
                    bronze_row = map_row_to_bronze(dict(row), bronze_name)
                    rows.append(bronze_row)

            if not rows:
                return self.spark.createDataFrame(
                    [], self._empty_schema(bronze_name),
                )

            spark_schema = infer_spark_schema(
                conn, self.config.schema,
                table_def.source_table.split(".")[-1],
                bronze_name,
            )
            df = self.spark.createDataFrame(rows, schema=spark_schema)
            return self._add_metadata(df, bronze_name, batch_id)
        finally:
            conn.close()

    def read_query(self, query: str, bronze_name: str, batch_id: str) -> DataFrame:
        conn = self._connect()
        try:
            rows = []
            with conn.cursor(name="query_cursor", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.itersize = 50000
                cur.execute(query)
                for row in cur:
                    bronze_row = map_row_to_bronze(dict(row), bronze_name)
                    rows.append(bronze_row)

            if not rows:
                return self.spark.createDataFrame(
                    [], self._empty_schema(bronze_name),
                )

            spark_schema = infer_spark_schema(
                conn, self.config.schema,
                "", bronze_name,
            )
            df = self.spark.createDataFrame(rows, schema=spark_schema)
            return self._add_metadata(df, bronze_name, batch_id)
        finally:
            conn.close()

    def _add_metadata(self, df: DataFrame, source_name: str, batch_id: str) -> DataFrame:
        now_ts = datetime.now(timezone.utc).isoformat()
        source_uri = f"postgresql://{self.config.host}:{self.config.port}/{self.config.database}"
        return df \
            .withColumn("_source_file", lit(source_uri)) \
            .withColumn("_source_table", lit(source_name)) \
            .withColumn("_batch_id", lit(batch_id)) \
            .withColumn("_ingested_at", lit(now_ts))

    def _empty_schema(self, source_name: str) -> StructType:
        cols = get_bronze_columns(source_name)
        fields = [StructField(c, StringType(), True) for c in cols]
        md_fields = [
            StructField("_source_file", StringType(), True),
            StructField("_source_table", StringType(), True),
            StructField("_batch_id", StringType(), True),
            StructField("_ingested_at", StringType(), True),
        ]
        return StructType(fields + md_fields)


class DuckDBReader:
    def __init__(
        self,
        duckdb_config: Optional[DuckDBConfig] = None,
        spark: Optional[SparkSession] = None,
    ):
        self.config = duckdb_config or DUCKDB_CONFIG
        self.spark = spark or SparkSession.builder \
            .appName("ElyssaDuckDBReader") \
            .config("spark.sql.adaptive.enabled", "true") \
            .getOrCreate()
        self._duck = _duckdb_lib.connect(":memory:")
        from bronze.s3_config import configure_s3
        configure_s3(self._duck)
        self._duck.execute(f"SET threads = {self.config.threads}")
        self._duck.execute(f"SET memory_limit = '{self.config.memory_limit_mb}MB'")

    def close(self):
        self._duck.close()

    def get_row_count(self, table_def: SourceTableDef) -> int:
        parquet_path = table_def.source_table
        return self._duck.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
        ).fetchone()[0]

    def read_table(
        self, table_def: SourceTableDef,
        batch_id: str,
    ) -> DataFrame:
        bronze_name = table_def.bronze_name
        parquet_path = table_def.source_table
        col_list = ", ".join(table_def.columns)

        result = self._duck.execute(
            f"SELECT {col_list} FROM read_parquet('{parquet_path}') "
            f"ORDER BY {table_def.id_column}"
        )
        rows = [dict(zip([desc[0] for desc in result.description], row))
                for row in result.fetchall()]

        if not rows:
            return self.spark.createDataFrame(
                [], self._empty_schema(bronze_name),
            )

        spark_schema = self._infer_schema(table_def, bronze_name)
        df = self.spark.createDataFrame(rows, schema=spark_schema)
        return self._add_metadata(df, bronze_name, batch_id, parquet_path)

    def read_query(self, query: str, bronze_name: str, batch_id: str,
                   parquet_path: str = "") -> DataFrame:
        result = self._duck.execute(query)
        rows = [dict(zip([desc[0] for desc in result.description], row))
                for row in result.fetchall()]

        if not rows:
            return self.spark.createDataFrame(
                [], self._empty_schema(bronze_name),
            )

        df = self.spark.createDataFrame(rows)
        return self._add_metadata(df, bronze_name, batch_id, parquet_path)

    def _infer_schema(self, table_def: SourceTableDef,
                      source_name: str) -> StructType:
        parquet_path = table_def.source_table
        duck_columns = self._duck.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchall()

        bronze_col_map = DB_TO_BRONZE_COLUMN_MAP.get(source_name, {})
        duck_type_map = {
            "BIGINT": IntegerType, "INTEGER": IntegerType,
            "SMALLINT": ShortType, "TINYINT": ShortType,
            "BOOLEAN": BooleanType, "DATE": DateType,
            "DOUBLE": lambda: DecimalType(12, 2),
            "FLOAT": lambda: DecimalType(6, 2),
            "VARCHAR": StringType, "TEXT": StringType,
        }
        fields = []
        col_names = [c[0] for c in duck_columns]
        for col_name in col_names:
            if col_name not in bronze_col_map:
                continue
            duck_col_info = [c for c in duck_columns if c[0] == col_name]
            if not duck_col_info:
                continue
            duck_type_str = duck_col_info[0][1].split("(")[0].upper()
            spark_type_cls = duck_type_map.get(duck_type_str, StringType)
            spark_type = spark_type_cls() if callable(spark_type_cls) else spark_type_cls
            bronze_name = bronze_col_map.get(col_name, col_name)
            fields.append(StructField(bronze_name, spark_type, True))

        return StructType(fields)

    def _add_metadata(self, df: DataFrame, source_name: str,
                      batch_id: str, source_path: str) -> DataFrame:
        now_ts = datetime.now(timezone.utc).isoformat()
        return df \
            .withColumn("_source_file", lit(source_path)) \
            .withColumn("_source_table", lit(source_name)) \
            .withColumn("_batch_id", lit(batch_id)) \
            .withColumn("_ingested_at", lit(now_ts))

    def _empty_schema(self, source_name: str) -> StructType:
        cols = get_bronze_columns(source_name)
        fields = [StructField(c, StringType(), True) for c in cols]
        md_fields = [
            StructField("_source_file", StringType(), True),
            StructField("_source_table", StringType(), True),
            StructField("_batch_id", StringType(), True),
            StructField("_ingested_at", StringType(), True),
        ]
        return StructType(fields + md_fields)


def ingest_from_db(
    table_names: Optional[list[str]] = None,
    output_root: str = DEFAULT_DB_OUTPUT_ROOT,
    log_root: str = DEFAULT_DB_METADATA_ROOT,
    connection_config: Optional[DatabaseConnection] = None,
    source_type: str = "postgresql",
) -> dict[str, int]:
    batch_id = _generate_batch_id()
    print(f"DB ingestion batch: {batch_id} (source: {source_type})")

    if source_type == "duckdb":
        sources_dict = DUCKDB_PARQUET_SOURCES
        reader = DuckDBReader()
    else:
        sources_dict = DB_SOURCE_TABLES
        reader = DatabaseReader(connection_config=connection_config)

    results = {}
    sources = {
        name: cfg for name, cfg in sources_dict.items()
        if table_names is None or name in table_names
    }

    for bronze_name, table_def in sources.items():
        print(f"[{batch_id}] Ingesting {bronze_name} from {table_def.source_table}")
        df = reader.read_table(table_def, batch_id)
        row_count = df.count()
        output_path = f"{output_root}/{bronze_name}"
        df \
            .repartition(1) \
            .write \
            .mode("append") \
            .format("parquet") \
            .option("compression", "snappy") \
            .save(output_path)
        results[bronze_name] = row_count
        print(f"[{batch_id}] {bronze_name}: {row_count} rows ingested")

    if source_type == "duckdb":
        reader.close()

    print(f"Batch {batch_id} complete. Results: {json.dumps(results)}")
    return results


if __name__ == "__main__":
    import sys
    tables = sys.argv[1:] if len(sys.argv) > 1 else None
    ingest_from_db(tables)
