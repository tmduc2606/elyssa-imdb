# DE Pipeline Optimization Plan

**Codename: Elyssa** — Phase 1 Production Data Engineering
_Derived from specialized_assessment.md findings_
**Hardware:** AMD Athlon 200GE (2C/4T), 16 GB RAM
**Baseline runtime:** ~5h 30m (Bronze 47m → Silver 3.5h → Gold 63m → Export 15m)
**Assessment reference:** A1-A16 in `specialized_assessment.md`

---

## Tier Strategy

| Tier | Type | Impact | Risk | Items |
|------|------|--------|------|-------|
| T1 | Safety & correctness | Prevents OOM, fixes broken data | None | A1-A8 |
| T2 | Performance & quality | Reduces runtime 20-40% | Low | A9-A13 |
| T3 | Architectural | Reduces runtime 60-70% | Medium | A14-A16 |

---

## Tier 1 — Safety & Correctness (0 dev hours config, 2-3 days implementation)

### T1.1 Wire `etl-runner` Container into Silver DAG

**Assessment ref:** A2 (P0 — `etl-runner` exists but unused)
**File:** `imdb_pipeline_dag.py`, `docker-compose.yml`

**Problem:** Silver DuckDB runs inside Airflow container (4 GB limit), sharing RAM with webserver and scheduler. The `etl-runner` container (6 GB, `mem_limit: 6g`) already exists in `mlops/docker-compose.yml` but is never used.

**Solution:** Add `etl-runner` to `docker/docker-compose.yml` and wire it into the DAG:

```yaml
# docker/docker-compose.yml
etl-runner:
  image: elyssa-etl-runner:latest
  build:
    context: ..
    dockerfile: docker/Dockerfile.etl-runner
  container_name: elyssa-etl-runner
  mem_limit: 6g
  memswap_limit: 8g
  oom_score_adj: -500
  environment:
    DUCKDB_MEMORY_LIMIT: "4GB"
    DUCKDB_THREADS: "2"
    POSTGRES_HOST: postgres
    POSTGRES_USER: ${POSTGRES_USER:-elyssa}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
  volumes:
    - ../data-engineering:/opt/etl/data-engineering:rw
    - airflow_data:/opt/etl/output:rw
    - etl_temp:/opt/etl/tmp:rw
  shm_size: 2g
  networks:
    - elyssa-net
  restart: "no"
```

In the DAG, replace `SilverTransformOperator` with a `DockerOperator` or `SSHOperator` that triggers silver_operator.py inside the etl-runner container:

```python
# imdb_pipeline_dag.py — using DockerOperator
from airflow.providers.docker.operators.docker import DockerOperator

silver_transform = DockerOperator(
    task_id="silver_transform",
    image="elyssa-etl-runner:latest",
    command="python /opt/etl/data-engineering/orchestration/operators/silver_operator.py",
    docker_url="unix://var/run/docker.sock",
    network_mode="elyssa-net",
    mount_tmp_dir=False,
    auto_remove=True,
    environment={
        "DUCKDB_MEMORY_LIMIT": "4GB",
        "POSTGRES_HOST": "postgres",
    },
    execution_timeout=timedelta(hours=6),
)
```

**Rationale:** If the `etl-runner` is in `mlops/docker-compose.yml` and the Airflow pipeline runs in `docker/docker-compose.yml`, they are separate compose stacks. The simpler approach is to remove the `etl-runner` from mlops/ and add it to `docker/docker-compose.yml` where the Airflow instance lives, so they share a Docker network.

**Est. impact:** Eliminates OOM on Silver UNNEST (peak usage moves from 3.5 GB in 4 GB container to ~4.5 GB in 6 GB container).

### T1.2 Fix Silver DuckDB memory_limit

**Assessment ref:** A1 (P0 — 2.5 GB in 4 GB container is unsafe)
**File:** `silver_operator.py:132`

```python
# Before (line 132)
conn.execute("SET memory_limit = '2.5GB'")

# After
conn.execute("SET memory_limit = '1.2GB'")  # 60% of remaining budget after Airflow
```

With the `etl-runner` container (T1.1), change to:
```python
conn.execute("SET memory_limit = '4GB'")  # 67% of 6 GB container
```

### T1.3 Fix Gold PK Grains

**Assessment ref:** A3 (P0), A4 (P0)
**Files:** `gold/models/marts/schema.yml`, `gold/models/marts/episodic_content/schema.yml`

**fact_performance** — change PK from `(tconst, nconst, category)` to `(title_key, name_key, ordering)`:

