try:
    from airflow.models import BaseOperator
except ImportError:
    class BaseOperator:  # type: ignore[no-redef]
        """Stub BaseOperator when Airflow is not installed (standalone etl-runner)."""
        def __init__(self, *args, **kwargs):
            self.log = _StubLogger()
        template_fields = ()

    class _StubLogger:
        def info(self, *a, **kw): print(a[0] if a else "")
        def warning(self, *a, **kw): print("[WARN]", a[0] if a else "")
        def error(self, *a, **kw): print("[ERROR]", a[0] if a else "")
import json
from typing import Optional
import os
import glob
import sys
from datetime import datetime, timezone

# Support both Airflow container (/opt/airflow/...) and etl-runner (/opt/etl/...)
_orch_path = "/opt/airflow/data-engineering/orchestration"
if not os.path.isdir(_orch_path):
    _orch_path = "/opt/etl/data-engineering/orchestration"
sys.path.insert(0, _orch_path)
from pipeline_logger import get_logger

_root_path = "/opt/airflow/data-engineering"
if not os.path.isdir(os.path.join(_root_path, "bronze")):
    _root_path = "/opt/etl/data-engineering"

# Hash-shard count for child tables (P0-1/R1). All 8 children are sharded —
# every IMDb child source exceeds the old 5M threshold, so the chunked
# full-COPY branch was removed (R4).
CHILD_SHARD_COUNT = 16

# R2: secondary indexes on the 8 child tables. Dropped before bulk load and
# recreated afterward; PK/UNIQUE constraints and FK constraints remain
# enforced (test_fk_integrity covers them). DDL uses IF NOT EXISTS so it is
# idempotent across the docker-init and silver/schema.sql variants.
CHILD_SECONDARY_INDEXES = {
    "silver.title_genre": [
        ("idx_title_genre_tconst", "CREATE INDEX IF NOT EXISTS idx_title_genre_tconst ON silver.title_genre(tconst)"),
        ("idx_title_genre_tconst_genre", "CREATE INDEX IF NOT EXISTS idx_title_genre_tconst_genre ON silver.title_genre(tconst, genre)"),
    ],
    "silver.title_director": [
        ("idx_title_director_tconst", "CREATE INDEX IF NOT EXISTS idx_title_director_tconst ON silver.title_director(tconst)"),
        ("idx_title_director_nconst", "CREATE INDEX IF NOT EXISTS idx_title_director_nconst ON silver.title_director(nconst)"),
    ],
    "silver.title_writer": [
        ("idx_title_writer_tconst", "CREATE INDEX IF NOT EXISTS idx_title_writer_tconst ON silver.title_writer(tconst)"),
        ("idx_title_writer_nconst", "CREATE INDEX IF NOT EXISTS idx_title_writer_nconst ON silver.title_writer(nconst)"),
    ],
    "silver.title_akas_type": [
        ("idx_title_akas_type_ref", "CREATE INDEX IF NOT EXISTS idx_title_akas_type_ref ON silver.title_akas_type(title_id, ordering)"),
    ],
    "silver.title_akas_attribute": [
        ("idx_title_akas_attribute_ref", "CREATE INDEX IF NOT EXISTS idx_title_akas_attribute_ref ON silver.title_akas_attribute(title_id, ordering)"),
    ],
    "silver.title_principal_char": [
        ("idx_title_principal_char_ref", "CREATE INDEX IF NOT EXISTS idx_title_principal_char_ref ON silver.title_principal_char(tconst, ordering)"),
    ],
    "silver.name_profession": [
        ("idx_name_profession_nconst", "CREATE INDEX IF NOT EXISTS idx_name_profession_nconst ON silver.name_profession(nconst)"),
    ],
    "silver.name_known_for_title": [
        ("idx_name_known_for_nconst", "CREATE INDEX IF NOT EXISTS idx_name_known_for_nconst ON silver.name_known_for_title(nconst)"),
        ("idx_name_known_for_tconst", "CREATE INDEX IF NOT EXISTS idx_name_known_for_tconst ON silver.name_known_for_title(tconst)"),
    ],
}

# R2-ext: FK constraints on the FK-backed children. Dropped during bulk load
# too — the per-row RI-trigger probe against the parent index dominates load
# time (measured ~13-15 min/shard vs ~40 s for FK-free children). Re-added
# NOT VALID + VALIDATED after all children load (single streaming anti-join
# scan vs per-row probes); the test_fk_integrity DQ gate remains the backstop.
CHILD_FK_CONSTRAINTS = {
    "silver.title_akas_type": [
        ("title_akas_type_title_id_ordering_fkey", "FOREIGN KEY (title_id, ordering) REFERENCES silver.title_akas(title_id, ordering) ON DELETE CASCADE"),
    ],
    "silver.title_akas_attribute": [
        ("title_akas_attribute_title_id_ordering_fkey", "FOREIGN KEY (title_id, ordering) REFERENCES silver.title_akas(title_id, ordering) ON DELETE CASCADE"),
    ],
    "silver.title_principal_char": [
        ("title_principal_char_tconst_ordering_fkey", "FOREIGN KEY (tconst, ordering) REFERENCES silver.title_principal(tconst, ordering) ON DELETE CASCADE"),
    ],
}


