# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

## Overview
Medallion architecture processing IMDb `.tsv.gz` into queryable star-schema marts.

| Layer | Engine | Output | Est. Time |
|-------|--------|--------|-----------|
| **Bronze** | DuckDB | Raw Parquet (7 tables) | ~47 min |
| **Silver** | DuckDB → psycopg2 COPY | PostgreSQL 3NF/BCNF (14 tables, SCD2) | ~3h 39m |
| **Gold** | dbt | Star-schema (6 fact/dim tables, 4.9 GB) | ~63 min |
| **Export** | DuckDB | Snappy Parquet → `marts/full/` | ~15 min |

## Critical: WSL2 Memory Constraint

**Docker Desktop on Windows runs containers inside a WSL2 VM.** The default WSL2 memory cap is **8 GB**, regardless of host RAM. Check yours:

```powershell
wsl --status  # Look for "memory limit"
```

If it says 8 GB (or less), the effective RAM for Docker is **8 GB**, not 16 GB. All memory budgets below are calculated for this constraint. To raise the cap, create `%USERPROFILE%\.wslconfig`:

```ini
[wsl2]
memory=12GB
processors=4
```

## Architecture Changes (Tier-3 Memory Optimization)

**Previous problem:** OOM crash at `silver.title_director` — DuckDB `memory_limit='4GB'` inside Airflow container with `mem_limit: 2g`.

**Applied fixes (see `docs/de_optimization_plan_tier3_memory.md`):**

| Fix | What | Why |
|-----|------|-----|
| M1 | DuckDB `memory_limit` → 1.2 GB (silver), 1.5 GB (bronze) | Prevents cgroup OOM kill — DuckDB spills to disk gracefully |
| M2 | New `etl-runner` container (6 GB budget) | DuckDB no longer competes with Airflow for memory |
| M3 | Chunked UNNEST (1M-row batches) | Bounds peak memory during array explosions (title.principals_char, etc.) |
| M4 | `etl_temp` Docker volume | Spill I/O off the container writable layer onto a dedicated volume |
| M5 | PG session tuning (`maintenance_work_mem`, `wal_level`) | Faster bulk COPY, less WAL amplification |
| M6 | Removed dead PySpark imports + pandas | Cleaner dependency tree |
| M7 | Multi-stage Docker builds | Smaller images (~800 MB vs ~1.2 GB for airflow) |
| M8 | Airflow parallelism 2, scheduler heartbeat 30s | Matches 2C/4T CPU, reduces scheduler overhead |
| M9 | `oom_score_adj` on all services | ETL runner killed last (mid-transaction), Postgres/Neo4j killed first |
| M10 | `--profile-memory` flag + `_log_memory()` hook | Build per-transformation sizing matrix |

### Auto-Cleanup Between Layers
The pipeline cleans up automatically at every stage boundary:
- **Bronze:** `CHECKPOINT` after each table flushes DuckDB temp files
- **Silver parent→child:** `CHECKPOINT` after all parent tables, CSV per table deleted after COPY
- **Silver child:** Per-chunk temp views dropped, CSV deleted after each chunk
- **Silver cleanup (finally):** All remaining temp dirs and CSVs removed
- **Duplicate temp dirs** are `shutil.rmtree()`'d even on pipeline failure

### Speed vs. Memory: The Trade-off
Lower DuckDB `memory_limit` (1.2 GB) forces more spill-to-disk, which is **slower** than a hypothetical crash-free 4 GB run. All other optimizations are orthogonal:
- **Faster:** PG session tuning, volume-backed spill (avoids Docker overlay I/O tax), chunked CSVs
- **Slower:** Lower memory limit (more disk spill), chunked UNNEST (repeated parquet scans)
- **Neutral:** Multi-stage builds, dead code removal, oom_score_adj, memory profiling

The net effect: **completes reliably instead of crashing at ~2h 23m**. Once stable, you can tune `memory_limit` upward in the `etl-runner` container (6 GB budget) for faster runs.

---

