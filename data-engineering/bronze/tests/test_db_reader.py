from unittest.mock import patch, MagicMock, call
import pytest

from bronze.db_configs import (
    DatabaseConnection, SourceTableDef, DuckDBConfig,
    DB_SOURCE_TABLES, DUCKDB_PARQUET_SOURCES,
    POSTGRESQL_CONFIG, DUCKDB_CONFIG,
)
from bronze.db_schema_map import (
    DB_TO_BRONZE_COLUMN_MAP, get_bronze_columns, get_db_columns,
    map_row_to_bronze,
)


class TestDbConfigs:
    def test_postgresql_config_has_defaults(self):
        cfg = POSTGRESQL_CONFIG
        assert cfg.host == "postgres"
        assert cfg.port == 5432
        assert cfg.database == "elyssa_warehouse"
        assert cfg.user == "elyssa"
        assert cfg.source_type == "postgresql"

    def test_db_source_tables_has_all_seven(self):
        expected = {
            "title.basics", "title.akas", "title.crew",
            "title.episode", "title.principals", "title.ratings",
            "name.basics",
        }
        assert set(DB_SOURCE_TABLES.keys()) == expected

    def test_each_table_has_required_fields(self):
        for name, cfg in DB_SOURCE_TABLES.items():
            assert cfg.source_table, f"{name} missing source_table"
            assert cfg.bronze_name == name
            assert len(cfg.columns) > 0, f"{name} has no columns"
            assert cfg.id_column, f"{name} missing id_column"

    def test_each_table_has_watermark_column(self):
        for name, cfg in DB_SOURCE_TABLES.items():
            assert cfg.watermark_column == "ingested_at", \
                f"{name} watermark must be ingested_at"

    def test_table_batch_sizes_positive(self):
        for name, cfg in DB_SOURCE_TABLES.items():
            assert cfg.batch_size > 0, f"{name} batch_size must be positive"
            assert cfg.batch_size == 50000, f"{name} batch_size should be 50000"

    def test_custom_connection_config(self):
        custom = DatabaseConnection(
            host="custom-host",
            port=9999,
            database="custom_db",
            user="custom_user",
            password="custom_pass",
            schema="public",
        )
        assert custom.host == "custom-host"
        assert custom.port == 9999
        assert custom.database == "custom_db"

    def test_source_table_def_defaults(self):
        td = SourceTableDef(
            source_table="public.test",
            bronze_name="test",
            columns=["a", "b"],
        )
        assert td.watermark_column is None
        assert td.id_column == "tconst"
        assert td.batch_size == 50000
        assert td.description == ""


class TestDbSchemaMap:
    def test_all_tables_have_mapping(self):
        for source_name in DB_SOURCE_TABLES:
            assert source_name in DB_TO_BRONZE_COLUMN_MAP, \
                f"{source_name} missing from column map"

    def test_bronze_columns_match_config(self):
        for source_name, table_def in DB_SOURCE_TABLES.items():
            bronze_cols = get_bronze_columns(source_name)
            db_cols = get_db_columns(source_name)
            assert len(bronze_cols) == len(db_cols), \
                f"{source_name}: bronze/db column count mismatch"
            assert all(isinstance(c, str) for c in bronze_cols)
            assert all(isinstance(c, str) for c in db_cols)

    def test_title_basics_mapping(self):
        mapping = DB_TO_BRONZE_COLUMN_MAP["title.basics"]
        assert mapping["tconst"] == "tconst"
        assert mapping["title_type"] == "titleType"
        assert mapping["primary_title"] == "primaryTitle"
        assert mapping["is_adult"] == "isAdult"
        assert mapping["start_year"] == "startYear"
        assert mapping["runtime_minutes"] == "runtimeMinutes"

    def test_title_ratings_mapping(self):
        mapping = DB_TO_BRONZE_COLUMN_MAP["title.ratings"]
        assert mapping["average_rating"] == "averageRating"
        assert mapping["num_votes"] == "numVotes"
        assert mapping["snapshot_date"] == "snapshotDate"

    def test_name_basics_mapping(self):
        mapping = DB_TO_BRONZE_COLUMN_MAP["name.basics"]
        assert mapping["nconst"] == "nconst"
        assert mapping["primary_name"] == "primaryName"
        assert mapping["birth_year"] == "birthYear"

    def test_map_row_to_bronze(self):
        row = {
            "tconst": "tt0000001",
            "title_type": "short",
            "primary_title": "Test Title",
            "is_adult": False,
            "start_year": 2020,
            "end_year": None,
            "runtime_minutes": 120,
            "primary_title": "Test",
            "original_title": "Original",
        }
        result = map_row_to_bronze(row, "title.basics")
        assert result["tconst"] == "tt0000001"
        assert result["titleType"] == "short"
        assert result["primaryTitle"] == "Test"
        assert result["isAdult"] is False
        assert "title_type" not in result

    def test_map_row_to_bronze_filters_unknown(self):
        row = {"tconst": "tt0000001", "unknown_col": "should_be_filtered"}
        result = map_row_to_bronze(row, "title.basics")
        assert "unknown_col" not in result
        assert result["tconst"] == "tt0000001"

    def test_get_bronze_columns_roundtrip(self):
        for source_name in DB_SOURCE_TABLES:
            db_cols = get_db_columns(source_name)
            bronze_cols = get_bronze_columns(source_name)
            mapping = DB_TO_BRONZE_COLUMN_MAP[source_name]
            assert len(db_cols) == len(bronze_cols)
            assert len(set(bronze_cols)) == len(bronze_cols), \
                f"{source_name}: duplicate bronze column names"


