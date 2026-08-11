"""Legacy standalone DB/Parquet reader, rewritten to drop PySpark.

Reads PostgreSQL (via psycopg2) or DuckDB/Parquet sources and returns
lightweight Table objects (list[dict] with a Spark-like .count()).
The canonical pipeline path is orchestration/dags/imdb_pipeline_dag.py
(scripts/run_bronze.py + orchestration/operators/silver_operator.py).

Output rows are keyed by bronze-style column names via bronze.db_schema_map.
"""

from datetime import datetime, timezone
from typing import Optional, Generator
import json
import uuid

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
    map_row_to_bronze, get_bronze_columns,
    DB_TO_BRONZE_COLUMN_MAP,
)
from bronze.parquet_io import write_rows_to_parquet


class Field:
    def __init__(self, name: str, type_: type = str, nullable: bool = True):
        self.name = name
        self.type = type_
        self.nullable = nullable


class Schema:
    def __init__(self, fields: list[Field]):
        self.fields = fields

    @property
    def names(self) -> list[str]:
        return [f.name for f in self.fields]


class Table:
    """In-memory result table: list[dict] rows with a Spark-like API."""

    def __init__(self, rows: list[dict], schema: Optional[Schema] = None):
        self.rows = rows
        self.schema = schema

    @classmethod
    def empty(cls, schema: Optional[Schema] = None) -> "Table":
        return cls([], schema)

    def count(self) -> int:
        return len(self.rows)

    @property
    def columns(self) -> list[str]:
        if self.rows:
            return list(self.rows[0].keys())
        if self.schema is not None:
            return self.schema.names
        return []

    def __iter__(self):
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)


