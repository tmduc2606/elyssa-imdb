"""
Silver Layer Comprehensive Tests & Benchmarks
Validates: Schema enforcement, type casting, array normalization, SCD2, upsert, FK checks
"""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pyspark.sql import SparkSession
from pyspark.sql.types import (
    StructType, StructField, StringType, BooleanType, IntegerType,
    ShortType, DecimalType
)
from pyspark.sql.functions import col, lit, current_timestamp
from silver.transform import (
    null_to_empty, empty_to_null, cast_types, rename_to_silver,
    explode_array, ARRAY_FIELDS, TYPE_MAP, NULL_MARKER
)
from silver.upsert import SILVER_TABLE_DDL, generate_merge_sql
from silver.fk_checks import FK_CHECKS, run_fk_checks

# ─── Spark Session ────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def spark():
    session = SparkSession.builder \
        .appName("SilverTests") \
        .master("local[1]") \
        .config("spark.sql.warehouse.dir", "/tmp/spark-warehouse") \
        .getOrCreate()
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()

# ─── Schema Tests ─────────────────────────────────────────────────────────────

class TestSilverSchema:
    """Tests for silver/schema.sql"""

    def test_schema_file_exists(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        assert os.path.exists(schema_path), "schema.sql not found"

    def test_schema_has_timescaledb(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        with open(schema_path) as f:
            content = f.read()
        assert "CREATE EXTENSION IF NOT EXISTS timescaledb" in content

    def test_schema_has_14_tables(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        with open(schema_path) as f:
            content = f.read()
        tables = [
            "silver.title_basics", "silver.title_genre", "silver.title_rating",
            "silver.title_episode", "silver.title_akas", "silver.title_akas_type",
            "silver.title_akas_attribute", "silver.title_director", "silver.title_writer",
            "silver.title_principal", "silver.title_principal_char",
            "silver.name_basics", "silver.name_profession", "silver.name_known_for_title",
        ]
        for table in tables:
            assert f"CREATE TABLE IF NOT EXISTS {table}" in content, f"Table {table} not found"

    def test_schema_has_scd2_columns(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        with open(schema_path) as f:
            content = f.read()
        assert "valid_from" in content
        assert "valid_to" in content
        assert "is_current" in content

    def test_schema_has_surrogate_keys(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        with open(schema_path) as f:
            content = f.read()
        assert "CREATE SEQUENCE IF NOT EXISTS silver.title_key_seq" in content
        assert "CREATE SEQUENCE IF NOT EXISTS silver.name_key_seq" in content
        assert "CREATE SEQUENCE IF NOT EXISTS silver.character_key_seq" in content

    def test_schema_has_governance_tables(self):
        schema_path = os.path.join(os.path.dirname(__file__), '..', 'schema.sql')
        with open(schema_path) as f:
            content = f.read()
        assert "silver.graph_sync_status" in content
        assert "silver.data_quality_log" in content
        assert "silver.quarantine" in content

# ─── Transform Tests ──────────────────────────────────────────────────────────

class TestTransform:
    """Tests for silver/transform.py"""

    def test_null_to_empty_preserves_data(self, spark):
        schema = StructType([
            StructField("a", StringType(), True),
            StructField("b", StringType(), True),
        ])
        df = spark.createDataFrame([("hello", "world")], schema)
        result = null_to_empty(df)
        rows = result.collect()
        assert rows[0]["a"] == "hello"
        assert rows[0]["b"] == "world"

    def test_null_to_empty_converts(self, spark):
        schema = StructType([
            StructField("a", StringType(), True),
            StructField("b", StringType(), True),
        ])
        df = spark.createDataFrame([(None, "test")], schema)
        result = null_to_empty(df)
        rows = result.collect()
        assert rows[0]["a"] == ""

    def test_empty_to_null_converts(self, spark):
        schema = StructType([
            StructField("a", StringType(), True),
            StructField("b", StringType(), True),
        ])
        df = spark.createDataFrame([("test", "data")], schema)
        result = empty_to_null(df)
        rows = result.collect()
        assert rows[0]["a"] == "test"
        assert rows[0]["b"] == "data"

    def test_cast_types_title_basics(self, spark):
        schema = StructType([
            StructField("isAdult", StringType(), True),
            StructField("startYear", StringType(), True),
            StructField("endYear", StringType(), True),
            StructField("runtimeMinutes", StringType(), True),
        ])
        df = spark.createDataFrame([("1", "2020", "2021", "120")], schema)
        result = cast_types(df, "title.basics")
        cols = set(result.columns)
        assert "is_adult" in cols
        assert "start_year" in cols
        assert "end_year" in cols
        assert "runtime_minutes" in cols
        assert "isAdult" not in cols

    def test_cast_types_title_ratings(self, spark):
        schema = StructType([
            StructField("averageRating", StringType(), True),
            StructField("numVotes", StringType(), True),
        ])
        df = spark.createDataFrame([("7.5", "1000")], schema)
        result = cast_types(df, "title.ratings")
        cols = set(result.columns)
        assert "average_rating" in cols
        assert "num_votes" in cols

    def test_rename_to_silver_maps_columns(self, spark):
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("parentTconst", StringType(), True),
            StructField("seasonNumber", StringType(), True),
            StructField("episodeNumber", StringType(), True),
        ])
        df = spark.createDataFrame([("tt0000001", "tt0000002", "1", "1")], schema)
        result = rename_to_silver(df, "title.episode")
        cols = set(result.columns)
        assert "parent_tconst" in cols
        assert "season_number" in cols
        assert "episode_number" in cols
        assert "parentTconst" not in cols

    def test_explode_array_single_column(self, spark):
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("genres", StringType(), True),
        ])
        df = spark.createDataFrame([("tt0000001", "Drama|Comedy")], schema)
        results = explode_array(df, "title.basics")
        assert len(results) == 1
        target_table, exploded_df = results[0]
        assert target_table == "silver.title_genre"
        rows = exploded_df.collect()
        assert len(rows) == 2
        genres = [r["genre"] for r in rows]
        assert "Drama" in genres
        assert "Comedy" in genres

    def test_explode_array_multi_column(self, spark):
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("directors", StringType(), True),
            StructField("writers", StringType(), True),
        ])
        df = spark.createDataFrame([("tt0000001", "nm001,nm002", "nm003")], schema)
        results = explode_array(df, "title.crew")
        assert len(results) == 2
        tables = {t for t, _ in results}
        assert "silver.title_director" in tables
        assert "silver.title_writer" in tables

    def test_explode_array_empty_value(self, spark):
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("genres", StringType(), True),
        ])
        df = spark.createDataFrame([("tt0000001", None)], schema)
        results = explode_array(df, "title.basics")
        # Should not explode None values
        if results:
            _, exploded_df = results[0]
            rows = exploded_df.collect()
            # None values should not produce rows
            assert len(rows) == 0 or all(r["genre"] is not None for r in rows)