```yaml
# In gold/models/marts/schema.yml
- name: fact_performance
  columns:
    - name: title_key
      tests: [not_null]
    - name: name_key
      tests: [not_null]
    - name: ordering
      tests: [unique, not_null]
      description: "PK: (title_key, name_key, ordering) — unique per credit position"
```

**fact_episode** — change PK from `(series_key, season_number, episode_number)` to `(episode_key)`:

```yaml
# In gold/models/marts/episodic_content/schema.yml
- name: fact_episode
  columns:
    - name: episode_key
      tests: [unique, not_null]
      description: "PK: tconst of the episode itself"
```

### T1.4 Remove Dead PySpark Code

**Assessment ref:** A5 (P1)
**Files:** `silver/scd2_transform.py`, `silver/transform.py`, `silver/upsert.py`

**Actions:**
- `silver/scd2_transform.py`: Remove or deprecate all 144 lines. Add `# DEPRECATED — use inline SCD2 in silver_operator.py` header. The functions `generate_scd2_columns()`, `compute_scd2_close_sql()`, `build_scd2_merge_sql()` use PySpark `DataFrame` which is stripped from the Docker image.
- `silver/transform.py`: Remove unused ARRAY_FIELDS, TYPE_MAP, null_to_empty, rename_to_silver, explode_array — all PySpark-based and superseded by DuckDB SQL in silver_operator.py.
- `silver/upsert.py`: Remove `generate_merge_sql()` — never called.

**Est. impact:** Eliminates ~250 lines of dead code, removes confusion about which transform path is active.

### T1.5 Verify & Fix Child Table Population

**Assessment ref:** A6 (P1)
**Files:** `silver_operator.py:498-539`

**Action:** Against live PostgreSQL, verify row counts for:
```sql
SELECT 'title_akas_type' AS tbl, COUNT(*) FROM silver.title_akas_type
UNION ALL
SELECT 'title_akas_attribute', COUNT(*) FROM silver.title_akas_attribute
UNION ALL
SELECT 'title_principal_char', COUNT(*) FROM silver.title_principal_char;
```

If tables are empty, the issue is likely a column name mismatch in `snake_cols` vs `schema.sql` column definitions. Check:
- `title_akas_type`: `snake_cols = ["title_id", "ordering", "type"]`
- `title_akas_attribute`: `snake_cols = ["title_id", "ordering", "attr"]`
- `title_principal_char`: `snake_cols = ["tconst", "ordering", "character_name"]`

Verify these match the column names in `silver/schema.sql`.

### T1.6 Move Gold FK Check Before Gold Export

**Assessment ref:** A7 (P1)
**File:** `silver/fk_checks.py:73-81`

**Current:** Runs `SELECT COUNT(*) FROM gold.fact_performance LEFT JOIN gold.dim_person` — too late, or already propagated to Gold.

**Fix:** Change FK check to run against Silver layer before dbt builds Gold:

```python
# fk_checks.py — replace Gold FK with Silver FK
{
    "name": "fact_performance_nconst_exists_in_name_basics",
    "sql": """
        SELECT COUNT(*) AS orphan_count
        FROM silver.title_principal p
        LEFT JOIN silver.name_basics n ON p.nconst = n.nconst AND n.is_current = TRUE
        WHERE n.nconst IS NULL
    """,
    "threshold": 0,
},
```

This catches the 7,649 orphan nconst before they reach Gold.

### T1.7 Generate `_MANIFEST.json`

**Assessment ref:** A8 (P1)
**File:** `orchestration/operators/gold_export_operator.py`

**Action:** Re-run Gold export operator after dbt test passes. If operator is not easily re-runnable, create a one-shot script:

```python
# scripts/generate_manifest.py
import os, json, hashlib
MART_DIR = "/opt/airflow/output/gold/"
entries = []
for f in os.listdir(MART_DIR):
    if f.endswith(".parquet"):
        path = os.path.join(MART_DIR, f)
        stat = os.stat(path)
        entries.append({
            "file": f,
            "size_bytes": stat.st_size,
            "mtime": stat.st_mtime,
        })
manifest = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "file_count": len(entries),
    "files": entries,
}
with open(os.path.join(MART_DIR, "_MANIFEST.json"), "w") as f:
    json.dump(manifest, f, indent=2)
```

### T1.8 Fix DQ Composite PK SQL

**Assessment ref:** A13 (P2)
**File:** `dq/config.yaml`

**Current:** `count(DISTINCT tconst, ordering)` — binder error, `tconst` renamed to `title_key`
**Fix:** Change to `count(DISTINCT title_key, ordering)` to match Gold schema column names.

