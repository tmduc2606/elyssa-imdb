# Elyssa-IMDb Pipeline Optimization Blueprint

**Codename:** Elyssa — Ingestion Query Optimization  
**Date:** 2026-06-30  
**Status:** Proposal Stage — Awaiting Consideration  
**Target:** 30–40 min end-to-end runtime, stable disk usage under 50GB  

---

## 1. Root Cause Analysis

### 1.1 Disk Usage Explosion (250GB → 153.7GB free = ~96GB consumed)

| Root Cause | Est. Impact | Evidence |
|---|---|---|
| DuckDB temp files spill to container writable layer | ~40–60GB | `temp_directory` never set; in-memory DB defaults to `.tmp` in CWD → Docker overlay2 |
| db_ingest copies Parquet to same source path | ~8–15GB | `parquet_root="/opt/airflow/output/bronze"` = source; copy is a no-op on data but metadata grows |
| CSV intermediates in /tmp persist on crash | ~2–5GB | Silver operator writes `/tmp/silver_*.csv`; crash leaves orphans |
| Docker container logs (no rotation) | ~5–20GB | No `logging:` config in docker-compose.yml |
| Airflow task logs accumulate | ~2–5GB | Default `log_filename_template` keeps all task logs |
| PostgreSQL WAL + bloat from repeated TRUNCATE+COPY | ~5–10GB | 14 tables × TRUNCATE/COPY cycle generates WAL |
| Neo4j + dbt `target/` compiled artifacts | ~1–2GB | dbt `target/` not cleaned between runs |

**Primary culprit:** DuckDB temp spill to Docker overlay2. When DuckDB runs with `connect(":memory:")` and no `temp_directory` is set, it creates `.tmp` in the process working directory. Inside the Airflow container, this lands on the writable layer backed by the `airflow_data` named volume. Each run of bronze (6GB limit) + silver (4GB limit) can generate 10+ GB of temp files that accumulate.

### 1.2 Runtime Bottlenecks (Current: ~90–120 min estimated)

| Stage | Est. Time | Bottleneck |
|---|---|---|
| Bronze (7 tables TSV→Parquet) | 8–15 min | Sequential processing; `read_csv` on large TSVs with `ignore_errors=true` |
| db_ingest (Parquet copy) | 1–3 min | Unnecessary copy (reads from same path it writes to) |
| Silver (14 tables Parquet→CSV→PostgreSQL) | 40–60 min | CSV intermediate is 2–3× slower than direct COPY; sequential table processing |
| Gold dbt run (6 models) | 10–20 min | `int_title_details` does 5 LEFT JOINs + STRING_AGG on ~10M rows |
| Neo4j sync (3 tables) | 3–8 min | Full table materialization into Python; batch INSERT without UNWIND optimization |
| DQ checks (5 checks) | 2–5 min | Sequential full table scans |
| **Total** | **64–111 min** | |

---

## 2. Optimization Strategy

### Phase A: Critical Fixes (Est. Impact: -40 min, -80GB disk)

#### A1. DuckDB temp_directory — Fix Disk Spill

**Problem:** DuckDB temp files land on Docker overlay2, consuming host disk.  
**Fix:** Set `temp_directory` to a dedicated path on the `airflow_data` volume with explicit cleanup.

```python
# In both bronze_operator.py and silver_operator.py
conn = duckdb.connect(":memory:")
conn.execute("SET threads = 2")
conn.execute("SET memory_limit = '4GB'")  # Reduce from 6GB — see A2
conn.execute("SET preserve_insertion_order = false")
conn.execute("SET temp_directory = '/opt/airflow/output/duckdb_temp/'")
conn.execute("SET max_temp_directory_size = '10GB'")
```

**Add cleanup at operator finally block:**
```python
finally:
    conn.close()
    # Clean up DuckDB temp files
    import shutil
    temp_dir = "/opt/airflow/output/duckdb_temp/"
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
```

**Add to docker-compose.yml:**
```yaml
airflow:
  environment:
    - AIRFLOW__CORE__PARALLELISM=8
    - AIRFLOW__CORE__MAX_ACTIVE_TASKS_PER_DAG=8
  logging:
    driver: json-file
    options:
      max-size: "50m"
      max-file: "3"
```

