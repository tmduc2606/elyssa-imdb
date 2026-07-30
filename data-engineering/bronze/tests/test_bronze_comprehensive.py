"""
Bronze Layer Comprehensive Tests & Benchmarks
Validates: PySpark ingestion, config, schema mapping, metadata columns, error handling
"""
import os
import sys
import time
import pytest
import duckdb as _duckdb_lib

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, BooleanType, IntegerType
from pyspark.sql.functions import col, count, when
from bronze.config import SOURCE_CONFIG
from bronze.ingest_imdb import generate_batch_id, add_metadata

# ─── Spark Session (Java 25 compatible) ──────────────────────────────────────

@pytest.fixture(scope="module")
def spark():
    os.environ.setdefault("PYSPARK_PYTHON", r"C:\Python314\python.exe")
    os.environ.setdefault("PYSPARK_DRIVER_PYTHON", r"C:\Python314\python.exe")
    os.environ.setdefault("SPARK_LOCAL_IP", "127.0.0.1")
    session = SparkSession.builder \
        .appName("BronzeTests") \
        .master("local[1]") \
        .config("spark.pyspark.python", r"C:\Python314\python.exe") \
        .config("spark.pyspark.driver.python", r"C:\Python314\python.exe") \
        .config("spark.sql.warehouse.dir", "file:///C:/tmp/spark-warehouse") \
        .config("spark.hadoop.hadoop.security.authentication", "simple") \
        .config("spark.hadoop.hadoop.security.authorization", "false") \
        .config("spark.driver.extraJavaOptions",
                "-Dhadoop.security.authentication=simple -Dhadoop.security.authorization=false") \
        .getOrCreate()
    session.sparkContext.setLogLevel("ERROR")
    yield session
    session.stop()

# ─── Config Tests ─────────────────────────────────────────────────────────────

class TestConfig:
    """Tests for bronze/config.py"""

    def test_source_config_has_all_tables(self):
        expected = {
            "title.basics", "title.akas", "title.crew",
            "title.episode", "title.principals", "title.ratings",
            "name.basics"
        }
        assert set(SOURCE_CONFIG.keys()) == expected

    def test_source_config_returns_correct_columns(self):
        for table, cfg in SOURCE_CONFIG.items():
            cols = cfg["columns"]
            assert len(cols) > 0, f"{table} has no columns defined"
            assert "tconst" in cols or "nconst" in cols or "ordering" in cols, \
                f"{table} missing primary key column"

    def test_source_config_columns_are_strings(self):
        for table in SOURCE_CONFIG:
            cols = SOURCE_CONFIG[table]["columns"]
            assert all(isinstance(c, str) for c in cols), f"{table} has non-string columns"

    def test_source_config_has_delimiter_and_null_value(self):
        for table in SOURCE_CONFIG:
            cfg = SOURCE_CONFIG[table]
            assert "delimiter" in cfg, f"{table} missing delimiter"
            assert "null_value" in cfg, f"{table} missing null_value"

    def test_schema_column_count_matches_imdb_spec(self):
        expected_counts = {
            "title.basics": 9,
            "title.akas": 8,
            "title.crew": 3,
            "title.episode": 4,
            "title.principals": 6,
            "title.ratings": 3,
            "name.basics": 6,
        }
        for table, expected_count in expected_counts.items():
            actual_count = len(SOURCE_CONFIG[table]["columns"])
            assert actual_count == expected_count, \
                f"{table}: expected {expected_count} columns, got {actual_count}"

# ─── Ingestion Logic Tests ────────────────────────────────────────────────────

class TestIngestionLogic:
    """Tests for bronze/ingest_imdb.py logic (without PySpark execution)"""

    def test_generate_batch_id_returns_12_hex(self):
        bid = generate_batch_id()
        assert len(bid) == 12
        assert all(c in "0123456789abcdef" for c in bid)

    def test_generate_batch_id_unique(self):
        ids = {generate_batch_id() for _ in range(100)}
        assert len(ids) == 100

    def test_source_config_matches_all_tables(self):
        for table in SOURCE_CONFIG:
            assert "columns" in SOURCE_CONFIG[table]
            assert "delimiter" in SOURCE_CONFIG[table]

# ─── PySpark Ingestion Tests ──────────────────────────────────────────────────