def _pid_exists(pid: int) -> bool:
    """Check if a process with the given PID still exists."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _acquire_silver_file_lock(lock_path: str, logger):
    """Acquire an exclusive file lock for Silver ETL serialization.

    Uses fcntl.flock with LOCK_EX | LOCK_NB. If the lock is held by a dead
    PID (stale), removes the stale lock and retries once. If the holder is
    alive, raises RuntimeError to prevent concurrent TRUNCATE CASCADE.
    """
    import fcntl

    lock_dir = os.path.dirname(lock_path)
    os.makedirs(lock_dir, exist_ok=True)

    fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        # Lock is held — check if holder PID is still alive
        holder_pid = None
        try:
            with os.fdopen(fd, "r") as f:
                content = f.read()
            holder_pid = int(content.strip()) if content.strip().isdigit() else None
        except Exception:
            pass

        if holder_pid and not _pid_exists(holder_pid):
            logger.warning(f"Stale Silver file lock from dead PID {holder_pid}, removing")
            os.close(fd)
            try:
                os.remove(lock_path)
            except OSError:
                pass
            # Retry once
            fd = os.open(lock_path, os.O_CREAT | os.O_RDWR)
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                raise RuntimeError(
                    "Another Silver ETL run is already in progress (file lock held). "
                    "Aborting to prevent concurrent TRUNCATE CASCADE."
                )
        else:
            raise RuntimeError(
                "Another Silver ETL run is already in progress. "
                "Aborting to prevent deadlock on TRUNCATE CASCADE."
            )

    # Record our PID in the lock file
    os.ftruncate(fd, 0)
    os.lseek(fd, 0, os.SEEK_SET)
    os.write(fd, str(os.getpid()).encode())
    os.fsync(fd)
    return fd


def _release_silver_file_lock(fd, lock_path: str):
    """Release file lock and clean up lock file."""
    if fd is not None:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
            os.close(fd)
        except Exception:
            pass
    try:
        if os.path.exists(lock_path):
            os.remove(lock_path)
    except OSError:
        pass


def _log_memory(conn, logger, stage_name):
    """Log DuckDB peak memory and temp file usage for profiling (M10)."""
    try:
        peak_mb = conn.execute(
            "SELECT peak_memory / (1024 * 1024) FROM pragma_database_info()"
        ).fetchone()[0]
        temp_count = conn.execute(
            "SELECT count(*) FROM glob( "
            "(SELECT value FROM pragma_database_setting('temp_directory')) || '/*.tmp')"
        ).fetchone()[0]
        logger.info(f"[MEMPROFILE] {stage_name}: DuckDB peak={peak_mb} MB, temp_files={temp_count}")
    except Exception:
        pass


def _parquet_row_count(conn, url):
    """Read the Parquet footer for a row count without scanning data (R3).

    parquet_metadata emits one row per row group per column; the row count
    is max(row_group_num_rows) per row_group_id, summed. Falls back to a
    full COUNT(*) scan if the metadata read fails (e.g. exotic stores).
    """
    try:
        return conn.execute(
            "SELECT sum(row_group_num_rows) FROM ("
            "  SELECT row_group_id, max(row_group_num_rows) AS row_group_num_rows"
            f"  FROM parquet_metadata('{url}') GROUP BY row_group_id)"
        ).fetchone()[0]
    except Exception:
        return conn.execute(f"SELECT COUNT(*) FROM read_parquet('{url}')").fetchone()[0]


def _partition_child_source(conn, src_url, part_dir, shard_key, log):
    """Single-pass partitioned copy of a child source (R1).

    COPY ... PARTITION_BY (_shard) writes _shard=N/ directories so a shard
    scan reads only 1/16 of the source. The old approach materialized the
    source once and re-scanned it with WHERE _shard = N per shard (~17x
    total reads); this is ~2x. A stale partition dir from a crashed run is
    removed first (stale-dir guard).
    """
    import shutil

    if os.path.isdir(part_dir):
        shutil.rmtree(part_dir, ignore_errors=True)
    os.makedirs(part_dir, exist_ok=True)
    conn.execute(f"""
        COPY (
            SELECT *,
                   CAST(((hash("{shard_key}") % {CHILD_SHARD_COUNT}) + {CHILD_SHARD_COUNT}) % {CHILD_SHARD_COUNT} AS SMALLINT) AS _shard
            FROM read_parquet('{src_url}')
        ) TO '{part_dir}' (FORMAT PARQUET, PARTITION_BY (_shard))
    """)
    log.info(f"    partitioned into {CHILD_SHARD_COUNT} shards at {part_dir}")


def _process_child_table_sharded(conn, pg_cursor, child_def, part_dir, log):
    """Load a child table from a hash-partitioned source (R1).

    The source was partitioned once (COPY ... PARTITION_BY _shard), so
    _shard=N/ files contain only rows whose key hashes to shard N. Per-shard
    scans therefore read only 1/16 of the source and per-shard DISTINCT is
    globally correct; the PG-side SELECT DISTINCT + ON CONFLICT DO NOTHING
    can be dropped (PK violations are impossible). This replaces the
    materialized-table + WHERE _shard = N path that re-scanned the whole
    source once per shard.
    """
    dst_table = child_def["dst_table"]
    snake_cols = child_def["snake_cols"]
    sql_template = child_def["sql"]

    chunk_total = 0
    for shard_idx in range(CHILD_SHARD_COUNT):
        shard_dir = os.path.join(part_dir, f"_shard={shard_idx}")
        if not glob.glob(os.path.join(shard_dir, "*.parquet")):
            log.info(f"  {dst_table}: shard {shard_idx} empty, skipping")
            continue
        source_expr = f"(SELECT * FROM read_parquet('{os.path.join(shard_dir, '*.parquet')}'))"
        shard_sql = sql_template.format(source=source_expr)
        csv_path = f"/tmp/silver_{dst_table.replace('.', '_')}_shard_{shard_idx}.csv"
        conn.execute(f"COPY ({shard_sql}) TO '{csv_path}' (FORMAT CSV, HEADER true, DELIMITER '|')")

        # Per-shard temp table — COPY then plain INSERT (no DISTINCT/ON
        # CONFLICT: the shard key guarantees a key never spans shards).
        stg_table = f"stg_shard_{dst_table.replace('.', '_')}_{shard_idx}"
        cols = ", ".join(snake_cols)
        pg_cursor.execute(f"CREATE TEMP TABLE {stg_table} (LIKE {dst_table} INCLUDING DEFAULTS)")
        with open(csv_path, "r") as f:
            pg_cursor.copy_expert(
                f"COPY {stg_table} ({cols}) FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')",
                f,
            )
        pg_cursor.execute(f"INSERT INTO {dst_table} ({cols}) SELECT {cols} FROM {stg_table}")
        shard_rows = pg_cursor.rowcount
        pg_cursor.execute(f"DROP TABLE IF EXISTS {stg_table}")

        os.remove(csv_path)
        chunk_total += shard_rows
        log.info(f"  {dst_table}: shard {shard_idx} loaded ({shard_rows} rows)")

    log.info(f"  {dst_table}: {chunk_total} total rows loaded")
    return chunk_total


class SilverTransformOperator(BaseOperator):
    """
    Runs the Silver ETL pipeline: reads Bronze Parquet, transforms,
    and upserts into PostgreSQL using DuckDB + psycopg2 COPY (no PySpark).
    """

    template_fields = ("bronze_path",)

    def __init__(
        self,
        bronze_path: str = "s3://bronze/",
        jdbc_url: str = "postgresql://elyssa:***@postgres:5432/elyssa_warehouse",
        jdbc_user: str = "elyssa",
        jdbc_password: str = "elyssa_pg_2026",
        profile_memory: bool = False,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.bronze_path = bronze_path
        self.jdbc_url = jdbc_url
        self.jdbc_user = jdbc_user
        self.jdbc_password = jdbc_password
        self.profile_memory = profile_memory

    def execute(self, context):
        import duckdb
        import psycopg2

        log = get_logger()
        batch_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        start_ts = datetime.now(timezone.utc)

        log.log_stage(stage="silver_transform", batch_id=batch_id, status="started",
                      message="Processing parent tables + 8 child normalization tables")

        # M1: Use file-backed DuckDB for automatic spill-to-disk
        # Prefer the dedicated etl_temp volume (/opt/etl/tmp in etl-runner,
        # /opt/airflow/output/tmp in airflow) so the Silver lock, checkpoint
        # markers, and subprocess log are shared across containers and survive
        # container restarts. Falls back to /tmp otherwise.
        temp_root = "/opt/etl/tmp"
        if not os.path.isdir(temp_root):
            temp_root = "/opt/airflow/output/tmp"
        if not os.path.isdir(temp_root):
            temp_root = "/tmp/"
        duckdb_temp = os.path.join(temp_root, "duckdb_spill")
        csv_dir = os.path.join(temp_root, "csv_intermediates")
        duckdb_file = os.path.join(duckdb_temp, f"silver_{batch_id}.duckdb")
        os.makedirs(duckdb_temp, exist_ok=True)
        os.makedirs(csv_dir, exist_ok=True)
        conn = duckdb.connect(str(duckdb_file))
        sys.path.insert(0, _root_path)
        from bronze.s3_config import configure_s3
        configure_s3(conn)
        conn.execute("SET threads = 2")
        mem_limit = os.environ.get("DUCKDB_MEMORY_LIMIT", "2GB")
        conn.execute(f"SET memory_limit = '{mem_limit}'")
        conn.execute("SET preserve_insertion_order = false")
        conn.execute(f"SET temp_directory = '{duckdb_temp}'")
        conn.execute("SET max_temp_directory_size = '1.25GB'")

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

        # M5: Tune PostgreSQL session for bulk COPY
        # max_wal_size, wal_level, archive_mode are POSTMASTER params (set in docker-compose, not per-session)
        with pg.cursor() as tune:
            tune.execute("SET maintenance_work_mem = '256MB'")
            # P3-11: skip synchronous WAL flush during bulk COPY (session-level;
            # pipeline is checkpoint-driven and idempotent — worst case on a
            # power loss is re-running the current stage, no corruption).
            tune.execute("SET synchronous_commit = off")
        pg.commit()

        # Acquire file-based exclusive lock to serialize Silver ETL runs
        # (prevents concurrent TRUNCATE CASCADE). Lock auto-releases on crash.
        _lock_fd = None
        try:
            silver_lock_path = os.path.join(temp_root, "silver.lock")
            _lock_fd = _acquire_silver_file_lock(silver_lock_path, self.log)
            self.log.info(f"Acquired Silver file lock: {silver_lock_path}")
        except Exception as e:
            self.log.error(f"Failed to acquire Silver file lock: {e}")
            raise RuntimeError(
                "Another Silver ETL run is already in progress. "
                "Aborting to prevent deadlock on TRUNCATE CASCADE."
            ) from e

        # Ensure schemas and tables exist (idempotent — survives container rebuilds)
        schema_path = os.path.join(_root_path, "silver", "schema.sql")
        if os.path.exists(schema_path):
            with open(schema_path, "r") as f:
                with pg.cursor() as pg_cursor:
                    pg_cursor.execute(f.read())
            pg.commit()
            self.log.info(f"Schema applied from {schema_path}")
        else:
            self.log.warning(f"schema.sql not found at {schema_path}")

        # Ensure checkpoint table exists (might not be in older schema.sql)
        with pg.cursor() as ck:
            ck.execute("""
                CREATE TABLE IF NOT EXISTS silver.pipeline_checkpoints (
                    pipeline_name VARCHAR(100) NOT NULL,
                    stage VARCHAR(100) NOT NULL,
                    batch_id VARCHAR(20),
                    completed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    metadata JSONB,
                    PRIMARY KEY (pipeline_name, stage)
                )
            """)
        pg.commit()

        # ── Checkpoint Recovery: skip completed stages ─────────────────────
        skip_parents = False
        skip_children = False
        with pg.cursor() as cp:
            cp.execute("SELECT stage, batch_id, completed_at FROM silver.pipeline_checkpoints WHERE pipeline_name = 'silver'")
            for row in cp.fetchall():
                stage = row[0]
                if stage == 'parents_done':
                    skip_parents = True
                    self.log.info(f"[CHECKPOINT] Parents already completed (batch={row[1]}, at={row[2]}), skipping parents")
                elif stage == 'children_done':
                    skip_parents = True
                    skip_children = True
                    self.log.info(f"[CHECKPOINT] Children already completed (batch={row[1]}, at={row[2]}), skipping all Silver ETL")
        pg.commit()

        # Clear stale failure marker from previous interrupted runs
        _marker_failed = os.path.join(temp_root, ".silver.failed")
        _marker_completed = os.path.join(temp_root, ".silver.completed")
        try:
            for _m in (_marker_failed, _marker_completed):
                if os.path.exists(_m):
                    os.remove(_m)
        except OSError:
            pass

        if skip_children:
            self.log.info("Silver ETL fully complete from prior checkpoint — nothing to do")
            log.log_stage(stage="silver_transform", batch_id=batch_id,
                          status="complete", message="Skipped — all stages done from checkpoint")
            pg.close()
            conn.close()
            return

        # Clean partial/corrupted Silver state from previous failed runs
        # (only if not resuming from a parents_done checkpoint)
        if not skip_parents:
            with pg.cursor() as cleanup:
                cleanup.execute("TRUNCATE silver.title_genre, silver.title_director, silver.title_writer, silver.title_akas_type, silver.title_akas_attribute, silver.title_principal_char, silver.name_profession, silver.name_known_for_title")
            pg.commit()
            self.log.info("Truncated Silver child tables to clear partial/corrupted state")

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
        # name.basics have no primaryName, 2 rows in title.episode have no
        # parentTconst). These rows are skipped (quarantined implicitly)
        # rather than failing the entire COPY.
        not_null_filters = {
            "name.basics": "primaryName",
            "title.episode": "parentTconst",
        }

        _lock_fd = None
        try:
            total_rows = 0
            table_items = list(table_defs.items()) if not skip_parents else []
            for table_idx, (src_table, (dst_table, camel_cols, pk_cols)) in enumerate(table_items):
                self.log.info(f"  [{table_idx+1}/{len(table_items)}] Starting {src_table} -> {dst_table}...")
                parquet_url = f"{self.bronze_path}{src_table}.parquet"
                try:
                    conn.execute(f"SELECT 1 FROM read_parquet('{parquet_url}') LIMIT 0")
                except Exception:
                    self.log.warning(f"Parquet not found at {parquet_url}, skipping {src_table}")
                    continue

                # Build SELECT with column names from parquet (matches TSV headers)
                # Coalesce \N (IMDb null marker) to SQL NULL, and for NOT NULL
                # columns like isAdult, replace NULL with the default value.
                select_parts = []
                select_exprs = {}
                for col_name in camel_cols:
                    expr = f"\"{col_name}\""
                    expr = f"NULLIF({expr}, '\\N')"
                    default_val = not_null_fixes.get(col_name)
                    if default_val is not None:
                        expr = f"COALESCE({expr}, '{default_val}')"
                    if col_name in bool_casts:
                        expr = f"CASE WHEN {expr} = '1' THEN 't' WHEN {expr} = '0' THEN 'f' ELSE 'f' END"
                    select_parts.append(f"{expr} AS \"{col_name}\"")
                    select_exprs[col_name] = expr
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

                # R3: footer row count — no full scan for the pre-count
                row_count = _parquet_row_count(conn, parquet_url)

                if row_count == 0:
                    self.log.info(f"  {src_table}: 0 rows, skipping")
                    continue

                self.log.info(f"  {src_table}: {row_count} rows -> {dst_table}")

                # Build snake_case column list (needed before CSV export for SCD2 hashing)
                snake_cols = [camel_to_snake_map.get(c, c) for c in camel_cols]
                snake_cols_list = ", ".join(snake_cols)
                pg_cols_part = f"({snake_cols_list})"

                # ── SCD2 Merge (title_basics, name_basics) vs Truncate+Copy ──
                scd2_pk_map = {
                    "silver.title_basics": "tconst",
                    "silver.name_basics": "nconst",
                }
                is_scd2 = dst_table in scd2_pk_map

                # P0-3: SCD2 change detection — an md5 of the business
                # attributes is computed in DuckDB during the CSV export and
                # stored with every version. The expire/insert merge only
                # touches keys whose attr_hash differs from the current
                # version, so unchanged keys are no longer versioned on every
                # reload.
                audit_cols = {"is_current", "valid_from", "valid_to", "ingested_at", "batch_id"}
                attr_hash_expr = None
                if is_scd2:
                    hash_cols = [c for c, s in zip(camel_cols, snake_cols) if s not in audit_cols]
                    hash_values = ", ".join(f"COALESCE({select_exprs[c]}, '')" for c in hash_cols)
                    attr_hash_expr = f"md5(concat_ws('|', {hash_values}))"

                # Copy to CSV for PostgreSQL COPY (M4: use volume-backed csv_dir)
                # SCD2 tables append the attr_hash column (P0-3 change detection)
                csv_path = os.path.join(csv_dir, f"silver_{src_table.replace('.', '_')}.csv")
                export_select = select_sql
                if attr_hash_expr:
                    export_select += f", {attr_hash_expr} AS attr_hash"
                conn.execute(
                    "COPY (SELECT " + export_select + " FROM read_parquet('" + parquet_url + "')"
                    + where_clause + ") TO '" + csv_path + "' (FORMAT CSV, HEADER true, DELIMITER '|')"
                )

                with pg.cursor() as pg_cursor:
                    if is_scd2:
                        pk_col = scd2_pk_map[dst_table]
                        # Drop indexes for the specific table to speed up SCD2
                        # (recreated after load; if failure occurs mid-way, indexes are rebuilt)
                        pg_cursor.execute("SAVEPOINT sp_drop_idx")
                        try:
                            if dst_table == "silver.title_basics":
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_title_basics_tconst")
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_title_basics_current")
                            elif dst_table == "silver.name_basics":
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_name_basics_nconst")
                                pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_name_basics_current")
                        except Exception as e:
                            self.log.warning(f"Failed to drop index on {dst_table}: {e} — rolling back to savepoint")
                            pg_cursor.execute("ROLLBACK TO SAVEPOINT sp_drop_idx")
                        # Temp tables must be unqualified (no schema prefix)
                        stg_table = f"stg_{dst_table.replace('.', '_')}"

                        # Drop and recreate staging table (same structure minus SCD2/audit cols, plus attr_hash)
                        stg_cols = [c for c in snake_cols if c not in audit_cols]
                        stg_cols_list = ", ".join(stg_cols)
                        stg_create_cols = ", ".join(f"{c} VARCHAR" for c in stg_cols)
                        stg_create_cols += ", attr_hash VARCHAR(32)"

                        pg_cursor.execute(f"DROP TABLE IF EXISTS {stg_table}")
                        pg_cursor.execute(f"CREATE TEMP TABLE {stg_table} ({stg_create_cols})")

                        # Add index on PK for fast UPDATE ... WHERE pk IN (SELECT ...)
                        pg_cursor.execute(f"CREATE INDEX idx_{stg_table}_pk ON {stg_table} ({pk_col})")

                        # COPY into staging (attr_hash is the last CSV column)
                        stg_cols_part = f"({stg_cols_list}, attr_hash)"
                        with open(csv_path, "r") as f:
                            pg_cursor.copy_expert(
                                f"COPY {stg_table} {stg_cols_part} FROM STDIN WITH (FORMAT CSV, HEADER true, DELIMITER '|', NULL '')",
                                f,
                            )

                        # Expire current versions whose business attributes changed
                        pg_cursor.execute(f"""
                            UPDATE {dst_table}
                            SET valid_to = NOW(), is_current = FALSE
                            FROM {stg_table} s
                            WHERE {dst_table}.{pk_col} = s.{pk_col}
                              AND {dst_table}.is_current = TRUE
                              AND {dst_table}.attr_hash <> s.attr_hash
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
                            INSERT INTO {dst_table} ({stg_insert_cols}, valid_from, is_current, batch_id, ingested_at, attr_hash)
                            SELECT {stg_select_cols}, NOW(), TRUE, '{batch_id}', NOW(), s.attr_hash
                            FROM {stg_table} s
                            WHERE NOT EXISTS (
                                SELECT 1 FROM {dst_table} tb
                                WHERE tb.{pk_col} = s.{pk_col}
                                  AND tb.is_current
                                  AND tb.attr_hash = s.attr_hash
                            )
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
                if self.profile_memory:
                    _log_memory(conn, self.log, f"parent_{src_table}")

            # Commit parents before children — so a child failure doesn't roll back 2h of parent work
            pg.commit()
            # Save checkpoint: parents done
            with pg.cursor() as ck:
                ck.execute("""
                    INSERT INTO silver.pipeline_checkpoints (pipeline_name, stage, batch_id, completed_at, metadata)
                    VALUES ('silver', 'parents_done', %s, NOW(), %s)
                    ON CONFLICT (pipeline_name, stage)
                    DO UPDATE SET batch_id = EXCLUDED.batch_id, completed_at = NOW(), metadata = EXCLUDED.metadata
                """, (batch_id, json.dumps({"total_parent_rows": total_rows})))
            pg.commit()
            self.log.info(f"[CHECKPOINT] parents_done saved (batch={batch_id}, rows={total_rows})")
            conn.execute("CHECKPOINT")
            self.log.info("DuckDB temp checkpoint after parent tables, starting child normalization")
            if self.profile_memory:
                _log_memory(conn, self.log, "after_parent_tables")

            # ─── Normalize Child Tables ───────────────────────────────────────
            # SQL templates use {source} placeholder — replaced with
            # read_parquet('file.parquet') for full COPY or a shard subquery
            # for large sources. shard_key is the PK-leading column used to
            # hash-shard large sources (P0-1): all rows of a key stay in one
            # shard, keeping per-shard DISTINCT globally correct.
            child_table_defs = [
                {
                    "dst_table": "silver.title_genre",
                    "snake_cols": ["tconst", "genre"],
                    "src_table": "title.basics",
                    "shard_key": "tconst",
                    "sql": """
                        SELECT DISTINCT tconst, genre
                        FROM {source},
                        LATERAL UNNEST(string_split(NULLIF(genres, '\\N'), ',')) AS t(genre)
                        WHERE genres IS NOT NULL
                          AND genres != ''
                          AND genres != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.title_director",
                    "snake_cols": ["tconst", "ordering", "nconst"],
                    "src_table": "title.crew",
                    "shard_key": "tconst",
                    "sql": """
                        SELECT tconst,
                               CAST(ordinality AS SMALLINT) AS ordering,
                               nconst
                        FROM (
                          SELECT tconst,
                                 UNNEST(string_split(NULLIF(directors, '\\N'), ',')) AS nconst,
                                 generate_subscripts(string_split(NULLIF(directors, '\\N'), ','), 1) AS ordinality
                          FROM {source}
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
                    "shard_key": "tconst",
                    "sql": """
                        SELECT tconst,
                               CAST(ordinality AS SMALLINT) AS ordering,
                               nconst
                        FROM (
                          SELECT tconst,
                                 UNNEST(string_split(NULLIF(writers, '\\N'), ',')) AS nconst,
                                 generate_subscripts(string_split(NULLIF(writers, '\\N'), ','), 1) AS ordinality
                          FROM {source}
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
                    "shard_key": "titleId",
                    "sql": """
                        SELECT DISTINCT titleId AS title_id,
                               ordering,
                               type
                        FROM {source},
                        LATERAL UNNEST(string_split(NULLIF(types, '\\N'), ',')) AS t(type)
                        WHERE types IS NOT NULL
                          AND types != ''
                          AND types != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.title_akas_attribute",
                    "snake_cols": ["title_id", "ordering", "attr"],
                    "src_table": "title.akas",
                    "shard_key": "titleId",
                    "sql": """
                        SELECT DISTINCT titleId AS title_id,
                               ordering,
                               attr
                        FROM {source},
                        LATERAL UNNEST(string_split(NULLIF(attributes, '\\N'), ',')) AS t(attr)
                        WHERE attributes IS NOT NULL
                          AND attributes != ''
                          AND attributes != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.title_principal_char",
                    "snake_cols": ["tconst", "ordering", "character_name"],
                    "src_table": "title.principals",
                    "shard_key": "tconst",
                    "sql": """
                        SELECT DISTINCT tconst,
                               ordering,
                               TRIM(character_val, '"') AS character_name
                        FROM {source},
                        LATERAL UNNEST(
                            string_split(TRIM(NULLIF(characters, '\\N'), '[]'), '","')
                        ) AS t(character_val)
                        WHERE characters IS NOT NULL
                          AND characters != ''
                          AND characters != '\\N'
                    """,
                },
                {
                    "dst_table": "silver.name_profession",
                    "snake_cols": ["nconst", "profession_order", "profession"],
                    "src_table": "name.basics",
                    "shard_key": "nconst",
                    "sql": """
                        SELECT nconst,
                               CAST(ordinality AS SMALLINT) AS profession_order,
                               profession
                        FROM (
                          SELECT nconst,
                                 UNNEST(string_split(NULLIF(primaryProfession, '\\N'), ',')) AS profession,
                                 generate_subscripts(string_split(NULLIF(primaryProfession, '\\N'), ','), 1) AS ordinality
                          FROM {source}
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
                    "shard_key": "nconst",
                    "sql": """
                        SELECT nconst,
                               CAST(ordinality AS SMALLINT) AS known_for_order,
                               tconst
                        FROM (
                          SELECT nconst,
                                 UNNEST(string_split(NULLIF(knownForTitles, '\\N'), ',')) AS tconst,
                                 generate_subscripts(string_split(NULLIF(knownForTitles, '\\N'), ','), 1) AS ordinality
                          FROM {source}
                          WHERE knownForTitles IS NOT NULL
                            AND knownForTitles != ''
                            AND knownForTitles != '\\N'
                        ) sub
                    """,
                },
            ]

            child_rows = 0
            # R2: drop secondary indexes on the child tables before bulk load.
            # Recreated after the loop (and in the except path on failure).
            with pg.cursor() as idxc:
                for _tbl, _idxs in CHILD_SECONDARY_INDEXES.items():
                    for _name, _ddl in _idxs:
                        idxc.execute(f"DROP INDEX IF EXISTS silver.{_name}")
                # R2-ext: FK constraints on FK-backed children are dropped for
                # the load too (per-row RI probes dominate; re-added below).
                for _tbl, _fks in CHILD_FK_CONSTRAINTS.items():
                    for _name, _ddl in _fks:
                        idxc.execute(f"ALTER TABLE {_tbl} DROP CONSTRAINT IF EXISTS {_name}")
            pg.commit()
            self.log.info("[R2] Dropped secondary indexes + FK constraints on child tables for bulk load")

            for child_idx, child in enumerate(child_table_defs):
                child_parquet_url = f"{self.bronze_path}{child['src_table']}.parquet"
                try:
                    conn.execute(f"SELECT 1 FROM read_parquet('{child_parquet_url}') LIMIT 0")
                except Exception:
                    self.log.warning(f"Child parquet not found at {child_parquet_url}, skipping {child['dst_table']}")
                    continue

                self.log.info(f"  [{child_idx+1}/{len(child_table_defs)}] Starting {child['dst_table']}...")

                # R3: footer row count — no full scan for the pre-count
                total_src = _parquet_row_count(conn, child_parquet_url)

                if total_src == 0:
                    self.log.info(f"  {child['dst_table']}: 0 source rows, skipping")
                    continue

                # R1: partition the source once (single S3 pass) into
                # _shard=N/ directories, then load each shard from its own
                # files (1/16 of the source per shard). Replaces the
                # materialized-table + WHERE _shard=N re-scan of the whole
                # source per shard (~17x total reads -> ~2x).
                src_tbl_name = child["src_table"].replace('.', '_')
                part_dir = os.path.join(duckdb_temp, "partitioned", src_tbl_name)
                shard_key = child.get("shard_key", child["snake_cols"][0])
                self.log.info(f"  {child['dst_table']}: {total_src:,} source rows, partitioning by {shard_key} ({CHILD_SHARD_COUNT} shards)")
                _partition_child_source(conn, child_parquet_url, part_dir, shard_key, self.log)

                try:
                    with pg.cursor() as pg_cursor:
                        pg_cursor.execute(f"TRUNCATE {child['dst_table']}")
                        loaded = _process_child_table_sharded(conn, pg_cursor, child, part_dir, self.log)
                finally:
                    # R1 stale-dir guard: drop the partition dir even on failure
                    import shutil
                    shutil.rmtree(part_dir, ignore_errors=True)

                child_rows += loaded
                self.log.info(f"  {child['dst_table']}: {loaded} rows loaded (sharded)")
                log.log_stage(stage="silver_transform", batch_id=batch_id,
                              status="success", row_count=loaded,
                              message=f"child {child['dst_table']} (sharded)")

                if self.profile_memory:
                    _log_memory(conn, self.log, f"child_{child['dst_table']}")

                # Flush DuckDB temp between child-table UNNESTs to bound peak RSS
                conn.execute("CHECKPOINT")

            pg.commit()
            # R2: recreate secondary indexes after all child tables load
            with pg.cursor() as idxc:
                for _tbl, _idxs in CHILD_SECONDARY_INDEXES.items():
                    for _name, _ddl in _idxs:
                        idxc.execute(_ddl)
                # R2-ext: re-add FK constraints NOT VALID and validate them.
                # VALIDATE is one streaming anti-join scan per child (vs the
                # per-row RI probes that dominated load time).
                for _tbl, _fks in CHILD_FK_CONSTRAINTS.items():
                    for _name, _ddl in _fks:
                        idxc.execute(f"ALTER TABLE {_tbl} ADD CONSTRAINT {_name} {_ddl} NOT VALID")
                        self.log.info(f"  {_tbl}: validating FK {_name}")
                        idxc.execute(f"ALTER TABLE {_tbl} VALIDATE CONSTRAINT {_name}")
            pg.commit()
            self.log.info("[R2] Recreated secondary indexes + validated FK constraints on child tables")
            # P3-12: refresh planner statistics so wait_silver's n_live_tup
            # polling (and dbt's incremental filtering) sees accurate counts
            with pg.cursor() as an:
                an.execute("ANALYZE silver.title_basics, silver.title_akas, silver.title_episode, silver.title_rating, silver.title_principal, silver.name_basics, silver.title_genre, silver.title_director, silver.title_writer, silver.title_akas_type, silver.title_akas_attribute, silver.title_principal_char, silver.name_profession, silver.name_known_for_title")
            pg.commit()
            # Save checkpoint: children done
            with pg.cursor() as ck:
                ck.execute("""
                    INSERT INTO silver.pipeline_checkpoints (pipeline_name, stage, batch_id, completed_at, metadata)
                    VALUES ('silver', 'children_done', %s, NOW(), %s)
                    ON CONFLICT (pipeline_name, stage)
                    DO UPDATE SET batch_id = EXCLUDED.batch_id, completed_at = NOW(), metadata = EXCLUDED.metadata
                """, (batch_id, json.dumps({"total_parent_rows": total_rows, "total_child_rows": child_rows})))
            pg.commit()
            self.log.info(f"[CHECKPOINT] children_done saved (batch={batch_id}, parent_rows={total_rows}, child_rows={child_rows})")
            elapsed = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
            self.log.info(f"Silver ETL complete: {total_rows} parent rows + {child_rows} child rows across {len(table_defs) + len(child_table_defs)} tables")
            log.log_stage(stage="silver_transform", batch_id=batch_id,
                          status="complete", row_count=total_rows + child_rows,
                          duration_ms=elapsed,
                          message=f"{total_rows} parent + {child_rows} child rows")
            try:
                with open(_marker_completed, "w") as _mf:
                    _mf.write(datetime.now(timezone.utc).isoformat())
            except OSError:
                pass
        except Exception as e:
            self.log.error(f"Silver ETL failed: {e}")
            log.log_error(stage="silver_transform", batch_id=batch_id,
                          error=f"Silver ETL failed: {e}")
            try:
                with open(_marker_failed, "w") as _mf:
                    _mf.write(f"{e}\n")
            except OSError:
                pass
            try:
                pg.rollback()
            except Exception:
                pass
            # R2: a failed run must not leave the child secondary indexes
            # dropped (they were committed before the child loop)
            try:
                with pg.cursor() as idxc:
                    for _tbl, _idxs in CHILD_SECONDARY_INDEXES.items():
                        for _name, _ddl in _idxs:
                            idxc.execute(_ddl)
                    # R2-ext: re-add FK constraints NOT VALID (schema intact;
                    # the next successful run validates them)
                    for _tbl, _fks in CHILD_FK_CONSTRAINTS.items():
                        for _name, _ddl in _fks:
                            idxc.execute(f"ALTER TABLE {_tbl} ADD CONSTRAINT {_name} {_ddl} NOT VALID")
                pg.commit()
            except Exception:
                pass
            raise
        finally:
            conn.close()
            # Clean up temp CSV files (M4: check both old /tmp and volume paths)
            try:
                import glob as _glob
                for _p in ("/tmp/", csv_dir):
                    for csv_file in _glob.glob(os.path.join(_p, "silver_*.csv")):
                        try:
                            os.remove(csv_file)
                        except Exception:
                            pass
            except Exception:
                pass
            # M1: Clean up DuckDB file and temp files
            try:
                import shutil
                if os.path.exists(duckdb_file):
                    os.remove(duckdb_file)
                if os.path.exists(duckdb_temp):
                    shutil.rmtree(duckdb_temp, ignore_errors=True)
            except Exception as e:
                self.log.warning(f"Failed to clean up DuckDB temp files: {e}")
            # Release file lock before closing connection
            try:
                _release_silver_file_lock(_lock_fd, os.path.join(temp_root, "silver.lock"))
            except Exception:
                pass
            pg.close()


if __name__ == "__main__":
    operator = SilverTransformOperator(
        task_id="silver_transform_standalone",
    )
    operator.execute({})