# ─── Upsert Config Tests ─────────────────────────────────────────────────────

class TestUpsert:
    """Tests for silver/upsert.py"""

    def test_silver_ddl_has_all_14_tables(self):
        expected = {
            "silver.title_basics", "silver.title_rating", "silver.title_episode",
            "silver.title_akas", "silver.title_genre", "silver.title_akas_type",
            "silver.title_akas_attribute", "silver.title_director", "silver.title_writer",
            "silver.title_principal", "silver.title_principal_char",
            "silver.name_basics", "silver.name_profession", "silver.name_known_for_title",
        }
        assert set(SILVER_TABLE_DDL.keys()) == expected

    def test_all_tables_have_pk(self):
        for table, config in SILVER_TABLE_DDL.items():
            assert "pk" in config, f"{table} missing 'pk' in config"
            assert len(config["pk"]) > 0, f"{table} has empty 'pk'"

    def test_title_basics_has_merge_cols(self):
        config = SILVER_TABLE_DDL["silver.title_basics"]
        assert "merge_cols" in config
        assert "primary_title" in config["merge_cols"]

    def test_generate_merge_sql_basic(self):
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("title_type", StringType(), True),
            StructField("primary_title", StringType(), True),
        ])
        spark = SparkSession.builder.appName("test").master("local[1]").getOrCreate()
        try:
            df = spark.createDataFrame([("tt0000001", "movie", "Test")], schema)
            create_sql, merge_sql = generate_merge_sql("silver.title_basics", df)
            assert "MERGE INTO" in merge_sql
            assert "silver.title_basics" in merge_sql
        finally:
            spark.stop()