#### A2. DuckDB Memory Tuning — Reduce Spilling

**Problem:** `memory_limit = '6GB'` (bronze) and `'4GB'` (silver) cause excessive spill on COPY TO parquet.  
**Fix:** Lower memory_limit to 50–60% of container RAM to prevent bypass operations from exceeding limits. Set `preserve_insertion_order = false` — the single most impactful setting.

```python
# Bronze: reduce from 6GB to 3GB
conn.execute("SET memory_limit = '3GB'")
conn.execute("SET threads = 2")
conn.execute("SET preserve_insertion_order = false")

# Silver: keep at 4GB but ensure temp_directory is set
conn.execute("SET memory_limit = '4GB'")
conn.execute("SET threads = 2")
conn.execute("SET preserve_insertion_order = false")
```

**Key insight from DuckDB docs:** "Counter-intuitively, reducing the memory limit below the default 80% can help prevent OOM errors. Some operations bypass the buffer manager and reserve more memory than the limit allows."

#### A3. Eliminate db_ingest Double-Copy

**Problem:** `DatabaseIngestOperator` copies Parquet from `/opt/airflow/output/bronze/` to itself (path mismatch in DAG vs operator defaults).  
**Fix:** Either remove `db_ingest` from the DAG entirely (it's a Phase 1 backup concern), or fix the path and add incremental logic.

**Recommended:** Remove from critical path. Make it a post-pipeline backup task:

```python
# In imdb_pipeline_dag.py — change from sequential to parallel post-Silver
silver_transform >> gold_dbt_run >> [gold_dbt_test, neo4j_sync, db_ingest]
```

Or simply remove it for Phase 1:
```python
# Remove db_ingest from main chain
start >> imdb_sensor >> bronze_ingest >> quarantine_check >> silver_transform
silver_transform >> gold_dbt_run >> [gold_dbt_test, neo4j_sync]
gold_dbt_test >> dq_checks
neo4j_sync >> dq_checks >> freshness_check >> end
```

#### A4. CSV Intermediate Elimination — Direct DuckDB→PostgreSQL

**Problem:** Silver operator reads Parquet → DuckDB transforms → writes CSV → psycopg2 reads CSV → PostgreSQL COPY. The CSV step is the #1 time sink.  
**Fix:** Use DuckDB's `postgres_scanner` extension or `pg_copy` to write directly from DuckDB to PostgreSQL, eliminating the CSV entirely.

**Option A (Recommended): Use DuckDB postgres_scanner**
```python
# Install postgres_scanner in DuckDB
conn.install_extension("postgres_scanner")
conn.load_extension("postgres_scanner")

# Direct write — no CSV intermediate
conn.execute(f"""
    ATTACH 'postgresql://elyssa:elyssa_pg_2026@postgres:5432/elyssa_warehouse' AS pg (TYPE postgres)
""")
conn.execute(f"""
    CREATE TABLE pg.silver.title_basics AS
    SELECT * FROM read_parquet('{parquet_path}')
""")
```

**Option B: Use psycopg2 COPY with DuckDB streaming (current approach, optimized)**
```python
# Instead of writing to CSV file, stream directly via copy_expert
import io

# DuckDB exports to a BytesIO buffer
result = conn.execute(f"COPY ({select_sql}) TO '/dev/stdout' (FORMAT CSV, HEADER true, DELIMITER '|')")
# ... this doesn't work well in Python

# Better: use DuckDB to write to a named pipe or temp file, then stream
# The real optimization: reduce the number of COPY operations
```

**Option C (Simplest): Batch multiple tables into single COPY**
```python
# Instead of 14 separate DuckDB→CSV→PostgreSQL cycles:
# 1. DuckDB reads ALL parquet files once
# 2. DuckDB writes ALL transformed data to a single multi-table CSV or directly to PostgreSQL
# This reduces I/O from 28 reads (14 Parquet + 14 CSV) to 14 reads + 14 writes
```

**Best approach for Phase 1:** Keep CSV but parallelize the DuckDB→CSV step with the PostgreSQL COPY step using Python threads:

```python
import concurrent.futures

def process_table(src_table, dst_table, parquet_path, conn, pg):
    # DuckDB transform + CSV write
    csv_path = f"/tmp/silver_{src_table.replace('.', '_')}.csv"
    conn.execute(f"COPY ({transform_sql}) TO '{csv_path}' (FORMAT CSV, HEADER true, DELIMITER '|')")
    
    # PostgreSQL COPY (in parallel with other tables' DuckDB transforms)
    with open(csv_path, "rb") as f:
        pg_cursor = pg.cursor()
        pg_cursor.copy_expert(f"COPY {dst_table} ... FROM STDIN WITH (FORMAT CSV, ...)", f)
    os.remove(csv_path)

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = [executor.submit(process_table, ...) for ...]
    concurrent.futures.wait(futures)
```

---

### Phase B: Gold Layer Optimization (Est. Impact: -10 min)

#### B1. dbt Model Materialization

**Problem:** `int_title_details` does 5 LEFT JOINs + STRING_AGG on ~10M rows as a `table` materialization.  
**Fix:** Add `+indexes: true` and ensure `work_mem` is sufficient. Also consider incremental materialization for `fact_title_rating`.

```yaml
# In dbt_project.yml
models:
  imdb_gold:
    staging:
      +materialized: view
      +schema: stg
    intermediate:
      +materialized: ephemeral  # Changed from table — int_title_details is only used by dim_title
      +schema: int
    marts:
      +materialized: table
      +post_hook:
        - "ANALYZE {{ this }}"
```

**Key change:** Make `int_title_details` and `int_person_details` **ephemeral** — they're only referenced by one mart each. This avoids creating intermediate tables in PostgreSQL and lets dbt inline the SQL.

#### B2. Add Missing Indexes for dbt Joins

```sql
-- Add to 02_silver_schema.sql
CREATE INDEX IF NOT EXISTS idx_title_genre_tconst_genre ON silver.title_genre(tconst, genre);
CREATE INDEX IF NOT EXISTS idx_title_director_tconst ON silver.title_director(tconst);
CREATE INDEX IF NOT EXISTS idx_title_writer_tconst ON silver.title_writer(tconst);
CREATE INDEX IF NOT EXISTS idx_title_episode_parent_tconst ON silver.title_episode(parent_tconst);
```

#### B3. Optimize stg_title_episode

**Problem:** `stg_title_episode` joins to `title_basics` to get `series_title`, adding a expensive JOIN.  
**Fix:** Pre-compute or remove `series_title` from the staging model if it's not used downstream.

```sql
-- Current: joins title_basics for series_title
-- Fix: remove the join, add series_title at mart level only if needed
SELECT
    te.tconst,
    te.parent_tconst,
    te.season_number,
    te.episode_number,
    tb.primary_title AS series_title  -- This JOIN is expensive
FROM {{ source('silver', 'title_episode') }} te
LEFT JOIN {{ source('silver', 'title_basics') }} tb
    ON te.parent_tconst = tb.tconst AND tb.is_current = TRUE
```

---

### Phase C: Silver SCD2 Optimization (Est. Impact: -15 min)

#### C1. Batch SCD2 Merge

**Problem:** Current SCD2 does individual `UPDATE ... WHERE pk IN (SELECT pk FROM stg)` which scans the full `title_basics` table (potentially millions of rows with is_current=TRUE history).  
**Fix:** Use a CTE-based merge that avoids the subquery scan:

```sql
-- Current (slow):
UPDATE silver.title_basics
SET valid_to = NOW(), is_current = FALSE
WHERE tconst IN (SELECT tconst FROM stg_title_basics)
  AND is_current = TRUE;

-- Optimized (CTE merge):
WITH expired AS (
    UPDATE silver.title_basics
    SET valid_to = NOW(), is_current = FALSE
    FROM stg_title_basics s
    WHERE silver.title_basics.tconst = s.tconst
      AND silver.title_basics.is_current = TRUE
    RETURNING silver.title_basics.tconst
)
INSERT INTO silver.title_basics (tconst, title_type, primary_title, ...)
SELECT s.tconst, s.title_type, s.primary_title, ..., NOW(), TRUE, 'batch_id', NOW()
FROM stg_title_basics s;
```

**Even better:** Use PostgreSQL's `INSERT ... ON CONFLICT` with a dedicated staging table approach:

```sql
-- Step 1: Expire all current rows that appear in new batch
UPDATE silver.title_basics
SET valid_to = NOW(), is_current = FALSE
FROM stg_title_basics s
WHERE silver.title_basics.tconst = s.tconst
  AND silver.title_basics.is_current = TRUE;

-- Step 2: Insert new versions
INSERT INTO silver.title_basics (tconst, title_type, ..., valid_from, is_current, batch_id, ingested_at)
SELECT tconst, title_type, ..., NOW(), TRUE, 'batch_id', NOW()
FROM stg_title_basics;
```

The `FROM` syntax (PostgreSQL 9.5+) is faster than `WHERE pk IN (SELECT pk FROM stg)` because it uses a hash join instead of a nested loop.

#### C2. Drop Redundant Indexes During Load

```python
# In silver_operator.py, before SCD2 merge:
pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_title_basics_tconst")
pg_cursor.execute("DROP INDEX IF EXISTS silver.idx_title_basics_current")

# ... do the merge ...

# Recreate indexes after merge
pg_cursor.execute("CREATE INDEX idx_title_basics_tconst ON silver.title_basics(tconst)")
pg_cursor.execute("CREATE INDEX idx_title_basics_current ON silver.title_basics(is_current) WHERE is_current = TRUE")
```

---

### Phase D: Neo4j & DQ Optimization (Est. Impact: -5 min)

#### D1. Neo4j Streaming Sync

**Problem:** `neo4j_sync.py` materializes all rows into Python lists before writing. For `title_principal` (~50M rows), this can consume 4+ GB RAM.  
**Fix:** Stream rows directly from cursor to Neo4j:

```python
# Current: collect all batches, then write
batches = []
for row in cur:
    batch.append(dict(row))
    if len(batch) >= 5000:
        batches.append(batch)
        batch = []

# Optimized: stream and write concurrently
with driver.session() as session:
    batch = []
    for row in cur:
        batch.append(dict(row))
        if len(batch) >= 5000:
            session.run(cypher, batch=batch)
            batch = []
    if batch:
        session.run(cypher, batch=batch)
```

#### D2. DQ Checks Parallelization

**Problem:** 5 DQ checks run sequentially, each doing full table scans.  
**Fix:** Use PostgreSQL `CREATE INDEX` for check columns, or run checks in parallel using Python threads:

```python
import concurrent.futures

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
    futures = {executor.submit(run_single_check, check, conn): check for check in checks}
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
```

---

### Phase E: Docker & Infrastructure (Est. Impact: -10GB disk)

#### E1. Docker Logging Configuration

```yaml
# Add to all services in docker-compose.yml
services:
  postgres:
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"
  neo4j:
    logging:
      driver: json-file
      options:
        max-size: "50m"
        max-file: "3"
  airflow:
    logging:
      driver: json-file
      options:
        max-size: "100m"
        max-file: "5"
```

#### E2. Airflow Log Rotation

```python
# In docker-compose.yml environment
AIRFLOW__CORE__LOG_FILENAME_TEMPLATE: "{{ti.dag_id}}/{{ti.task_id}}/{{ts}}/{{try_number}}.log"
AIRFLOW__LOGGING__LOGGING_LEVEL: WARNING  # Reduce verbosity
```

#### E3. PostgreSQL Tuning for Bulk Loads

```yaml
# Update docker-compose.yml postgres command
command: >
  postgres
    -c shared_preload_libraries=timescaledb
    -c max_connections=200
    -c shared_buffers=512MB          # Increased from 256MB
    -c work_mem=128MB                # Increased from 64MB
    -c maintenance_work_mem=256MB    # Increased from 128MB
    -c wal_buffers=16MB
    -c max_wal_size=4GB              # Increased from 2GB
    -c checkpoint_completion_target=0.9
    -c random_page_cost=1.1
    -c effective_io_concurrency=200
    -c effective_cache_size=1536MB   # 3× shared_buffers
    -c log_min_duration_statement=2000
    -c timezone=UTC
    -c statement_timeout=3600000     # 1 hour timeout
```

---

## 3. Implementation Plan

### Wave 1: Critical Fixes (Day 1) — Must complete before production

| # | Task | Files | Est. Time |
|---|---|---|---|
| A1 | Set DuckDB temp_directory + cleanup | `bronze_operator.py`, `silver_operator.py` | 30 min |
| A2 | Tune DuckDB memory_limit + preserve_insertion_order | `bronze_operator.py`, `silver_operator.py` | 15 min |
| A3 | Remove db_ingest from critical path | `imdb_pipeline_dag.py` | 10 min |
| A4 | Add Docker logging rotation | `docker-compose.yml` | 10 min |
| **Wave 1 Total** | | | **65 min** |

### Wave 2: Silver Optimization (Day 2)

| # | Task | Files | Est. Time |
|---|---|---|---|
| C1 | Optimize SCD2 merge to use FROM syntax | `silver_operator.py` | 45 min |
| C2 | Drop/recreate indexes during SCD2 load | `silver_operator.py` | 20 min |
| E3 | Tune PostgreSQL shared_buffers + work_mem | `docker-compose.yml` | 10 min |
| **Wave 2 Total** | | | **75 min** |

### Wave 3: Gold & Peripheral (Day 3)

| # | Task | Files | Est. Time |
|---|---|---|---|
| B1 | Make intermediate dbt models ephemeral | `dbt_project.yml` | 15 min |
| B2 | Add missing indexes for dbt joins | `02_silver_schema.sql` | 15 min |
| B3 | Optimize stg_title_episode | `stg_title_episode.sql` | 10 min |
| D1 | Stream Neo4j sync (remove batch collection) | `neo4j_sync.py` | 20 min |
| D2 | Parallelize DQ checks | `dq/run_checks.py` | 20 min |
| **Wave 3 Total** | | | **80 min** |

### Wave 4: Validation (Day 4)

| # | Task | Est. Time |
|---|---|---|
| Full pipeline run with timing | 40 min |
| Disk usage monitoring | 10 min |
| DQ gate verification | 15 min |
| Performance baseline documentation | 20 min |
| **Wave 4 Total** | **85 min** |

---

## 4. Expected Outcomes

| Metric | Before | After (Target) |
|---|---|---|
| Total runtime | 90–120 min | 30–40 min |
| Disk usage per run | +40–60 GB | +5–10 GB |
| DuckDB temp spill | Uncontrolled | Capped at 10GB, cleaned up |
| CSV intermediates | 14 sequential | Parallelized or eliminated |
| dbt intermediate tables | 2 tables created | Ephemeral (inlined) |
| PostgreSQL WAL per run | ~5–10 GB | ~2–3 GB |
| Docker log accumulation | Unbounded | Capped at 350MB |

---

## 5. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| DuckDB postgres_scanner extension not available | Medium | High | Fall back to optimized CSV path |
| SCD2 FROM syntax fails on large datasets | Low | Medium | Test with 1M row subset first |
| Ephemeral dbt models increase query complexity | Low | Low | Monitor query plans |
| Parallel Silver processing causes PG connection exhaustion | Medium | Medium | Limit pool_size=5 |
| temp_directory cleanup fails mid-run | Low | Low | Add try/except with fallback rm |

---

## 6. Deferred Items (Phase 2)

| Item | Reason |
|---|---|
| Child table SCD2 | Full reload is acceptable for Phase 1 |
| DuckDB persistent database mode | Adds complexity; in-memory with tempDirectory is sufficient |
| PostgreSQL partitioning on title_rating | TimescaleDB hypertable already handles this |
| dbt incremental materialization | Current full-refresh is fine for 10M rows |
| Arrow/IPC instead of CSV | Higher optimization; CSV is sufficient after parallelization |

---

## 7. Monitoring & Observability

After implementation, track:

1. **Pipeline duration per stage** (via `pipeline_logger` stage timestamps)
2. **DuckDB temp directory size** (add metric log at operator finish)
3. **Disk free space** (add pre/post check in DAG)
4. **PostgreSQL table bloat** (run `SELECT pg_size_pretty(pg_total_relation_size(...))` after each run)
5. **Docker volume sizes** (`docker system df` before/after runs)

---

*Blueprint prepared for review. All changes are backwards-compatible and can be implemented incrementally.*