---

## Tier 2 — Performance & Quality (1-2 days)

### T2.1 Increase dbt Threads

**Assessment ref:** A12
**File:** `gold/profiles.yml`

```yaml
outputs:
  prod:
    type: postgres
    threads: 4  # was 2
```

**Rationale:** AMD 200GE has 4 logical threads. PostgreSQL can handle 4 concurrent connections. dbt's DAG ensures models with dependencies don't run concurrently, so peak concurrency is limited to independent models (staging models run in parallel, intermediate models depend on staging).

**Risk:** If PostgreSQL shared_buffers is too low (256 MB), 4 concurrent threads could cause index scan contention. Mitigate by increasing `shared_buffers` to `512 MB` in docker-compose.yml postgres command args.

### T2.2 Make Intermediate Models Ephemeral

**Assessment ref:** A11
**File:** `gold/dbt_project.yml`

```yaml
models:
  imdb_gold:
    intermediate:
      +materialized: ephemeral  # was: table
```

**Rationale:** `int_title_details` is referenced only by `dim_title`. `int_person_details` is referenced only by `dim_person`. Making them ephemeral inlines the SQL into the mart query, eliminating intermediate table writes. This saves ~15-20% of Gold build time.

### T2.3 Eliminate CSV Intermediates via DuckDB postgres_scanner

**Assessment ref:** A9
**File:** `silver_operator.py`

**Current path:** DuckDB → CSV file → psycopg2 COPY → PostgreSQL
**Target path:** DuckDB → PostgreSQL directly via `postgres_scanner`

```python
# Install and load extension
conn.install_extension("postgres_scanner")
conn.load_extension("postgres_scanner")

# Attach PostgreSQL
conn.execute(f"""
    ATTACH 'postgresql://elyssa:{password}@postgres:5432/elyssa_warehouse' AS pg (TYPE postgres)
""")

# Direct COPY — no CSV
conn.execute(f"""
    CREATE TABLE pg.silver.title_genre AS
    SELECT tconst, UNNEST(string_split(NULLIF(genres, '\\N'), ',')) AS genre
    FROM read_parquet('{parquet_path}')
    WHERE genres IS NOT NULL AND genres != '' AND genres != '\\N'
""")
```

**Est. impact:** Eliminates ~1h of Silver CSV I/O. DuckDB writes directly to PostgreSQL via the postgres wire protocol, which is faster than CSV export + psycopg2 import.

**Risk:** `postgres_scanner` is an extension that must be installed. DuckDB 1.2 ships it as a core extension. If unavailable, fall back to streaming via `conn.fetchmany()` with `executemany()`.

### T2.4 Add Composite FK Indexes

**File:** `silver/migrations/001_initial_schema.sql` or post-Gold DDL

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_performance_title_name
  ON gold.fact_performance(title_key, name_key);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_episode_key
  ON gold.fact_episode(episode_key);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dim_title_start_year
  ON gold.dim_title(start_year);
```

**Est. impact:** Reduces join probe time for analytics queries and DS feature engineering.

---

## Tier 3 — Architectural (3-5 days, highest payoff)

### T3.1 Implement Incremental Watermark

**Assessment ref:** A10
**Files:** `bronze/watermark.py`, `imdb_pipeline_dag.py`

**Current:** `bronze/watermark.py` exists with `save_watermark()` / `load_watermark()` but is never called.

**Implementation:**

```python
# In bronze_operator.py execute() — when using checkpoint resume:
if os.path.exists(output_path):
    existing_count = conn.execute(...).fetchone()[0]
    # NEW: check watermark freshness
    watermark = load_watermark()
    if watermark and watermark.get(table) == file_checksum:
        self.log.info(f"  {table}: SKIP (watermark matches, no new data)")
        continue
```

```python
# In imdb_pipeline_dag.py — add watermark tracking
def _save_pipeline_watermark(**context):
    from bronze.watermark import save_watermark
    save_watermark({"last_run": datetime.now(timezone.utc).isoformat()})
