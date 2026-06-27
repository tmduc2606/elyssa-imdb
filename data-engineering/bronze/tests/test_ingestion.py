from bronze.config import SOURCE_CONFIG
from bronze.ingest_imdb import generate_batch_id, add_metadata, read_source, SPARK_APP_NAME

EXPECTED_ROW_COUNTS = {
    "title.akas": 57934300,
    "title.basics": 12593486,
    "title.crew": 12593486,
    "title.episode": 9731563,
    "title.principals": 100109752,
    "title.ratings": 1684492,
    "name.basics": 15432611,
}

NULL_PATTERN = r"\N"

def test_generate_batch_id():
    bid = generate_batch_id()
    assert isinstance(bid, str)
    assert len(bid) == 12

def test_source_config_has_all_tables():
    expected = {"title.akas", "title.basics", "title.crew", "title.episode",
                "title.principals", "title.ratings", "name.basics"}
    assert set(SOURCE_CONFIG.keys()) == expected

def test_each_source_has_required_keys():
    for name, cfg in SOURCE_CONFIG.items():
        assert "columns" in cfg, f"{name} missing columns"
        assert "delimiter" in cfg, f"{name} missing delimiter"
        assert cfg["delimiter"] == "\t", f"{name} delimiter must be tab"
        assert cfg["null_value"] is None, f"{name} null_value must be None (preserve raw fidelity in Bronze)"

def test_column_counts_match_imdb_spec():
    expected_counts = {
        "title.akas": 8,
        "title.basics": 9,
        "title.crew": 3,
        "title.episode": 4,
        "title.principals": 6,
        "title.ratings": 3,
        "name.basics": 6,
    }
    for name, cfg in SOURCE_CONFIG.items():
        assert len(cfg["columns"]) == expected_counts[name], \
            f"{name}: expected {expected_counts[name]} cols, got {len(cfg['columns'])}"

def test_metadata_columns():
    import pandas as pd
    from pyspark.sql import SparkSession
    spark = SparkSession.builder.appName(SPARK_APP_NAME).master("local[1]").getOrCreate()
    try:
        df = spark.createDataFrame([{"a": "1"}])
        df_md = add_metadata(df, "test_table", "abc123", row_count=42, checksum="abc123def456")
        md_cols = {"_source_file", "_source_table", "_batch_id", "_ingested_at", "_row_count", "_checksum"}
        actual = set(df_md.columns)
        assert md_cols.issubset(actual), f"Missing metadata cols: {md_cols - actual}"
        row = df_md.collect()[0]
        assert row["_row_count"] == 42
        assert row["_checksum"] == "abc123def456"
    finally:
        spark.stop()

def test_config_matches_duke_column_profiles():
    duke_basics_cols = ["tconst", "titleType", "primaryTitle", "originalTitle",
                        "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"]
    assert SOURCE_CONFIG["title.basics"]["columns"] == duke_basics_cols

    duke_akas_cols = ["titleId", "ordering", "title", "region", "language",
                      "types", "attributes", "isOriginalTitle"]
    assert SOURCE_CONFIG["title.akas"]["columns"] == duke_akas_cols