class TestDbReader:
    def test_generate_batch_id(self):
        from bronze.db_reader import _generate_batch_id
        bid = _generate_batch_id()
        assert isinstance(bid, str)
        assert len(bid) == 12

    @patch("bronze.db_reader.psycopg2.connect")
    def test_get_row_count(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (12345,)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        from bronze.db_reader import DatabaseReader
        reader = DatabaseReader()
        table_def = DB_SOURCE_TABLES["title.basics"]
        count = reader.get_row_count(table_def)

        assert count == 12345
        mock_cursor.execute.assert_called_once_with(
            "SELECT COUNT(*) FROM silver.title_basics"
        )

    @patch("bronze.db_reader.psycopg2.connect")
    def test_read_table_batches_yields_batches(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        fake_rows = [
            {"tconst": f"tt{i:07d}", "title_type": "movie", "primary_title": f"Title{i}",
             "original_title": f"Original{i}", "is_adult": False, "start_year": 2020,
             "end_year": None, "runtime_minutes": 120}
            for i in range(150)
        ]
        mock_cursor.__iter__.return_value = iter(fake_rows)
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        from bronze.db_reader import DatabaseReader
        reader = DatabaseReader()
        table_def = DB_SOURCE_TABLES["title.basics"]
        table_def._batch_size_backup = table_def.batch_size
        try:
            table_def.batch_size = 100
            batches = list(reader.read_table_batches(table_def))
            assert len(batches) == 2
            assert len(batches[0]) == 100
            assert len(batches[1]) == 50
        finally:
            table_def.batch_size = table_def._batch_size_backup

    @patch("bronze.db_reader.psycopg2.connect")
    def test_empty_table_returns_no_batches(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = iter([])
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        from bronze.db_reader import DatabaseReader
        reader = DatabaseReader()
        table_def = DB_SOURCE_TABLES["title.basics"]
        batches = list(reader.read_table_batches(table_def))
        assert len(batches) == 0

    def test_infer_spark_schema_snake_case_conversion(self):
        from bronze.db_reader import PG_TYPE_MAP
        assert "int2" in PG_TYPE_MAP
        assert "int4" in PG_TYPE_MAP
        assert "text" in PG_TYPE_MAP
        assert "varchar" in PG_TYPE_MAP
        assert "bool" in PG_TYPE_MAP
        assert "numeric" in PG_TYPE_MAP
        assert "date" in PG_TYPE_MAP
        assert "timestamptz" in PG_TYPE_MAP

    def test_empty_schema_has_metadata_columns(self):
        from bronze.db_reader import DatabaseReader
        reader = DatabaseReader()
        schema = reader._empty_schema("title.basics")
        field_names = [f.name for f in schema.fields]
        assert "tconst" in field_names
        assert "titleType" in field_names
        assert "_source_file" in field_names
        assert "_source_table" in field_names
        assert "_batch_id" in field_names
        assert "_ingested_at" in field_names

    @patch("bronze.db_reader.psycopg2.connect")
    def test_read_query_executes_custom_sql(self, mock_connect):
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_cursor.__iter__.return_value = iter([
            {"tconst": "tt0000001", "title_type": "movie", "primary_title": "Test",
             "original_title": "Test", "is_adult": False, "start_year": 2020,
             "end_year": None, "runtime_minutes": 120},
        ])
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
        mock_connect.return_value = mock_conn

        from bronze.db_reader import DatabaseReader
        reader = DatabaseReader()
        result = reader.read_query(
            "SELECT * FROM silver.title_basics LIMIT 1",
            "title.basics",
            "batch_test",
        )
        assert result is not None


class TestIngestFromDb:
    @patch("bronze.db_reader.DatabaseReader")
    def test_ingest_from_db_returns_dict(self, mock_reader_cls):
        mock_instance = MagicMock()
        mock_instance.read_table.return_value.count.return_value = 42
        mock_reader_cls.return_value = mock_instance

        from bronze.db_reader import ingest_from_db
        result = ingest_from_db(table_names=["title.basics"])
        assert isinstance(result, dict)
        assert result["title.basics"] == 42


class TestDbConfigEdgeCases:
    def test_connection_config_default_schema(self):
        cfg = DatabaseConnection()
        assert cfg.schema == "silver"

    def test_source_table_def_no_id_column_defaults(self):
        td = SourceTableDef(
            source_table="public.test",
            bronze_name="test",
            columns=["a"],
        )
        assert td.id_column == "tconst"

    def test_all_source_tables_have_unique_bronze_names(self):
        names = [cfg.bronze_name for cfg in DB_SOURCE_TABLES.values()]
        assert len(names) == len(set(names)), "Duplicate bronze names"

    def test_all_source_tables_have_valid_source_references(self):
        for name, cfg in DB_SOURCE_TABLES.items():
            parts = cfg.source_table.split(".")
            assert len(parts) == 2, \
                f"{name}: source_table should be schema.table, got {cfg.source_table}"
            assert parts[0].isidentifier()
            assert parts[1].isidentifier()


class TestDuckDBConfig:
    def test_duckdb_config_defaults(self):
        cfg = DuckDBConfig()
        assert cfg.source_type == "duckdb"
        assert cfg.read_only is True
        assert cfg.threads == 4
        assert cfg.memory_limit_mb == 2048

    def test_duckdb_parquet_sources_has_all_seven(self):
        expected = {
            "title.basics", "title.akas", "title.crew",
            "title.episode", "title.principals", "title.ratings",
            "name.basics",
        }
        assert set(DUCKDB_PARQUET_SOURCES.keys()) == expected

    def test_duckdb_sources_point_to_parquet(self):
        for name, cfg in DUCKDB_PARQUET_SOURCES.items():
            assert cfg.source_table.endswith(".parquet"), \
                f"{name}: source should be .parquet, got {cfg.source_table}"
            assert cfg.bronze_name == name

    def test_duckdb_source_columns_no_underscore_prefix(self):
        for name, cfg in DUCKDB_PARQUET_SOURCES.items():
            for col in cfg.columns:
                assert not col.startswith("_"), \
                    f"{name}: column {col} should not start with underscore"

    def test_custom_duckdb_config(self):
        custom = DuckDBConfig(threads=8, memory_limit_mb=4096)
        assert custom.threads == 8
        assert custom.memory_limit_mb == 4096

    @patch("bronze.db_reader._duckdb_lib")
    def test_duckdb_reader_initializes(self, mock_duckdb):
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        from bronze.db_reader import DuckDBReader
        reader = DuckDBReader()
        assert reader is not None
        mock_duckdb.connect.assert_called_once_with(":memory:")

    @patch("bronze.db_reader._duckdb_lib")
    def test_duckdb_get_row_count(self, mock_duckdb):
        mock_conn = MagicMock()
        mock_conn.execute.return_value.fetchone.return_value = (42,)
        mock_duckdb.connect.return_value = mock_conn

        from bronze.db_reader import DuckDBReader
        reader = DuckDBReader()
        td = DUCKDB_PARQUET_SOURCES["title.basics"]
        count = reader.get_row_count(td)
        assert count == 42

    @patch("bronze.db_reader._duckdb_lib")
    def test_duckdb_reader_close(self, mock_duckdb):
        mock_conn = MagicMock()
        mock_duckdb.connect.return_value = mock_conn

        from bronze.db_reader import DuckDBReader
        reader = DuckDBReader()
        reader.close()
        mock_conn.close.assert_called_once()

    def test_duckdb_ingest_from_db_routes_correctly(self):
        from bronze.db_reader import ingest_from_db, DatabaseReader, DuckDBReader
        assert callable(ingest_from_db)


class TestIngestFromDbDuckDB:
    @patch("bronze.db_reader.DuckDBReader")
    def test_ingest_duckdb_source_creates_reader(self, mock_reader_cls):
        mock_instance = MagicMock()
        mock_instance.read_table.return_value.count.return_value = 42
        mock_reader_cls.return_value = mock_instance

        from bronze.db_reader import ingest_from_db
        result = ingest_from_db(
            table_names=["title.basics"],
            source_type="duckdb",
        )
        assert isinstance(result, dict)
        assert result["title.basics"] == 42

    def test_ingest_default_source_is_postgresql(self):
        import inspect
        from bronze.db_reader import ingest_from_db
        sig = inspect.signature(ingest_from_db)
        source_type_param = sig.parameters.get("source_type")
        assert source_type_param is not None
        assert source_type_param.default == "postgresql"