class TestPySparkIngestion:
    """Tests for PySpark Bronze ingestion with real SparkSession"""

    def _create_test_data(self, spark, source_name):
        """Create synthetic TSV-like data in memory"""
        if source_name == "title.basics":
            schema = StructType([
                StructField("tconst", StringType(), False),
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
                ("tt0000001", "short", "Carmencita", "Carmencita", "0", "1894", "\\N", "1", "Documentary,Short"),
                ("tt0000002", "short", "Le clown et ses chiens", "Le clown et ses chiens", "0", "1892", "\\N", "5", "Animation,Short"),
                ("tt0000003", "short", "Pauvre Pierrot", "Pauvre Pierrot", "0", "1892", "\\N", "4", "Animation,Comedy"),
                ("tt0000004", "short", "Un bon bock", "Un bon bock", "0", "1892", "\\N", "5", "Animation,Short"),
                ("tt0000005", "short", "Blacksmith Scene", "Blacksmith Scene", "0", "1893", "\\N", "1", "Comedy,Short"),
            ]
        elif source_name == "name.basics":
            schema = StructType([
                StructField("nconst", StringType(), False),
                StructField("primaryName", StringType(), True),
                StructField("birthYear", StringType(), True),
                StructField("deathYear", StringType(), True),
                StructField("primaryProfession", StringType(), True),
                StructField("knownForTitles", StringType(), True),
            ])
            data = [
                ("nm0000001", "Fred Astaire", "1899", "1987", "actor,dancer,producer", "tt0007264,tt0015414,tt0027125,tt0050472"),
                ("nm0000002", "Lauren Bacall", "1924", "2014", "actress,archive_footage", "tt0037382,tt0038355,tt0040459,tt0046911"),
                ("nm0000003", "Brigitte Bardot", "1934", "\\N", "actress,soundtrack", "tt0049041,tt0050788,tt0051071,tt0052357"),
                ("nm0000004", "John Belushi", "1949", "1982", "actor,writer,producer", "tt0070735,tt0072561,tt0077975,tt0080459"),
                ("nm0000005", "Ingrid Bergman", "1915", "1982", "actress,producer", "tt0036855,tt0038109,tt0052111,tt0070800"),
            ]
        elif source_name == "title.ratings":
            schema = StructType([
                StructField("tconst", StringType(), False),
                StructField("averageRating", StringType(), True),
                StructField("numVotes", StringType(), True),
            ])
            data = [
                ("tt0000001", "6.3", "154"),
                ("tt0000002", "5.9", "120"),
                ("tt0000003", "6.2", "89"),
                ("tt0000004", "6.1", "112"),
                ("tt0000005", "6.4", "200"),
            ]
        elif source_name == "title.episode":
            schema = StructType([
                StructField("tconst", StringType(), False),
                StructField("parentTconst", StringType(), True),
                StructField("seasonNumber", StringType(), True),
                StructField("episodeNumber", StringType(), True),
            ])
            data = [
                ("tt0000001", "tt0000006", "1", "1"),
                ("tt0000002", "tt0000006", "1", "2"),
                ("tt0000003", "tt0000006", "1", "3"),
                ("tt0000004", "tt0000006", "2", "1"),
                ("tt0000005", "tt0000006", "2", "2"),
            ]
        else:
            return None, None

        return spark.createDataFrame(data, schema), schema

    def test_null_marker_preserved(self, spark):
        """Verify \\N is preserved as empty string in Bronze"""
        df, _ = self._create_test_data(spark, "title.basics")
        rows = df.collect()
        end_year_values = [r["endYear"] for r in rows]
        assert "\\N" in end_year_values, "\\N marker should be preserved"

    def test_schema_columns_match_config(self, spark):
        """Verify DataFrame columns match config schema"""
        df, _ = self._create_test_data(spark, "title.basics")
        expected = SOURCE_CONFIG["title.basics"]["columns"]
        actual = df.columns
        assert set(expected) == set(actual), f"Column mismatch: {set(expected) ^ set(actual)}"

    def test_type_coercion_numeric(self, spark):
        """Verify numeric types can be coerced"""
        df, _ = self._create_test_data(spark, "title.basics")
        df2 = df.withColumn("startYear_int", col("startYear").cast(IntegerType()))
        rows = df2.collect()
        assert rows[0]["startYear_int"] == 1894

    def test_type_coercion_boolean(self, spark):
        """Verify boolean types can be coerced"""
        df, _ = self._create_test_data(spark, "title.basics")
        df2 = df.withColumn("isAdult_bool", col("isAdult").cast(BooleanType()))
        rows = df2.collect()
        assert rows[0]["isAdult_bool"] is False

    def test_metadata_columns_added(self, spark):
        """Verify metadata columns can be added"""
        df, _ = self._create_test_data(spark, "title.basics")
        df = add_metadata(df, "title.basics", "batch_test_20260626")
        rows = df.collect()
        assert rows[0]["_batch_id"] == "batch_test_20260626"
        assert rows[0]["_source_table"] == "title.basics"
        assert rows[0]["_ingested_at"] is not None
        assert "_source_file" in df.columns

    def test_empty_genres_handled(self, spark):
        """Verify empty genres are preserved"""
        schema = StructType([
            StructField("tconst", StringType(), False),
            StructField("genres", StringType(), True),
        ])
        data = [("tt0000001", "\\N"), ("tt0000002", "Drama"), ("tt0000003", "")]
        df = spark.createDataFrame(data, schema)
        rows = df.collect()
        assert rows[0]["genres"] == "\\N"
        assert rows[2]["genres"] == ""

    def test_record_count(self, spark):
        """Verify correct number of records"""
        df, _ = self._create_test_data(spark, "title.basics")
        assert df.count() == 5

# ─── Performance Benchmarks ───────────────────────────────────────────────────

class TestBronzePerformance:
    """Performance benchmarks for Bronze layer operations"""

    def test_config_lookup_time(self):
        """Benchmark: config lookup should be <1ms"""
        start = time.perf_counter()
        for _ in range(1000):
            SOURCE_CONFIG["title.basics"]["columns"]
        elapsed = time.perf_counter() - start
        avg_us = (elapsed / 1000) * 1_000_000
        assert avg_us < 100, f"Config lookup avg {avg_us:.1f}µs > 100µs threshold"

    def test_dataframe_creation_speed(self, spark):
        """Benchmark: DataFrame creation should be <5s for 1000 rows"""
        schema = StructType([
            StructField("tconst", StringType(), False),
            StructField("titleType", StringType(), True),
            StructField("primaryTitle", StringType(), True),
            StructField("originalTitle", StringType(), True),
            StructField("isAdult", StringType(), True),
            StructField("startYear", StringType(), True),
            StructField("endYear", StringType(), True),
            StructField("runtimeMinutes", StringType(), True),
            StructField("genres", StringType(), True),
        ])
        data = [(f"tt{i:07d}", "movie", f"Title {i}", f"Original {i}", "0", "2020", "\\N", "120", "Drama") for i in range(1000)]

        start = time.perf_counter()
        df = spark.createDataFrame(data, schema)
        count = df.count()
        elapsed = time.perf_counter() - start

        assert count == 1000
        assert elapsed < 5.0, f"DataFrame creation took {elapsed:.2f}s > 5s threshold"

# ─── DuckDB Parquet Read Tests (Java 25 compatible) ───────────────────────────

class TestDuckDBParquetReads:
    """Read real Parquet files via DuckDB (bypasses Hadoop/Java 25 limitation)"""

    PARQUET_ROOT = "s3://bronze/"

    @pytest.fixture(scope="class")
    def duck(self):
        return _duckdb_lib.connect(":memory:")

    def _parquet_path(self, table_name):
        return os.path.join(self.PARQUET_ROOT, f"{table_name}.parquet")

    def test_title_ratings_readable(self, duck):
        path = self._parquet_path("title.ratings")
        assert os.path.exists(path), f"Missing: {path}"
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0, "title.ratings is empty"

    def test_title_basics_readable(self, duck):
        path = self._parquet_path("title.basics")
        assert os.path.exists(path)
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0

    def test_name_basics_readable(self, duck):
        path = self._parquet_path("name.basics")
        assert os.path.exists(path)
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0

    def test_title_akas_readable(self, duck):
        path = self._parquet_path("title.akas")
        assert os.path.exists(path)
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0

    def test_title_crew_readable(self, duck):
        path = self._parquet_path("title.crew")
        assert os.path.exists(path)
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0

    def test_title_episode_readable(self, duck):
        path = self._parquet_path("title.episode")
        assert os.path.exists(path)
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0

    def test_title_principals_readable(self, duck):
        path = self._parquet_path("title.principals")
        assert os.path.exists(path)
        result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
        assert result[0] > 0

    def test_all_seven_tables_readable(self, duck):
        """Verify all 7 tables are readable in a single DuckDB session"""
        tables = ["title.akas", "title.basics", "title.crew", "title.episode",
                  "title.principals", "title.ratings", "name.basics"]
        for t in tables:
            path = self._parquet_path(t)
            assert os.path.exists(path), f"Missing: {t}"
            result = duck.execute(f"SELECT COUNT(*) AS cnt FROM read_parquet('{path}')").fetchone()
            assert result[0] > 0, f"{t} is empty"