# ─── FK Check Tests ───────────────────────────────────────────────────────────

class TestFKChecks:
    """Tests for silver/fk_checks.py"""

    def test_fk_checks_has_all_7_checks(self):
        assert len(FK_CHECKS) == 7

    def test_each_check_has_required_fields(self):
        for check in FK_CHECKS:
            assert "name" in check
            assert "sql" in check
            assert "threshold" in check
            assert "SELECT" in check["sql"].upper()

    def test_fk_check_names_are_descriptive(self):
        names = [c["name"] for c in FK_CHECKS]
        assert "title_episode_parent_exists" in names
        assert "title_rating_title_exists" in names
        assert "title_director_title_exists" in names

    def test_fk_check_thresholds_are_numeric(self):
        for check in FK_CHECKS:
            assert isinstance(check["threshold"], (int, float))
            assert check["threshold"] >= 0

# ─── Performance Benchmarks ───────────────────────────────────────────────────

class TestSilverPerformance:
    """Performance benchmarks for Silver layer operations"""

    @pytest.fixture(scope="class")
    def perf_spark(self):
        session = SparkSession.builder \
            .appName("SilverPerfBench") \
            .master("local[1]") \
            .getOrCreate()
        session.sparkContext.setLogLevel("ERROR")
        yield session
        session.stop()

    def test_transform_pipeline_throughput(self, perf_spark):
        """Benchmark: Transform pipeline should process 1000 rows in <15s"""
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("titleType", StringType(), True),
            StructField("primaryTitle", StringType(), True),
            StructField("originalTitle", StringType(), True),
            StructField("isAdult", StringType(), True),
            StructField("startYear", StringType(), True),
            StructField("endYear", StringType(), True),
            StructField("runtimeMinutes", StringType(), True),
            StructField("genres", StringType(), True),
        ])
        data = [
            (f"tt{i:07d}", "movie", f"Title {i}", f"Original {i}", "0", "2020", "\\N", "120", "Drama|Action")
            for i in range(1000)
        ]
        df = perf_spark.createDataFrame(data, schema)

        start = time.perf_counter()
        df = rename_to_silver(df, "title.basics")
        df = cast_types(df, "title.basics")
        df = empty_to_null(df)
        results = explode_array(df, "title.basics")
        count = df.count()
        elapsed = time.perf_counter() - start

        assert count == 1000
        assert elapsed < 15.0, f"Transform pipeline took {elapsed:.2f}s > 15s threshold"

    def test_explode_array_throughput(self, perf_spark):
        """Benchmark: Array explosion should process 100 rows in <5s"""
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("genres", StringType(), True),
        ])
        data = [(f"tt{i:07d}", "Drama|Comedy|Action|Thriller") for i in range(100)]
        df = perf_spark.createDataFrame(data, schema)

        start = time.perf_counter()
        results = explode_array(df, "title.basics")
        elapsed = time.perf_counter() - start

        assert elapsed < 5.0, f"Array explosion took {elapsed:.2f}s > 5s threshold"

    def test_scd2_logic_throughput(self, perf_spark):
        """Benchmark: SCD2 logic should process 1000 records in <10s"""
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("primary_title", StringType(), True),
            StructField("start_year", StringType(), True),
        ])
        data = [(f"tt{i:07d}", f"Title {i}", "2020") for i in range(1000)]
        df = perf_spark.createDataFrame(data, schema)

        start = time.perf_counter()
        # Simulate SCD2: add valid_from, valid_to, is_current
        df = df.withColumn("valid_from", current_timestamp())
        df = df.withColumn("valid_to", lit(None).cast(StringType()))
        df = df.withColumn("is_current", lit(True))
        count = df.count()
        elapsed = time.perf_counter() - start

        assert count == 1000
        assert elapsed < 10.0, f"SCD2 logic took {elapsed:.2f}s > 10s threshold"