## Prerequisites
- Docker 24+ with compose plugin
- 16 GB RAM (with `mem_limit` on all containers — see service table below)
- 20 GB free disk
- Raw IMDb `.tsv.gz` files in `duke/gate0/source/` (7 files, ~1.9 GB compressed)

### Service Memory Budgets

**Effective RAM = 8 GB (WSL2 cap).** All services must fit within 8 GB, with 3 GB headroom for DuckDB peak during ETL.

| Service | `mem_limit` | `oom_score_adj` | Idle (RSS) | Peak (RSS) | Why |
|---------|-------------|-----------------|------------|------------|-----|
| postgres | 1 GB | +500 | ~300 MB | ~500 MB | 128 MB shared_buffers, no shm_size |
| neo4j | 2 GB | +500 | ~800 MB | ~800 MB | Heap 512M + pagecache 256M (not on critical path) |
| rustfs | 256 MB | +500 | ~50 MB | ~50 MB | Stateless, negligible |
| **etl-runner** | **6 GB** | **−500** | **~10 MB** | **~4 GB** | **sleeps until ETL, then DuckDB peak** |
| airflow | **1 GB** | **−250** | **~400 MB** | **~500 MB** | Webserver + scheduler (parallelism=2) |

**Idle total:** ~1.6 GB / 8 GB WSL2 — **plenty of headroom for OS + Docker engine**.  
**Peak total (during ETL):** ~5.9 GB / 8 GB WSL2 — **73%, safe**.

> **Note:** `memswap_limit` is present in docker-compose.yml for non-WSL2 hosts. On Docker Desktop + WSL2, it may be silently ignored — the `mem_limit` cgroup hard limit still prevents OOM.

---

**All commands below run from the repo root** using the DE compose file at `docker/docker-compose.yml`.
This stack runs independently from the web app compose.

```powershell
# Set convenience alias (optional)
$dc = "docker compose -f docker/docker-compose.yml"
```

### Pipeline Mode (Selective Execution)

Use `docker/pipeline-mode.ps1` to start/stop selective pipeline stages without running the full dev stack:

```powershell
# Start pipeline-only services (postgres + airflow + etl-runner)
.\docker\pipeline-mode.ps1 start

# Run a single stage (requires bronze Parquet / silver tables already present)
.\docker\pipeline-mode.ps1 run bronze     # Bronze ingestion only
.\docker\pipeline-mode.ps1 run silver     # Silver ETL only
.\docker\pipeline-mode.ps1 run gold       # Gold dbt + export only

# Full end-to-end
.\docker\pipeline-mode.ps1 run full

# Clean (drop silver/gold schemas, wipe Parquet, restart)
.\docker\pipeline-mode.ps1 clean

# Resume full dev stack (neo4j + rustfs + duckdb)
.\docker\pipeline-mode.ps1 resume

# Stop everything
.\docker\pipeline-mode.ps1 stop
```

## 1. Build & Start

```powershell
# Build all DE images
docker compose -f docker/docker-compose.yml build

# Start services in background (hard memory limits applied automatically)
docker compose -f docker/docker-compose.yml up -d

# Wait for healthy state (30-60s)
docker compose -f docker/docker-compose.yml ps --status running
```

> **Low-RAM tip:** Build one service at a time to avoid parallel build contention:
> ```powershell
> docker compose -f docker/docker-compose.yml build postgres
> docker compose -f docker/docker-compose.yml build neo4j
> docker compose -f docker/docker-compose.yml build rustfs
> docker compose -f docker/docker-compose.yml build etl-runner
> docker compose -f docker/docker-compose.yml build airflow
> ```

## 2. Sign in to Airflow UI

The admin password is pre-seeded as **`admin`** (both username and password).

```powershell
# Open Airflow UI
start http://localhost:8081
# Sign in as admin / admin
```

> **Note:** If the simple_auth_manager password file was already generated (container restart), the password remains whatever was set on first start. To reset, delete the volume: `docker compose -f docker/docker-compose.yml down -v && docker compose up -d`

## 3. Unpause & Trigger the DAG

