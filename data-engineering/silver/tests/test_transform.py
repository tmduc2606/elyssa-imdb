from silver.transform import (
    null_to_empty, empty_to_null, cast_types, rename_to_silver,
    explode_array
)
from silver.upsert import SILVER_TABLE_DDL
from silver.fk_checks import FK_CHECKS

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType

def _spark():
    spark = SparkSession.builder.appName("test").master("local[1]").getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    return spark

def test_null_to_empty():
    spark = _spark()
    try:
        schema = StructType([StructField("a", StringType(), True), StructField("b", StringType(), True)])
        df = spark.createDataFrame([(None, "b")], schema)
        result = null_to_empty(df)
        rows = result.collect()
        assert rows[0]["a"] == "", "null should become empty string"
        assert rows[0]["b"] == "b"
    finally:
        spark.stop()

def test_empty_to_null():
    spark = _spark()
    try:
        schema = StructType([StructField("a", StringType(), True), StructField("b", StringType(), True)])
        df = spark.createDataFrame([("", "b"), (r"\N", "x")], schema)
        result = empty_to_null(df)
        rows = result.collect()
        assert rows[0]["a"] is None, "empty string should become null"
        assert rows[0]["b"] == "b"
        assert rows[1]["a"] is None, "literal \\N string should become null"
        assert rows[1]["b"] == "x"
    finally:
        spark.stop()

def test_cast_types_handles_basics():
    spark = _spark()
    try:
        schema = StructType([
            StructField("isAdult", StringType(), True),
            StructField("startYear", StringType(), True),
            StructField("titleType", StringType(), True),
        ])
        df = spark.createDataFrame([("1", "2020", "movie")], schema)
        result = cast_types(df, "title.basics")
        cols = set(result.columns)
        assert "is_adult" in cols
        assert "start_year" in cols
        assert "isAdult" not in cols
        assert "startYear" not in cols
    finally:
        spark.stop()

def test_rename_to_silver():
    spark = _spark()
    try:
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("parentTconst", StringType(), True),
        ])
        df = spark.createDataFrame([("tt0000001", "tt0000002")], schema)
        result = rename_to_silver(df, "title.episode")
        cols = set(result.columns)
        assert "parent_tconst" in cols
        assert "parentTconst" not in cols
    finally:
        spark.stop()

def test_explode_array_genres():
    spark = _spark()
    try:
        schema = StructType([
            StructField("tconst", StringType(), True),
            StructField("genres", StringType(), True),
        ])
        df = spark.createDataFrame([("tt0000001", "Drama|Comedy")], schema)
        results = explode_array(df, "title.basics")
        assert len(results) == 1, "expected 1 exploded table"
        target_table, exploded = results[0]
        assert target_table == "silver.title_genre"
        rows = exploded.collect()
        assert len(rows) == 2
        assert rows[0]["genre"] == "Drama"
        assert rows[1]["genre"] == "Comedy"
    finally:
        spark.stop()

def test_silver_ddl_config_has_all_tables():
    expected = {
        "silver.title_basics", "silver.title_rating", "silver.title_episode",
        "silver.title_akas", "silver.title_genre", "silver.title_akas_type",
        "silver.title_akas_attribute", "silver.title_director", "silver.title_writer",
        "silver.title_principal", "silver.title_principal_char",
        "silver.name_basics", "silver.name_profession", "silver.name_known_for_title",
    }
    assert set(SILVER_TABLE_DDL.keys()) == expected

def test_each_fk_check_has_valid_sql():
    for check in FK_CHECKS:
        assert "name" in check, f"Missing 'name' in {check}"
        assert "sql" in check, f"Missing 'sql' in {check}"
        assert "SELECT" in check["sql"].upper(), f"SQL missing SELECT in {check}"
        assert "threshold" in check, f"Missing 'threshold' in {check}"
