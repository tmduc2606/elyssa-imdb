from airflow.models import BaseOperator
from typing import Optional
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, "/opt/airflow/data-engineering/orchestration")
from pipeline_logger import get_logger


class SilverTransformOperator(BaseOperator):
    """
    Runs the Silver ETL pipeline: reads Bronze Parquet, transforms,
    and upserts into PostgreSQL using DuckDB + psycopg2 COPY (no PySpark).
    """

    template_fields = ("bronze_path",)

    def __init__(
        self,
        bronze_path: str = "/opt/airflow/output/bronze/",
        jdbc_url: str = "postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user: str = "elyssa",
        jdbc_password: str = "elyssa_pg_2026",
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.bronze_path = bronze_path
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password

    def execute(self, context):
        import duckdb
        import psycopg2

        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage="silver_transform", batch_id=batch_id, status="started",
                      message="Processing parent tables + 8 child normalization tables")

        conn = duckdb.connect(":memory:")
        conn.execute("SET threads = 2")
        conn.execute("SET memory_limit = '4GB'")
        conn.execute("SET preserve_insertion_order = false")

        # A1: Set DuckDB temp_directory to dedicated path on airflow_data volume
        temp_dir = "/opt/airflow/output/duckdb_temp/"
        os.makedirs(temp_dir, exist_ok=True)
        conn.execute(f"SET temp_directory = '{temp_dir}'")
        conn.execute("SET max_temp_directory_size = '10GB'")

        pg = psycopg2.connect(
            host="postgres", port=5432,
            user=self.jdbc_user, password=self.jdbc_password,
            dbname="elyssa_warehouse",
            keepalives=1,
            keepalives_idle=300,
            keepalives_interval=60,
            keepalives_count=5,
        )
        pg.autocommit = False

        # Ensure schemas and tables exist (idempotent — survives container rebuilds)
        schema_path = "/opt/airflow/data-engineering/silver/schema.sql"
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                with pg.cursor() as pg_cursor:
                    pg_cursor.execute(f.read())
            pg.commit()
            self.log.info("Schema applied from schema.sql")
        else:
            self.log.warning(f"schema.sql not found at {schema_path}")

        # ── Schema migrations for SCD2 (drop old UNIQUE constraints) ─────
        for _tbl, _old_con in [
            ("silver.title_basics", "uq_title_basics_tconst"),
            ("silver.name_basics", "uq_name_basics_nconst"),
        ]:
            try:
                with pg.cursor() as pg_cursor:
                    pg_cursor.execute(f"ALTER TABLE {_tbl} DROP CONSTRAINT IF EXISTS {_old_con}")
                pg.commit()
                self.log.info(f"Dropped old constraint {_old_con} on {_tbl}")
            except Exception:
                pg.rollback()

        # Column mappings: parquet_table -> (postgres_table, columns_in_order, pk_columns)
        # NOTE: "types", "attributes", "characters" are normalized into child tables
        # (title_akas_type, title_akas_attribute, title_principal_char).
        # "primaryProfession" and "knownForTitles" are in name_profession/name_known_for_title.
        # These child tables are not yet populated by this operator (TODO).
        table_defs = {
            "title.basics": (
                "silver.title_basics",
                ["tconst", "titleType", "primaryTitle", "originalTitle", "isAdult", "startYear", "endYear", "runtimeMinutes"],
                ["tconst"],
            ),
            "title.akas": (
                "silver.title_akas",
                ["titleId", "ordering", "title", "region", "language", "isOriginalTitle"],
                ["titleId", "ordering"],
            ),
            "title.episode": (
                "silver.title_episode",
                ["tconst", "parentTconst", "seasonNumber", "episodeNumber"],
                ["tconst", "parentTconst"],
            ),
            "title.ratings": (
                "silver.title_rating",
                ["tconst", "averageRating", "numVotes"],
                ["tconst"],
            ),
            "title.principals": (
                "silver.title_principal",
                ["tconst", "ordering", "nconst", "category", "job"],
                ["tconst", "ordering"],
            ),
            "name.basics": (
                "silver.name_basics",
                ["nconst", "primaryName", "birthYear", "deathYear"],
                ["nconst"],
            ),
        }

        # Map camelCase column names to snake_case for PostgreSQL
        camel_to_snake_map = {
            "titleType": "title_type",
            "primaryTitle": "primary_title",
            "originalTitle": "original_title",
            "isAdult": "is_adult",
            "startYear": "start_year",
            "endYear": "end_year",
            "runtimeMinutes": "runtime_minutes",
            "titleId": "title_id",
            "ordering": "ordering",
            "isOriginalTitle": "is_original_title",
            "parentTconst": "parent_tconst",
            "seasonNumber": "season_number",
            "episodeNumber": "episode_number",
            "averageRating": "average_rating",
            "numVotes": "num_votes",
            "nconst": "nconst",
            "tconst": "tconst",
            "primaryName": "primary_name",
            "birthYear": "birth_year",
            "deathYear": "death_year",
            "primaryProfession": "primary_profession",
            "knownForTitles": "known_for_titles",
            "category": "category",
            "job": "job",
            "characters": "characters",
            "region": "region",
            "language": "language",
            "types": "types",
            "attributes": "attributes",
            "title": "title",
            "genres": "genres",
        }

        # Columns that need \N -> default_value for NOT NULL constraints
        not_null_fixes = {
            "isAdult": "0",
            "isOriginalTitle": "0",
        }

        # Columns that need VARCHAR -> BOOLEAN cast for PostgreSQL COPY
        bool_casts = {"isAdult", "isOriginalTitle"}

        # Tables that require NOT NULL columns — filter out rows where those
        # columns are NULL (IMDb source data quality issues, e.g. 88 rows in
        # name.basics have no primaryName). These rows are skipped (quarantined
        # implicitly) rather than failing the entire COPY.
        not_null_filters = {
            "name.basics": "primaryName",
        }

        try:
            total_rows = 0
            table_items = list(table_defs.items())
            for table_idx, (src_table, (dst_table, camel_cols, pk_cols)) in enumerate(table_items):
                self.log.info(f"  [{table_idx+1}/{len(table_items)}] Starting {src_table} -> {dst_table}...")
                parquet_path = os.path.join(self.bronze_path, f"{src_table}.parquet")
                if not os.path.exists(parquet_path):
                    self.log.warning(f"Parquet not found: {parquet_path}, skipping")
                    continue

                # Build SELECT with column names from parquet (matches TSV headers)
                # Coalesce \N (IMDb null marker) to SQL NULL, and for NOT NULL
                # columns like isAdult, replace NULL with the default value.
                select_parts = []
                for col_name in camel_cols:
                    expr = f"\"{col_name}\""
                    expr = f"NULLIF({expr}, '\\N')"
                    default_val = not_null_fixes.get(col_name)
                    if default_val is not None:
                        expr = f"COALESCE({expr}, '{default_val}')"
                    if col_name in bool_casts:
                        expr = f"CASE WHEN {expr} = '1' THEN 't' WHEN {expr} = '0' THEN 'f' ELSE 'f' END"
                    select_parts.append(f"{expr} AS \"{col_name}\"")
                select_sql = ", ".join(select_parts)

                # Build WHERE clause to skip rows violating NOT NULL constraints.
                # Raw parquet stores IMDb's \N as a literal 2-char string, so we
                # must filter on the raw value (not SQL NULL) before NULLIF runs.
                not_null_col = not_null_filters.get(src_table)
                where_clause = ""
                if not_null_col:
                    where_clause = (
                        f" WHERE \"{not_null_col}\" IS NOT NULL"
                        f" AND \"{not_null_col}\" != ''"
                        f" AND \"{not_null_col}\" != '\\N'"
                    )

                # Count rows (after NOT NULL filter)
                count_sql = "SELECT COUNT(*) FROM read_parquet('" + parquet_path + "')"
                if not_null_col:
                    count_sql += where_clause
                row_count = conn.execute(count_sql).fetchone()[0]

                if row_count == 0:
                    self.log.info(f"  {src_table}: 0 rows, skipping")
                    continue

                self.log.info(f"  {src_table}: {row_count} rows -> {dst_table}")

                # Copy to CSV for PostgreSQL COPY
                csv_path = f"/tmp/silver_{src_table.replace('.', '_')}.csv"
                conn.execute(
                    "COPY (SELECT " + select_sql + " FROM read_parquet('" + parquet_path + "')"
                    + where_clause + ") TO '" + csv_path + "' (FORMAT CSV, HEADER true, DELIMITER '|')"
                )

                # Build snake_case column list
                snake_cols = [camel_to_snake_map.get(c, c) for c in camel_cols]
                snake_cols_list = ", ".join(snake_cols)
                pg_cols_part = f"({snake_cols_list})"

                # ── SCD2 Merge (title_basics, name_basics) vs Truncate+Copy ──
                scd2_pk_map = {
                    "silver.title_basics": "tconst",
                    "silver.name_basics": "nconst",
                }
                is_scd2 = dst_table in scd2_pk_map

                with pg.cursor() as pg_cursor:
                    if is_scd2:
                        pk_col = scd2_pk_map[dst_table]
                        # Drop indexes for the specific table to speed up SCD2
                        # (recreated after load; if failure occurs mid-way, indexes are rebuilt)
                        try:
                            if dst_table == "silver.title_basics":
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_title_basics_tconst")
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_title_basics_current")
                            elif dst_table == "silver.name_basics":
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_name_basics_nconst")
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_name_basics_current")
                        except Exception:
                            pass  # non-fatal; indexes will be recreated
                        # Temp tables must be unqualified (no schema prefix)
                        stg_table = f"stg_{dst_table.replace('.', '_')}"

                        # Drop and recreate staging table (same structure minus SCD2/audit cols)
                        stg_cols = [c for c in snake_cols
                                    if c not in ("is_current", "valid_from", "valid_to", "ingested_at", "batch_id")]
                        stg_cols_list = ", ".join(stg_cols)
                        stg_create_cols = ", ".join(f"{c} VARCHAR" for c in stg_cols)

                        pg_cursor.execute(f"DROP TABLE IF EXISTS {stg_table}")
                        pg_cursor.execute(f"CREATE TEMP TABLE {stg_table} ({stg_create_cols})")

                        # Add index on PK for fast UPDATE ... WHERE pk IN (SELECT ...)
                        pg_cursor.execute(f"CREATE INDEX idx_{stg_table}_pk ON {stg_table} ({pk_col})")

                        # COPY into staging
                        stg_cols_part = f"({stg_cols_list})"
                        with open(csv_path, "r") as f:
                            pg_cursor.copy_expert(
                                f"COPY {stg_table} {stg_cols_part} FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')",
                                f,
                            )

                        # Expire existing rows that still appear in new data
                        pg_cursor.execute(f"""
                            UPDATE {dst_table}
                            SET valid_to = NOW(), is_current = FALSE
                            FROM {stg_table} s
                            WHERE {dst_table}.{pk_col} = s.{pk_col}
                              AND {dst_table}.is_current = TRUE
                        """)
                        # Recreate indexes after load
                        if dst_table == "silver.title_basics":
                            pg_cursor.execute("CREATE INDEX idx_title_basics_tconst ON silver.title_basics(tconst)")
                            pg_cursor.execute("CREATE INDEX idx_title_basics_current ON silver.title_basics(is_current) WHERE is_current = TRUE")
                        elif dst_table == "silver.name_basics":
                            pg_cursor.execute("CREATE INDEX idx_name_basics_nconst ON silver.name_basics(nconst)")
                            pg_cursor.execute("CREATE INDEX idx_name_basics_current ON silver.name_basics(is_current) WHERE is_current = TRUE")
                        expired = pg_cursor.rowcount

                        # Insert new versions
                        stg_insert_cols = ", ".join(stg_cols)
                        # Type casts for SCD2 staging tables (all staging cols are VARCHAR)
                        scd2_type_casts = {
                            "silver.title_basics": {
                                "is_adult": "::BOOLEAN",
                                "start_year": "::SMALLINT",
                                "end_year": "::SMALLINT",
                                "runtime_minutes": "::INTEGER",
                            },
                            "silver.name_basics": {
                                "birth_year": "::SMALLINT",
                                "death_year": "::SMALLINT",
                            },
                        }
                        casts = scd2_type_casts.get(dst_table, {})
                        stg_select_cols = ", ".join(
                            f"{c}{casts.get(c, '')}" for c in stg_cols
                        )
                        pg_cursor.execute(f"""
                            INSERT INTO {dst_table} ({stg_insert_cols}, valid_from, is_current, batch_id, ingested_at)
                            SELECT {stg_select_cols}, NOW(), TRUE, '{batch_id}', NOW()
                            FROM {stg_table}
                        """)
                        inserted = pg_cursor.rowcount

                        pg_cursor.execute(f"DROP TABLE IF EXISTS {stg_table}")
                        self.log.info(f"  {dst_table}: {expired} expired, {inserted} inserted (SCD2)")
                    else:
                        # Truncate and COPY into PostgreSQL
                        # CASCADE handles FK constraints (e.g. title_akas_type -> title_akas)
                        pg_cursor.execute(f"TRUNCATE {dst_table} CASCADE")
                        with open(csv_path, "r") as f:
                            pg_cursor.copy_expert(
                                f"COPY {dst_table} {pg_cols_part} FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')",
                                f,
                            )

                os.remove(csv_path)
                total_rows += row_count
                self.log.info(f"  {dst_table}: {row_count} rows loaded")
                log.log_stage(stage="silver_transform", batch_id=batch_id,
                              status="success", row_count=row_count,
                              message=f"{src_table} -> {dst_table}")

            # ─── Normalize Child Tables ───────────────────────────────────────
            child_table_defs = [
                {
                    "dst_table": "silver.title_genre",
                    "snake_cols": ["tconst", "genre"],
                    "src_table": "title.basics",
                    "sql": """
                        SELECT tconst,
                               UNNEST(string_split(NULLIF(genres, '\\N'), ',')) AS genre
                        FROM read_parquet('{path}')
                        WHERE genres IS NOT NULL
                          AND genres != ''
                          AND genres != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.title_director",
                    "snake_cols": ["tconst", "ordering", "nconst"],
                    "src_table": "title.crew",
                    "sql": """
                        SELECT tconst,
                               CAST(ROW_NUMBER() OVER (PARTITION BY tconst) AS SMALLINT) AS ordering,
                               director AS nconst
                        FROM (
                            SELECT tconst,
                                   UNNEST(string_split(NULLIF(directors, '\\N'), ',')) AS director
                            FROM read_parquet('{path}')
                            WHERE directors IS NOT NULL
                              AND directors != ''
                              AND directors != '\\N'
                        ) sub
                    """,
                },
                {
                    "dst_table": "silver.title_writer",
                    "snake_cols": ["tconst", "ordering", "nconst"],
                    "src_table": "title.crew",
                    "sql": """
                        SELECT tconst,
                               CAST(ROW_NUMBER() OVER (PARTITION BY tconst) AS SMALLINT) AS ordering,
                               writer AS nconst
                        FROM (
                            SELECT tconst,
                                   UNNEST(string_split(NULLIF(writers, '\\N'), ',')) AS writer
                            FROM read_parquet('{path}')
                            WHERE writers IS NOT NULL
                              AND writers != ''
                              AND writers != '\\N'
                        ) sub
                    """,
                },
                {
                    "dst_table": "silver.title_akas_type",
                    "snake_cols": ["title_id", "ordering", "type"],
                    "src_table": "title.akas",
                    "sql": """
                        SELECT titleId AS title_id,
                               ordering,
                               UNNEST(string_split(NULLIF(types, '\\N'), ',')) AS type
                        FROM read_parquet('{path}')
                        WHERE types IS NOT NULL
                          AND types != ''
                          AND types != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.title_akas_attribute",
                    "snake_cols": ["title_id", "ordering", "attr"],
                    "src_table": "title.akas",
                    "sql": """
                        SELECT titleId AS title_id,
                               ordering,
                               UNNEST(string_split(NULLIF(attributes, '\\N'), ',')) AS attr
                        FROM read_parquet('{path}')
                        WHERE attributes IS NOT NULL
                          AND attributes != ''
                          AND attributes != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.title_principal_char",
                    "snake_cols": ["tconst", "ordering", "character_name"],
                    "src_table": "title.principals",
                    "sql": """
                        SELECT tconst,
                               ordering,
                               TRIM(UNNEST(
                                   string_split(TRIM(NULLIF(characters, '\\N'), '[]'), '","')
                               ), '"') AS character_name
                        FROM read_parquet('{path}')
                        WHERE characters IS NOT NULL
                          AND characters != ''
                          AND characters != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.name_profession",
                    "snake_cols": ["nconst", "profession_order", "profession"],
                    "src_table": "name.basics",
                    "sql": """
                        SELECT nconst,
                               CAST(ROW_NUMBER() OVER (PARTITION BY nconst) AS SMALLINT) AS profession_order,
                               profession AS profession
                        FROM (
                            SELECT nconst,
                                   UNNEST(string_split(NULLIF(primaryProfession, '\\N'), ',')) AS profession
                            FROM read_parquet('{path}')
                            WHERE primaryProfession IS NOT NULL
                              AND primaryProfession != ''
                              AND primaryProfession != '\\N'
                        ) sub
                    """,
                },
                {
                    "dst_table": "silver.name_known_for_title",
                    "snake_cols": ["nconst", "known_for_order", "tconst"],
                    "src_table": "name.basics",
                    "sql": """
                        SELECT nconst,
                               CAST(ROW_NUMBER() OVER (PARTITION BY nconst) AS SMALLINT) AS known_for_order,
                               title AS tconst
                        FROM (
                            SELECT nconst,
                                   UNNEST(string_split(NULLIF(knownForTitles, '\\N'), ',')) AS title
                            FROM read_parquet('{path}')
                            WHERE knownForTitles IS NOT NULL
                              AND knownForTitles != ''
                              AND knownForTitles != '\\N'
                        ) sub
                    """,
                },
            ]

            child_rows = 0
            for child_idx, child in enumerate(child_table_defs):
                parquet_path = os.path.join(self.bronze_path, f"{child['src_table']}.parquet")
                if not os.path.exists(parquet_path):
                    self.log.warning(f"Child parquet not found: {parquet_path}, skipping")
                    continue

                self.log.info(f"  [{child_idx+1}/{len(child_table_defs)}] Starting {child['dst_table']}...")
                sql = child["sql"].format(path=parquet_path)

                row_count = conn.execute(f"SELECT COUNT(*) FROM ({sql})").fetchone()[0]

                if row_count == 0:
                    self.log.info(f"  {child['dst_table']}: 0 rows, skipping")
                    continue

                self.log.info(f"  {child['dst_table']}: {row_count} rows to load")

                csv_path = f"/tmp/silver_{child['dst_table'].replace('.', '_')}.csv"
                conn.execute(f"COPY ({sql}) TO '{csv_path}' (FORMAT CSV, HEADER true, DELIMITER '|')")
                self.log.info(f"  {child['dst_table']}: CSV export done")

                with pg.cursor() as pg_cursor:
                    pg_cursor.execute(f"TRUNCATE {child['dst_table']}")

                    with open(csv_path, "r") as f:
                        cols = ", ".join(child["snake_cols"])
                        pg_cursor.copy_expert(
                            f"COPY {child['dst_table']} ({cols}) FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')",
                            f,
                        )
                os.remove(csv_path)
                child_rows += row_count
                self.log.info(f"  {child['dst_table']}: {row_count} rows loaded")
                log.log_stage(stage="silver_transform", batch_id=batch_id,
                              status="success", row_count=row_count,
                              message=f"child {child['dst_table']}")

            pg.commit()
            elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
            self.log.info(f"Silver ETL complete: {total_rows} parent rows + {child_rows} child rows across {len(table_defs) + len(child_table_defs)} tables")
            log.log_stage(stage="silver_transform", batch_id=batch_id,
                          status="complete", row_count=total_rows + child_rows,
                          duration_ms=elapsed,
                          message=f"{total_rows} parent + {child_rows} child rows")
        except Exception as e:
            self.log.error(f"Silver ETL failed: {e}")
            log.log_error(stage="silver_transform", batch_id=batch_id,
                          error=f"Silver ETL failed: {e}")
            try:
                pg.rollback()
            except Exception:
                pass
            raise
        finally:
            conn.close()
            # Clean up temp CSV files
            try:
                import glob
                for csv_file in glob.glob("/tmp/silver_*.csv"):
                    os.remove(csv_file)
            except Exception:
                pass
            # Clean up DuckDB temp files
            try:
                import shutil
                temp_dir = "/opt/airflow/output/duckdb_temp/"
                if os.path.exists(temp_dir):
                    shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception as e:
                self.log.warning(f"Failed to clean up DuckDB temp directory: {e}")
            pg.close()