```

**Est. impact on incremental runs:** 5.5h → ~45min (only new/changed data processed).

### T3.2 Partition Large Fact Tables

**File:** `orchestration/operators/gold_export_operator.py`

```python
# Replace flat Parquet export with Hive-partitioned write
conn.execute("""
    COPY (
        SELECT fp.*, dt.title_type
        FROM gold.fact_performance fp
        JOIN gold.dim_title dt ON fp.tconst = dt.tconst
    ) TO 'marts/full/fact_performance'
    (FORMAT PARQUET, PARTITION_BY (title_type), COMPRESSION SNAPPY)
""")
```

**Est. impact:** Partition pruning reduces scan by 40-60% for type-filtered queries. Particularly beneficial for DS genre model training (filters by movie types).

### T3.3 DuckDB-Native Silver (Remove PostgreSQL Detour)

**File:** New `build_silver_gold.py` script

**Current architecture:** TSV → DuckDB(Parquet) → CSV → psycopg2(PostgreSQL) → dbt(PostgreSQL) → DuckDB(export)

**Proposed:** TSV → DuckDB(Bronze Parquet) → DuckDB(Silver transformations + Gold star-schema) → Gold Parquet

```python
# build_silver_gold.py — pure DuckDB pipeline
import duckdb
conn = duckdb.connect("/tmp/etl.duckdb")
conn.execute("SET memory_limit = '8GB'")
conn.execute("SET threads = 2")

# Read Bronze → Silver transforms (all DuckDB SQL)
conn.execute("""
    CREATE TABLE silver.title_basics AS
    SELECT tconst, titleType, primaryTitle, ...
    FROM read_parquet('/opt/airflow/output/bronze/title.basics.parquet')
""")

# Build Gold star-schema directly
conn.execute("""
    CREATE TABLE gold.dim_title AS
    SELECT tconst, title_type, primary_title, ..., genre_list
    FROM silver.title_basics
""")

# Export to Parquet
conn.execute("""
    COPY gold.dim_title TO '/opt/airflow/output/gold/dim_title.parquet'
    (FORMAT PARQUET, COMPRESSION SNAPPY)
""")
```

**Est. impact:** Eliminates 3.5h Silver (PostgreSQL detour) + 63m Gold dbt + 15m export → total drops from 5.5h to ~1.5h.

**Risk:** SCD2 merge in DuckDB requires careful `UPDATE` + `INSERT` logic (no native `MERGE`). PostgreSQL's SCD2 logic would need to be ported.

---

## Implementation Sequence

```
Week 1 — Tier 1 (Safety & Correctness)
├── T1.1: Wire etl-runner container into DAG
├── T1.2: Fix silver DuckDB memory_limit
├── T1.3: Fix Gold PK grains (schema.yml × 2)
├── T1.4: Remove dead PySpark code (3 files)
├── T1.5: Verify & fix child table population
├── T1.6: Move FK check to Silver layer
├── T1.7: Generate _MANIFEST.json
└── T1.8: Fix DQ composite PK SQL

Week 2 — Tier 2 (Performance & Quality)
├── T2.1: Increase dbt threads to 4
├── T2.2: Make intermediate models ephemeral
├── T2.3: Eliminate CSV via postgres_scanner
├── T2.4: Add composite FK indexes
└── Benchmark: profile runtime vs baseline

Week 3 — Tier 3 (Architectural)
├── T3.1: Implement incremental watermark
├── T3.2: Partition large fact tables
├── T3.3: DuckDB-native Silver+Gold (optional)
└── End-to-end benchmark vs baseline
```

---

## Expected Cumulative Impact

| Metric | Baseline | After T1 | After T2 | After T3 |
|--------|----------|----------|----------|----------|
| Silver stability | OOM on UNNEST | Stable | Stable | Stable |
| Bronze ingestion | 47 min | 47 min | 47 min | 47 min |
| Silver ETL | 3h 30m | 3h 30m | ~2h 30m | ~30m |
| Gold dbt | 63 min | 63 min | ~40 min | ~15m |
| Gold export | 15 min | 15 min | 15 min | ~2m |
| **Total DE** | **~5h 30m** | **~5h 30m** | **~4h** | **~1h 30m** |
| False PK warnings | 3.9M "dupes" | 0 | 0 | 0 |
| DQ test failures | 4 (SQL errors) | 0 | 0 | 0 |
| Dead code lines | ~250 | 0 | 0 | 0 |

---

## Acceptance Criteria

1. Silver transform completes without OOM on full 210M-row run
2. All 8 child tables have >0 rows (title_akas_type, title_akas_attribute, title_principal_char populated)
3. Gold fact_performance PK has 0 duplicates at `(title_key, name_key, ordering)` grain
4. Gold fact_episode PK has 0 duplicates at `(episode_key)` grain
5. All DQ SQL tests execute without binder errors
6. `_MANIFEST.json` present in Gold export directory
7. All PySpark imports removed from silver/ modules
8. Pipeline runtime < 4 hours after Tier 2 (vs 5h30m baseline)
9. Incremental pipeline run < 1 hour after Tier 3
