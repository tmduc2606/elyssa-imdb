"""Bronze source configuration contract tests."""

from bronze.config import SOURCE_CONFIG


def test_source_config_has_all_tables():
    expected = {
        "title.akas", "title.basics", "title.crew",
        "title.episode", "title.principals", "title.ratings",
        "name.basics",
    }
    assert set(SOURCE_CONFIG.keys()) == expected


def test_each_source_has_required_keys():
    for name, cfg in SOURCE_CONFIG.items():
        assert "columns" in cfg, f"{name} missing columns"
        assert "delimiter" in cfg, f"{name} missing delimiter"
        assert cfg["delimiter"] == "\t", f"{name} delimiter must be tab"
        assert cfg["null_value"] is None, (
            f"{name} null_value must be None (preserve raw fidelity in Bronze)"
        )


def test_source_config_returns_correct_columns():
    for table, cfg in SOURCE_CONFIG.items():
        cols = cfg["columns"]
        assert len(cols) > 0, f"{table} has no columns defined"
        assert "tconst" in cols or "nconst" in cols or "ordering" in cols, \
            f"{table} missing primary key column"


def test_source_config_columns_are_strings():
    for table in SOURCE_CONFIG:
        cols = SOURCE_CONFIG[table]["columns"]
        assert all(isinstance(c, str) for c in cols), f"{table} has non-string columns"


def test_schema_column_count_matches_imdb_spec():
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


def test_config_matches_bronze_schema():
    expected_basics_cols = ["tconst", "titleType", "primaryTitle", "originalTitle",
                            "isAdult", "startYear", "endYear", "runtimeMinutes", "genres"]
    assert SOURCE_CONFIG["title.basics"]["columns"] == expected_basics_cols

    expected_akas_cols = ["titleId", "ordering", "title", "region", "language",
                          "types", "attributes", "isOriginalTitle"]
    assert SOURCE_CONFIG["title.akas"]["columns"] == expected_akas_cols