```powershell
# Unpause the pipeline DAG (disabled by default)
docker exec elyssa-airflow airflow dags unpause imdb_pipeline_dag

# Trigger a fresh run
docker exec elyssa-airflow airflow dags trigger imdb_pipeline_dag
```

## 4. Watch Progress Layer by Layer

```powershell
# Follow all Airflow logs in real-time
docker compose -f docker/docker-compose.yml logs -f airflow
```

### Bronze Layer (~47 min)
Look for task `bronze_ingest` completing. Check output:
```powershell
# Check Bronze row counts per source
docker exec elyssa-airflow python -c "
import duckdb
con = duckdb.connect(':memory:')
for t in ['title.basics','name.basics','title.ratings','title.principals','title.episode','title.crew','title.akas']:
    path = f'/opt/airflow/data-engineering/duke/gate0/source/{t}.tsv.gz'
    cnt = con.execute(f\"SELECT count(*) FROM read_csv('{path}', delim='\\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape='')\").fetchone()[0]
    print(f'  {t}: {cnt:>12,} rows')
"

# Check quarantine
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute('SELECT table_name, count(*) FROM silver.quarantine GROUP BY table_name')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]} quarantined')
cur.execute('SELECT count(*) FROM silver.batch_metadata')
print(f'  batch_metadata records: {cur.fetchone()[0]}')
"
```

### Silver Layer (~3h 39m)

**Parents (6):** `title_basics`, `name_basics`, `title_rating`, `title_episode`, `title_principal`, `title_crew`  
**Children (8):** `title_genre`, `title_director`, `title_writer`, `name_profession`, `name_known_for_title`, `title_principal_char`, `title_akas`, `title_episode_relation`

Look for task `silver_transform` completing. Check output:
```powershell
# Silver table row counts (all 14 tables)
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
for t in ['title_basics','name_basics','title_rating','title_episode','title_principal','title_crew',
          'title_genre','title_director','title_writer','name_profession','name_known_for_title',
          'title_principal_char','title_akas','title_episode_relation']:
    cur.execute(f'SELECT count(*) FROM silver.{t}')
    print(f'  silver.{t}: {cur.fetchone()[0]:>12,} rows')
cur.execute('SELECT count(*) FROM silver.title_basics WHERE is_current = FALSE')
print(f'  title_basics historical SCD2 versions: {cur.fetchone()[0]}')
cur.execute('SELECT count(*) FROM silver.name_basics WHERE is_current = FALSE')
print(f'  name_basics historical SCD2 versions: {cur.fetchone()[0]}')
"
```

### Gold Layer (~63 min)
Look for tasks `gold_dbt_run` and `gold_dbt_test` completing. Check output:
```powershell
# Gold table row counts
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
for t in ['dim_title','dim_person','fact_title_rating','fact_title_principal','fact_performance','fact_episode']:
    cur.execute(f'SELECT count(*) FROM gold.{t}')
    print(f'  gold.{t}: {cur.fetchone()[0]:>12,} rows')
"

# dbt test results from DQ log
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute('SELECT check_name, metric_value, threshold, passed FROM silver.data_quality_log ORDER BY logged_at DESC LIMIT 15')
for r in cur.fetchall():
    print(f'  {str(r[0]):40s} val={str(r[1]):>8s} thresh={r[2]}  {\"PASS\" if r[3] else \"FAIL\"}')
"
```

### Export (~15 min)
Look for task `gold_export` completing. Check output:
```powershell
# Verify Parquet files and manifest
docker exec elyssa-airflow ls -lh /opt/airflow/output/gold/
docker exec elyssa-airflow python -c "
import json
m = json.load(open('/opt/airflow/output/gold/_MANIFEST.json'))
total_gb = sum(e['file_size_mb'] for e in m) / 1024
print(f'Export: {len(m)} files, {total_gb:.1f} GB')
for e in m:
    print(f'  {e[\"table\"]:25s} {e[\"file_size_mb\"]:>8.1f} MB  sha256={e[\"sha256\"][:16]}...')
"
```

