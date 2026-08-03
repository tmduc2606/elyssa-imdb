<div align="center">

# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](docs/SMOKE_TEST.md)
[![DuckDB](https://img.shields.io/badge/DuckDB-Analytics-orange.svg)](data-engineering/README.md)
[![Airflow](https://img.shields.io/badge/Airflow-Orchestration-orange.svg)](data-engineering/README.md)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue.svg)](data-engineering/README.md)

</div>

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Tier-3 Memory Optimization](#tier-3-memory-optimization)
- [Auto-Cleanup Between Layers](#auto-cleanup-between-layers)
- [Speed vs. Memory](#speed-vs-memory)
- [Prerequisites](#prerequisites)
- [Service Memory Budgets](#service-memory-budgets)
- [Quick Start](#quick-start)
- [Layer Progress](#layer-progress)
- [DAG Status & Troubleshooting](#dag-status--troubleshooting)
- [Known Issues & Fixes](#known-issues--fixes)
- [Outputs](#outputs)
- [Service URLs](#service-urls)
- [Key Docs](#key-docs)

## Overview

Medallion architecture processing IMDb `.tsv.gz` into queryable star-schema marts.

| Layer | Engine | I/O | Output | Measured (final run) |
|-------|--------|-----|--------|----------------------|
| **Bronze** | DuckDB + httpfs | S3 (imdb-source/) → S3 (bronze/) + bind mount | Raw Parquet (7 tables, 212 M rows) | **19.5 m** |
| **Silver** | DuckDB + httpfs → psycopg2 COPY | S3 (bronze/) → PostgreSQL | PostgreSQL 3NF/BCNF (14 tables + 3 governance, SCD2) | **~5 h 04 m** (ETL) + **~41 m** (export) |
| **Gold** | dbt (threads=2) | PostgreSQL → PostgreSQL | Star-schema (12 models: 2 incremental, 5 table, 5 view; 43 tests) | **~1 h 55 m** (run) + **18–70 m** (test) |
| **Export** | DuckDB | PostgreSQL → bind mount `marts/` | Snappy Parquet (6 tables ≈ 5.5 GB) + `_MANIFEST.json` | **~31 m** |

> Measured on run `manual_20260731160437` (2026-07-31 → 08-01). That run doubled as the recovery
> vehicle for hotfixes, so its retry-heavy wall-clock (~23 h including sensor waits and overnight gap)
> is **not** representative — active compute totals ~9 h. A clean run on today's code is materially
> faster. Full post-mortem: [`docs/final_pipeline_summary.md`](docs/final_pipeline_summary.md).

All layers read/write through **RustFS** (S3-compatible, localhost), with bind mounts for DS notebook consumption.

## Architecture

```
IMDb .tsv.gz → Bronze (DuckDB) → Silver (PostgreSQL) → Gold (dbt) → Export (Parquet)
                                     ↑                                    ↑
                             Airflow DAG orchestrates all stages        marts/gold/
```

```
Phase 1 ran 27 hotfixes since the `rustfs_integration_plan.md` baseline (commit `8383467` → HEAD
`02ad9ed`) to reach a stable end-to-end success. Headline changes:

| Area | Final state |
|------|-------------|
| Long-running tasks | **Detached-subprocess pattern** (`b4453bd`) — heavy tasks (silver_export, gold_dbt_run/test, gold_export) run in child processes with file-based completion markers; Airflow tasks are lightweight spawner/sensor pairs. Fixes the Airflow 3.3 300 s orphan-pass kill loop (previously `wait_silver` needed 62 attempts). |
| Silver locking | File-based lock (`silver.lock`) replaces the advisory lock (`1053182`); orphan `title_episode` rows with NULL `parentTconst` filtered (`2ac02d3`). |
| PostgreSQL shm | `shm_size: 1g` + sysv hardening — fixes DSM ENOSPC in `agg_actor_cooccurrence` (`a8779df`). |
| Gold grain | `agg_actor_cooccurrence` deduplicated (154.7 M → 140.75 M distinct pairs), schema `gold` (not `gold_gold`), 4 grain tests added (`f131a3c`). |
| Indexes | 7 composite indexes on `gold.fact_*` (9.7 GB, all valid); `VACUUM (ANALYZE)` of `fact_performance` enables index-only scans (`02ad9ed`). |
| Bronze | Quote-safe COPY (temp table, no `quote=''`), checkpoint row-count verification; preserves rows with literal quotes (`5886981`, `9f431a8`, `c20ef7e`). |
| dbt | Exclusive file lock (`/tmp/dbt_run.lock`), stale PID kill, `--full-refresh --no-partial-parse`, threads=2. |

The old PySpark design was superseded by the DuckDB stack during optimization (see `docs/final_pipeline_summary.md` §5 for the full hotfix log).

---

## Tier-3 Memory Optimization

**Previous problem:** OOM crash at `silver.title_director` — DuckDB `memory_limit='4GB'` inside Airflow container with `mem_limit: 2g`.

**Applied fixes (see `docs/de_optimization_plan_tier3_memory.md`):**

| Fix | What | Why |
|-----|------|-----|
| M1 | DuckDB `memory_limit` → 1.2 GB (silver), 1.5 GB (bronze) | Prevents cgroup OOM kill — DuckDB spills to disk gracefully |
| M2 | New `etl-runner` container (2 GB budget) | DuckDB no longer competes with Airflow for memory |
| M3 | Chunked UNNEST (1M-row batches) | Bounds peak memory during array explosions (title.principals_char, etc.) |
| M4 | `etl_temp` Docker volume | Spill I/O off the container writable layer onto a dedicated volume |
| M5 | PG session tuning (`maintenance_work_mem`, `wal_level`) | Faster bulk COPY, less WAL amplification |
| M6 | Removed dead PySpark imports + pandas | Cleaner dependency tree |
| M7 | Multi-stage Docker builds | Smaller images (~800 MB vs ~1.2 GB for airflow) |
| M8 | Airflow parallelism 1, scheduler heartbeat 30s | Matches 2C/4T CPU, reduces scheduler overhead |
| M9 | `oom_score_adj` on all services | ETL runner killed last (mid-transaction), Postgres killed first |
| M10 | `--profile-memory` flag + `_log_memory()` hook | Build per-transformation sizing matrix |

---

## Benchmarks

### DuckDB Ingestion Throughput

Verified on reference hardware (AMD Athlon 200GE, 16 GB RAM, Docker Desktop + WSL2).

| Table | Rows | Scan Time | Throughput |
|-------|------|-----------|------------|
| title.basics | 12,593,486 | 4.9 ms | 2.6M rows/s |
| title.akas | 57,934,300 | 16.2 ms | 3.6M rows/s |
| title.crew | 12,593,486 | 2.6 ms | 4.8M rows/s |
| title.episode | 9,731,563 | 2.6 ms | 3.7M rows/s |
| title.principals | 100,109,752 | 21.7 ms | 4.6M rows/s |
| title.ratings | 1,684,492 | 1.5 ms | 1.1M rows/s |
| name.basics | 15,432,611 | 3.9 ms | 4.0M rows/s |
| **Total** | **210,079,690** | **53.4 ms** | **3.9M rows/s** |

**Row count accuracy vs blueprint:** 100.00%

## Auto-Cleanup Between Layers

The pipeline cleans up automatically at every stage boundary:
- **Bronze:** `CHECKPOINT` after each table flushes DuckDB temp files
- **Silver parent→child:** `CHECKPOINT` after all parent tables, CSV per table deleted after COPY
- **Silver child:** Per-chunk temp views dropped, CSV deleted after each chunk
- **Silver cleanup (finally):** All remaining temp dirs and CSVs removed
- **Duplicate temp dirs** are `shutil.rmtree()`'d even on pipeline failure

## Speed vs. Memory: The Trade-off

Lower DuckDB `memory_limit` (1.2 GB) forces more spill-to-disk, which is **slower** than a hypothetical crash-free 4 GB run. All other optimizations are orthogonal:
- **Faster:** PG session tuning, volume-backed spill (avoids Docker overlay I/O tax), chunked CSVs
- **Slower:** Lower memory limit (more disk spill), chunked UNNEST (repeated parquet scans)
- **Neutral:** Multi-stage builds, dead code removal, oom_score_adj, memory profiling

The net effect: **completes reliably instead of crashing at ~2h 23m**. Once stable, you can tune `memory_limit` upward in the `etl-runner` container (2 GB budget) for faster runs.

---

## Prerequisites
- Docker 24+ with compose plugin
- 16 GB RAM (with `mem_limit` on all containers — see service table below)
- 20 GB free disk

### Initial Setup: Download IMDb Data to RustFS S3
```powershell
# Build and start all services
docker compose -f docker/docker-compose.yml up -d

# Download 7 .tsv.gz files directly to RustFS S3 (streaming, no local disk)
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/download_imdb.py
```

This populates `s3://imdb-source/` with the 7 IMDb source files. The pipeline DAG sensor detects them and triggers Bronze ingestion.

---

## Service Memory Budgets

> **WSL2 Memory Constraint:** Docker Desktop on Windows runs containers inside a WSL2 VM. The default WSL2 memory cap is **8 GB**, regardless of host RAM. Check yours:
> ```powershell
> wsl --status  # Look for "memory limit"
> ```
> If it says 8 GB (or less), the effective RAM for Docker is **8 GB**, not 16 GB. To raise the cap, create `%USERPROFILE%\.wslconfig`:
> ```ini
> [wsl2]
> memory=12GB
> processors=4
> ```

**Docker Compose actual values** (from `docker/docker-compose.yml`):

| Service | `mem_limit` | `oom_score_adj` | Notes |
|---------|-------------|-----------------|-------|
| postgres | **2.5 GB** | +500 | Silver/Gold warehouse; `shared_buffers=512MB`, `work_mem=64MB`, `shm_size=1g` |
| rustfs | 256 MB | — | S3 object store (negligible) |
| etl-runner | **2 GB** | −500 | DuckDB ETL engine; `DUCKDB_MEMORY_LIMIT=2GB` |
| airflow | **3 GB** | −250 | DAG orchestrator + webserver + export/spill work |

> **Note:** `memswap_limit` is present in docker-compose.yml for non-WSL2 hosts. On Docker Desktop + WSL2, it may be silently ignored — the `mem_limit` cgroup hard limit still prevents OOM.

**Idle total:** ~5.75 GB / 8 GB WSL2 — headroom for OS + Docker engine.  
**Peak total (during ETL):** ~7.75 GB / 8 GB WSL2 — tight but within budget.

---

**All commands below run from the repo root** using the DE compose file at `docker/docker-compose.yml`.
This stack runs independently from the web app compose.

```powershell
# Set convenience alias (optional)
$dc = "docker compose -f docker/docker-compose.yml"
```

## Quick Start

### Pipeline Mode (Selective Execution)

Use `docker/pipeline-mode.ps1` to start/stop selective pipeline stages without running the full dev stack:

```powershell
# Start pipeline-only services (postgres + airflow + etl-runner + rustfs)
.\docker\pipeline-mode.ps1 start

# Run a single stage (requires bronze Parquet / silver tables already present)
.\docker\pipeline-mode.ps1 run bronze     # Bronze ingestion only
.\docker\pipeline-mode.ps1 run silver     # Silver ETL only
.\docker\pipeline-mode.ps1 run gold       # Gold dbt + export only

# Full end-to-end
.\docker\pipeline-mode.ps1 run full

# Clean (drop silver/gold schemas, wipe Parquet, restart)
.\docker\pipeline-mode.ps1 clean

# Stop everything
.\docker\pipeline-mode.ps1 stop
```

### 1. Build & Start

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
> > docker compose -f docker/docker-compose.yml build postgres
> > docker compose -f docker/docker-compose.yml build rustfs
> > docker compose -f docker/docker-compose.yml build etl-runner
> > docker compose -f docker/docker-compose.yml build airflow
> > ```

### 2. Sign in to Airflow UI

The admin password is pre-seeded as **`admin`** (both username and password).

```powershell
# Open Airflow UI
start http://localhost:18081
# Sign in as admin / admin
```

> **Note:** If the simple_auth_manager password file was already generated (container restart), the password remains whatever was set on first start. To reset, delete the volume: `docker compose -f docker/docker-compose.yml down -v && docker compose -f docker/docker-compose.yml up -d`

### 3. Unpause & Trigger the DAG

```powershell
# Unpause the pipeline DAG (disabled by default)
docker exec elyssa-airflow airflow dags unpause imdb_pipeline

# Trigger a fresh run
docker exec elyssa-airflow airflow dags trigger imdb_pipeline
```

## Layer Progress

### Bronze Layer (~20 min)
Look for task `run_bronze` / `wait_bronze` completing (marker `.bronze.completed`). Check output:
```powershell
# Check Bronze row counts from S3 Parquet
docker exec elyssa-airflow python -c "
import duckdb, sys
sys.path.insert(0, '/opt/airflow/data-engineering')
from bronze.s3_config import configure_s3
con = duckdb.connect(':memory:')
configure_s3(con)
for t in ['title.basics','name.basics','title.ratings','title.principals','title.episode','title.crew','title.akas']:
    path = f's3://bronze/{t}.parquet'
    cnt = con.execute(f'SELECT count(*) FROM read_parquet(\"{path}\")').fetchone()[0]
    print(f'  bronze.{t}: {cnt:>12,} rows')
"
```

### Silver Layer (~5 h ETL + ~41 m export)
Look for task `silver_transform` / `wait_silver` completing, then `silver_export` / `wait_silver_export` (marker `.export.completed`). Check output:
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

### Gold Layer (~2 h run + ~18–70 m test)
Look for tasks `gold_dbt_run` / `wait_dbt_run` and `gold_dbt_test` / `wait_dbt_test` completing. Check output:
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
```

### Quality Gates
- `dq_checks` — 7 checks (null_rate, orphan_rate, row-count variance) + Great Expectations Bronze suite (~3 min, all PASS).
- `freshness_check` — silver tables within 24 h SLA (~1 min, 5/5 PASS).

### Export (~31 min)
Look for task `gold_export` / `wait_gold_export` completing. Check output:
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
docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline

# Check task status for a specific run
docker exec elyssa-airflow tasks states-for-dag-run imdb_pipeline <run_id>

# Streaming logs filtered to pipeline tasks
docker compose -f docker/docker-compose.yml logs -f airflow | Select-String -Pattern "run_bronze|silver_transform|gold_dbt"

# Monitor container memory usage
docker stats elyssa-postgres elyssa-rustfs elyssa-etl-runner elyssa-airflow

# Check DuckDB temp/spill usage (inside etl-runner)
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

### Freshness ERROR on `silver.title_director`

**Symptom:** `failed to patch ingested_at: current tr...` (table lacks the column; `freshness.py` auto-ALTER hits a constraint error). SLA still met.

**Recommended Phase 2 fix:** add `ingested_at` to the silver child-table schema.

### Airflow 3.3 Deprecation Warnings

**Symptom:** `EmptyOperator`/`PythonOperator` → `airflow.providers.standard.*`, `BaseSensorOperator` → `airflow.sdk.bases.sensor`. Cosmetic.

**Fix applied:** None yet — cosmetic only. Plan migration in Phase 2.

### Redundant `gold_marts.tar.gz` (4.0 GB in container `/tmp`)

**Symptom:** The gold parquet dir is already bind-mounted to the host (`data-science/marts/gold/`); the tar added ~13.6 min with no host benefit.

**Fix applied (Phase 2, P0-2):** tar creation removed; manifest counts now read from parquet footers via `pyarrow.parquet.read_metadata`.

### dbt Test Runtime

**Symptom:** The 4 cooccurrence tests bring the suite to 43 tests; the uniqueness test alone ≈ 53 min, so a scheduled `gold_dbt_test` runs ~70 m.

**Fix applied (Phase 2, P1-5):** non-contractual `fact_performance`/`agg_actor_cooccurrence` tests set to `severity: warn`; `agg_actor_cooccurrence` build serialized (`SET max_parallel_workers_per_gather = 0`).

### Historical Fixes (Phase 1, for context)

- **300 s orphan-pass kill loop** — every long-running Airflow task killed at ~5 min. Fixed by the detached-subprocess pattern (`b4453bd`); do not revert to inline execution.
- **`title_crew` export failure** — `Catalog Error: Table with name title_crew does not exist!` (silver exports crew-derived tables; export list is 14 tables, not 15).
- **PostgreSQL shared-memory ENOSPC** — `could not resize shared memory segment ... No space left on device` in `agg_actor_cooccurrence`. Fixed by `shm_size: 1g` + sysv hardening (`a8779df`).
- **dbt lock contention** — concurrent dbt processes collide on PG relations. Fixed by exclusive file lock + stale PID kill + `--full-refresh --no-partial-parse`. If it reoccurs:
  ```sql
  DROP SCHEMA IF EXISTS gold CASCADE;
  CREATE SCHEMA gold;
  DELETE FROM pg_stat_activity WHERE state = 'idle in transaction' AND state_change < now() - interval '5 minutes';
  ```

---

## Outputs
- `../data-science/marts/bronze/` — 7 raw Parquet + `.bronze.completed` marker
- `../data-science/marts/silver/` — 14 Parquet + manifest
- `../data-science/marts/gold/` — 6 Gold marts (≈5.5 GB Snappy: dim_person 594 MB, dim_title 719 MB, fact_episode 133 MB, fact_performance 2.18 GB, fact_title_principal 1.89 GB, fact_title_rating 16 MB)
- `../data-science/marts/gold/_MANIFEST.json` — Export audit trail with SHA256 checksums (batch `20260801_080318`)
- `../data-science/marts/gold/.export.completed` — gold_export completion marker

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow UI | http://localhost:18081 | `admin` / `admin` |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| RustFS S3 API | http://localhost:9100 | `elyssa` / `elyssa_s3_2026` |
| RustFS Console | http://localhost:9101 | — |

## Key Docs

- [`docs/final_pipeline_summary.md`](docs/final_pipeline_summary.md) — **final Phase 1 deliverable**: run post-mortem, layer timings, hotfix log (27 commits), cleanup record
- [`docs/de_optimization_plan_tier3_memory.md`](docs/de_optimization_plan_tier3_memory.md) — Tier-3 memory optimization (M1–M10)
- [`docs/rustfs_integration_plan.md`](docs/rustfs_integration_plan.md) — RustFS/S3 baseline plan
- [`docs/schema_dictionary.md`](docs/schema_dictionary.md) — Column-level schema + known deltas
- [`docs/architecture_overview.md`](docs/architecture_overview.md) — Medallion architecture
- [`docs/export_guide.md`](docs/export_guide.md) — Parquet export + manifest format
- [`docs/phase1_summary.md`](docs/phase1_summary.md) — Phase 1 milestone summary
- [`docs/DOCKER_CONFIG_SUMMARY.md`](docs/DOCKER_CONFIG_SUMMARY.md) — Compose configuration reference
- [`docs/disaster_recovery.md`](docs/disaster_recovery.md) — Restore / recovery procedures