PG_TYPE_MAP: dict[str, type] = {
    "int2": int,
    "int4": int,
    "int8": int,
    "numeric": float,
    "float4": float,
    "float8": float,
    "bool": bool,
    "date": str,
    "varchar": str,
    "text": str,
    "name": str,
    "bpchar": str,
    "timestamptz": str,
    "timestamp": str,
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


def infer_schema(conn, table_schema: str, table_name: str,
                 source_name: str) -> Schema:
    """Infer a Schema for the bronze-mapped columns of a PG table."""
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
        fields.append(Field(
            bronze_col_map[col_name],
            PG_TYPE_MAP.get(type_name, str),
            nullable=not not_null,
        ))
    return Schema(fields)


# Backward-compatible alias for the pre-rewrite name.
infer_spark_schema = infer_schema


class DatabaseReader:
    def __init__(self, connection_config: Optional[DatabaseConnection] = None):
        self.config = connection_config or POSTGRESQL_CONFIG

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

    def _infer_schema(self, table_def: SourceTableDef,
                      source_name: str) -> Schema:
        conn = self._connect()
        try:
            return infer_schema(
                conn, self.config.schema,
                table_def.source_table.split(".")[-1],
                source_name,
            )
        finally:
            conn.close()

    def read_table(self, table_def: SourceTableDef,
                   batch_id: str) -> Table:
        bronze_name = table_def.bronze_name
        rows = []
        for batch in self.read_table_batches(table_def):
            rows.extend(map_row_to_bronze(r, bronze_name) for r in batch)

        if not rows:
            return Table.empty(self._empty_schema(bronze_name))

        schema = self._infer_schema(table_def, bronze_name)
        return self._add_metadata(Table(rows, schema), bronze_name, batch_id)

    def read_incremental(self, table_def: SourceTableDef,
                         last_watermark: Optional[str],
                         batch_id: str) -> Table:
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
                    rows.append(map_row_to_bronze(dict(row), bronze_name))

            if not rows:
                return Table.empty(self._empty_schema(bronze_name))

            schema = infer_schema(
                conn, self.config.schema,
                table_def.source_table.split(".")[-1],
                bronze_name,
            )
            return self._add_metadata(Table(rows, schema), bronze_name, batch_id)
        finally:
            conn.close()

    def read_query(self, query: str, bronze_name: str, batch_id: str) -> Table:
        conn = self._connect()
        try:
            rows = []
            with conn.cursor(name="query_cursor", cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.itersize = 50000
                cur.execute(query)
                for row in cur:
                    rows.append(map_row_to_bronze(dict(row), bronze_name))

            if not rows:
                return Table.empty(self._empty_schema(bronze_name))

            schema = infer_schema(
                conn, self.config.schema,
                "", bronze_name,
            )
            return self._add_metadata(Table(rows, schema), bronze_name, batch_id)
        finally:
            conn.close()

    def _add_metadata(self, table: Table, source_name: str,
                      batch_id: str) -> Table:
        now_ts = datetime.now(timezone.utc).isoformat()
        source_uri = f"postgresql://{self.config.host}:{self.config.port}/{self.config.database}"
        md = {
            "_source_file": source_uri,
            "_source_table": source_name,
            "_batch_id": batch_id,
            "_ingested_at": now_ts,
        }
        rows = [{**r, **md} for r in table.rows]
        schema = table.schema
        if schema is not None:
            md_fields = [
                Field(n, str, True)
                for n in ("_source_file", "_source_table", "_batch_id", "_ingested_at")
            ]
            schema = Schema(schema.fields + md_fields)
        return Table(rows, schema)

    def _empty_schema(self, source_name: str) -> Schema:
        cols = get_bronze_columns(source_name)
        fields = [Field(c, str, True) for c in cols]
        md_fields = [
            Field(n, str, True)
            for n in ("_source_file", "_source_table", "_batch_id", "_ingested_at")
        ]
        return Schema(fields + md_fields)


def _clean_path(path: str) -> str:
    return path.replace("\\", "/")


class DuckDBReader:
    def __init__(self, duckdb_config: Optional[DuckDBConfig] = None):
        self.config = duckdb_config or DUCKDB_CONFIG
        self._duck = _duckdb_lib.connect(":memory:")
        from bronze.s3_config import configure_s3
        configure_s3(self._duck)
        self._duck.execute(f"SET threads = {self.config.threads}")
        self._duck.execute(f"SET memory_limit = '{self.config.memory_limit_mb}MB'")

    def close(self):
        self._duck.close()

    def get_row_count(self, table_def: SourceTableDef) -> int:
        parquet_path = _clean_path(table_def.source_table)
        return self._duck.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_path}')"
        ).fetchone()[0]

    def read_table(self, table_def: SourceTableDef,
                   batch_id: str) -> Table:
        bronze_name = table_def.bronze_name
        parquet_path = _clean_path(table_def.source_table)
        col_list = ", ".join(table_def.columns)

        result = self._duck.execute(
            f"SELECT {col_list} FROM read_parquet('{parquet_path}') "
            f"ORDER BY {table_def.id_column}"
        )
        rows = [dict(zip([desc[0] for desc in result.description], row))
                for row in result.fetchall()]

        if not rows:
            return Table.empty(self._empty_schema(bronze_name))

        schema = self._infer_schema(table_def, bronze_name)
        return self._add_metadata(Table(rows, schema), bronze_name, batch_id,
                                  parquet_path)

    def read_query(self, query: str, bronze_name: str, batch_id: str,
                   parquet_path: str = "") -> Table:
        result = self._duck.execute(query)
        rows = [dict(zip([desc[0] for desc in result.description], row))
                for row in result.fetchall()]

        if not rows:
            return Table.empty(self._empty_schema(bronze_name))

        return self._add_metadata(Table(rows, None), bronze_name, batch_id,
                                  parquet_path)

    def _infer_schema(self, table_def: SourceTableDef,
                      source_name: str) -> Schema:
        parquet_path = _clean_path(table_def.source_table)
        duck_columns = self._duck.execute(
            f"DESCRIBE SELECT * FROM read_parquet('{parquet_path}')"
        ).fetchall()

        duck_type_map = {
            "BIGINT": int, "INTEGER": int, "SMALLINT": int, "TINYINT": int,
            "BOOLEAN": bool, "DATE": str,
            "DOUBLE": float, "FLOAT": float,
            "VARCHAR": str, "TEXT": str,
        }
        fields = []
        selected = set(table_def.columns)
        for col_info in duck_columns:
            col_name = col_info[0]
            if col_name not in selected:
                continue
            duck_type_str = col_info[1].split("(")[0].upper()
            fields.append(Field(col_name, duck_type_map.get(duck_type_str, str), True))
        return Schema(fields)

    def _add_metadata(self, table: Table, source_name: str,
                      batch_id: str, source_path: str) -> Table:
        now_ts = datetime.now(timezone.utc).isoformat()
        md = {
            "_source_file": source_path,
            "_source_table": source_name,
            "_batch_id": batch_id,
            "_ingested_at": now_ts,
        }
        rows = [{**r, **md} for r in table.rows]
        schema = table.schema
        if schema is not None:
            md_fields = [
                Field(n, str, True)
                for n in ("_source_file", "_source_table", "_batch_id", "_ingested_at")
            ]
            schema = Schema(schema.fields + md_fields)
        return Table(rows, schema)

    def _empty_schema(self, source_name: str) -> Schema:
        cols = get_bronze_columns(source_name)
        fields = [Field(c, str, True) for c in cols]
        md_fields = [
            Field(n, str, True)
            for n in ("_source_file", "_source_table", "_batch_id", "_ingested_at")
        ]
        return Schema(fields + md_fields)


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
        table = reader.read_table(table_def, batch_id)
        row_count = table.count()
        rows = getattr(table, "rows", None)
        if row_count and isinstance(rows, list) and rows:
            write_rows_to_parquet(rows, f"{output_root}/{bronze_name}.parquet")
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