---

## DAG Status & Troubleshooting

```powershell
# List all DAG runs
docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline_dag

# Check task status for a specific run
docker exec elyssa-airflow tasks states-for-dag-run imdb_pipeline_dag <run_id>

# Streaming logs filtered to pipeline tasks
docker compose -f docker/docker-compose.yml logs -f airflow | Select-String -Pattern "bronze_ingest|silver_transform|gold_dbt"

# Monitor container memory usage
docker stats elyssa-postgres elyssa-neo4j elyssa-rustfs elyssa-etl-runner elyssa-airflow

# Check DuckDB temp/spill usage (inside etl-runner or airflow)
docker exec elyssa-etl-runner du -sh /opt/etl/tmp/duckdb_spill/
docker exec elyssa-etl-runner du -sh /opt/etl/tmp/csv_intermediates/

# Run with memory profiling (build sizing matrix)
docker exec elyssa-airflow python /opt/airflow/data-engineering/orchestration/operators/silver_operator.py --profile-memory
```

---

## Known Issues & Fixes

### Child Table UNNEST Hang
**Symptom:** Silver parent tables load but child tables (e.g. `title_genre`, `title_director`) stay empty indefinitely. DuckDB process shows `futex_wait_queue` — kernel scheduler stall due to massive `ROW_NUMBER() OVER (PARTITION BY ...)` inside UNNEST subquery that cannot spill to disk.

**Fix applied:** All 8 child SQL templates rewritten to use `LATERAL UNNEST(...) WITH ORDINALITY` — no window functions, no intermediate sort. Chunk pagination uses simple `LIMIT/OFFSET` instead of `ROW_NUMBER() OVER ()`. DuckDB `memory_limit` is read from `DUCKDB_MEMORY_LIMIT` env var (default `2GB`).

**If it reoccurs:** Lower `DUCKDB_MEMORY_LIMIT` in `docker/docker-compose.yml` (etl-runner env) and ensure spill dir exists — DuckDB will spill to disk instead of hanging.

### dbt Lock Contention
**Symptom:** `gold_dbt_run` hangs or fails with `relation "gold.fact_episode" already exists`. Multiple concurrent dbt processes from retried DAG runs collide on same PG relations; stale `__dbt_tmp` tables accumulate; partial-parse cache serves stale metadata.

**Fix applied:** `dbt_operator.py` now acquires an exclusive file lock (`/tmp/dbt_run.lock`) before any dbt invocation; kills stale dbt PIDs before starting; cleans `__dbt_tmp` tables and partial-parse cache from PG; always uses `--full-refresh --no-partial-parse`.

**If it reoccurs:** Manually clean dbt artifacts:
```sql
DROP SCHEMA IF EXISTS gold CASCADE;
CREATE SCHEMA gold;
DELETE FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - interval '5 minutes';
```

### wait_silver Only Checks Parents
**Symptom:** `SilverDoneSensor` reports all tables ready but child tables are still empty — the sensor only polls the 6 parent tables.

**Fix applied:** `SilverDoneSensor` now polls all 14 tables (6 parents + 8 children), up to 480 attempts (4 hours), logging every 4th attempt.

---

## Outputs
- `../data-science/marts/full/*.parquet` — 6 Gold marts (~4.9 GB Snappy)
- `../data-science/marts/full/_MANIFEST.json` — Export audit trail with SHA256 checksums

## Service URLs
| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow UI | http://localhost:8081 | `admin` / auto-generated |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |

## Key Docs
- [`docs/specialized_assessment.md`](docs/specialized_assessment.md) — 56-check DE assessment
- [`docs/de_optimization_plan.md`](docs/de_optimization_plan.md) — 17-item optimization plan (Tier 1-2)
- [`docs/de_optimization_plan_tier3_memory.md`](docs/de_optimization_plan_tier3_memory.md) — Tier-3 memory optimization (10 interventions)
- [`docs/schema_dictionary.md`](docs/schema_dictionary.md) — Column-level schema + known deltas
