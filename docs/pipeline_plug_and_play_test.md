# Elyssa-IMDb Plug-and-Play Pipeline Test Guide

Sequential instructions + live log per layer for testing the once "plug-and-play" mechanism.

---

## Prerequisites: Verify Infrastructure

```powershell
# Check all services are running
docker compose -f docker/docker-compose.yml ps

# Check RustFS buckets exist (should show: imdb-source, bronze, gold-exports)
docker exec elyssa-rustfs rc bucket list local/

# Check Airflow is healthy
docker inspect --format '{{json .State.Health.Status}}' elyssa-airflow

# Check PostgreSQL is ready
docker exec elyssa-postgres pg_isready -U elyssa -d elyssa_warehouse

# Check etl-runner is alive
docker exec elyssa-etl-runner python -c "import duckdb; print('DuckDB ok')"
```

**Expected:** All 4 services `Up (healthy)`, `rc bucket list local/` shows 3 buckets, both Python envs importable.

---

## Layer 0: IMDb Data Download → RustFS S3

**Command:**
```powershell
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/download_imdb.py
```

**Expected log pattern** (7 files, ~1.2 GB total):
```
[2026-07-30T...] IMDb Download → http://rustfs:9000/imdb-source/
[2026-07-30T...] Downloading https://datasets.imdbws.com/title.basics.tsv.gz
[2026-07-30T...]   title.basics.tsv.gz: 123.4 MB, sha256=abc123..., 30.5s (4.0 MB/s)
...
[2026-07-30T...] Download complete: 7 files, 1.15 GB, 180.0s total, 0 failures
```

**Verify:**
```powershell
# List files in RustFS imdb-source bucket
docker exec elyssa-rustfs rc object list local/imdb-source
# Should show 8 files (7 .tsv.gz + download_metadata.json)

# Check metadata
docker exec elyssa-rustfs sh -c "rc cat local/imdb-source/download_metadata.json"
```

**Plug-and-play check:** Files now live in `s3://imdb-source/`. The `imdb_data_sensor` polls this bucket every 300s and detects them via DuckDB httpfs `read_csv('s3://imdb-source/*.tsv.gz')`.

---

## Trigger Phase: Start Pipeline Execution

After data is in S3, the pipeline must be kickstarted. Choose **one** path:

### Path A — Airflow DAG (Automated Sensor + Orchestration)

```powershell
# 1. Unpause the DAG (one-time; persists across restarts)
docker exec elyssa-airflow airflow dags unpause imdb_pipeline

# 2. Trigger a DAG run
docker exec elyssa-airflow airflow dags trigger -r manual_$(Get-Date -Format 'yyyyMMddHHmmss') imdb_pipeline

# 3. Monitor the sensor phase (polls S3 every 300s, timeout 3600s)
docker compose -f docker/docker-compose.yml logs -f airflow --tail 50
```

**Expected sensor log** (once files are detected):
```
[YYYY-MM-DDTHH:MM:SS] {imdb_sensor.py:XX} INFO - IMDb source files detected:
  title.basics.tsv.gz (123.4 MB)
  title.akas.tsv.gz (456.7 MB)
  ...
[YYYY-MM-DDTHH:MM:SS] {imdb_sensor.py:XX} INFO - All 7 source files present — sensor passed
```

### Path B — Direct Bronze Execution (Bypasses Airflow)

Skips the sensor entirely; runs bronze ingestion directly:

```powershell
# Confirm files exist first
docker exec elyssa-rustfs rc object list local/imdb-source

# Run bronze directly (no sensor needed)
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/run_bronze.py
```

### Path C — Using pipeline-mode.ps1 (Recommended for Manual Testing)

```powershell
.\docker\pipeline-mode.ps1 run bronze
```

This triggers the DAG via Airflow CLI and prints the tail command for live monitoring.

---

## Layer 1: Bronze Ingestion → S3 + Bind Mount

**Live log command (in separate terminal):**
```powershell
# Bronze subprocess log — lives on the shared etl_temp volume
# (survives container restarts, tailable from either container)
docker exec elyssa-airflow tail -f /opt/airflow/output/tmp/bronze_runner.log
docker exec elyssa-etl-runner tail -f /opt/etl/tmp/bronze_runner.log   # same file
```

**Direct execution (bypasses Airflow):**
```powershell
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/run_bronze.py
```

**Expected log pattern** (~18 min for 7 tables, 211.9M rows on the full 2026-07-31 dump):
```
[2026-07-30T...] === Bronze Ingestion Starting (S3-Centric) ===
[2026-07-30T...]   title.basics written -> s3://bronze/title.basics.parquet
[2026-07-30T...]   title.basics written -> /opt/airflow/output/bronze/title.basics.parquet
[2026-07-30T...]   title.basics: 12678890 rows (sha256=abc...)
[2026-07-30T...]   title.akas: 58686380 rows (sha256=def...)
...
[2026-07-30T...] === Bronze complete: 211949844 rows across 7 tables in 1092.3s ===
```
> Note: `title.basics` has 12.7M rows and `title.akas` 58.7M — IMDb TSV fields contain
> literal `"` characters (e.g. `"Rome brûle" (Portrait de Shirley Clarke)`), so bronze
> reads with `quote='' escape=''`. Any other config silently drops those rows.

Or if checkpoint resume triggers (row counts verified against the marker — mismatch forces re-ingest):
```
[2026-07-30T...]   CHECKPOINT title.basics: 12678890 rows already processed (marker + S3 verified)
[2026-07-30T...]   CHECKPOINT title.basics: row-count mismatch — S3=2228464 local=2228464 vs marker=12678890 — re-ingesting
```

**Verify S3 (pipeline hot path):**
```powershell
# List S3 bronze bucket
docker exec elyssa-rustfs rc object list local/bronze
# Should show 7 .parquet files
```

**Verify bind mount (DS notebook path):**
```powershell
docker exec elyssa-airflow ls -lh /opt/airflow/output/bronze/*.parquet
```

**Verify DuckDB can read from S3 Bronze:**
```powershell
docker exec elyssa-airflow python -c "
import duckdb
conn = duckdb.connect(':memory:')
from bronze.s3_config import configure_s3
configure_s3(conn)
r = conn.execute(\"SELECT count(*) FROM read_parquet('s3://bronze/title.basics.parquet')\").fetchone()[0]
print(f'title.basics: {r:,} rows')
r2 = conn.execute(\"SELECT count(*) FROM read_parquet('s3://bronze/name.basics.parquet')\").fetchone()[0]
print(f'name.basics: {r2:,} rows')
"
```

**Check status markers:**
```powershell
docker exec elyssa-airflow sh -c "cat /opt/airflow/output/bronze/.completed"
docker exec elyssa-airflow sh -c "cat /opt/airflow/output/bronze/.batch_metadata.json"
```

**Checkpoint behavior:** Bronze now writes per-table marker files (e.g., `.title.akas.completed`) containing `{"rows", "checksum", "batch_id"}`. On resume, it skips tables with valid markers instead of scanning full Parquet files.

**Plug-and-play check:** Bronze writes to both S3 (for Silver pipeline hot path) and local bind mount (for DS notebooks). Silver operator defaults to `bronze_path="s3://bronze/"`.

---

## Layer 2: Silver ETL → PostgreSQL

> **Concurrency note:** Silver ETL uses a file-based exclusive lock (`silver.lock`) to prevent concurrent runs from stepping on each other during `TRUNCATE CASCADE`. The lock auto-releases if the process crashes. If two runs collide, the second fails fast with `RuntimeError`. No PostgreSQL advisory lock is used — a blocked run would hide live progress for hours; fail-fast is the intended UX.
>
> **Failure detection:** on any exception the subprocess writes `.silver.failed` (next to `silver.lock`). `wait_silver` detects it within one poll cycle (30s) and fails the DAG immediately instead of polling for hours.

**Live progress (recommended — this is where the real ETL output goes):**
```powershell
# Silver runs as a detached subprocess inside etl-runner.
# stdout/stderr are streamed live to the shared etl_temp volume:
docker exec elyssa-etl-runner tail -f /opt/etl/tmp/silver_etl.log
# (same file visible from airflow at /opt/airflow/output/tmp/silver_etl.log)
```

**DAG/task state via Airflow 3.X CLI:**
```powershell
# List DAG runs (newest first) to get the run_id
docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline -o table

# Show per-task state for a run (e.g. manual__2026-07-30T09:09:49.088628+00:00)
docker exec elyssa-airflow airflow tasks states-for-dag-run imdb_pipeline <run_id> -o table

# Tail a task's Airflow log (spawn + sensor messages only;
# ETL progress lives in /opt/etl/tmp/silver_etl.log above)
# Airflow 3.3 removed `airflow tasks logs` — use the UI log viewer or the
# shared-volume subprocess logs (paths below)
docker exec elyssa-airflow airflow tasks state imdb_pipeline wait_silver <run_id>
```

**Direct execution (only when no Airflow run is active — file lock fails fast otherwise):**
```powershell
docker exec elyssa-etl-runner python /opt/etl/data-engineering/orchestration/operators/silver_operator.py 2>&1 | Tee-Object -FilePath docs/silver_live.log
```

**Check lock / failure markers:**
```powershell
# Lock holder PID (file exists only while a run is active)
docker exec elyssa-etl-runner sh -c "cat /opt/etl/tmp/silver.lock 2>/dev/null || echo 'no lock — no Silver run active'"

# Failure marker (written on crash; cleared on next run start)
docker exec elyssa-etl-runner sh -c "cat /opt/etl/tmp/.silver.failed 2>/dev/null || echo 'no failure marker'"
```

**Expected log pattern** (`[1/6]` parent tables, then `[1/8]` child normalization tables).
Counts reflect the full 2026-07-31 dump (title.basics 12.7M, akas 58.7M, principals
100.9M — see Bronze layer; the 2 episode orphan rows and 84 name.basics rows with NULL
primaryName are filtered):
```
{"timestamp": "...", "level": "INFO", "stage": "silver_transform", "status": "started", "message": "Processing parent tables + 8 child normalization tables"}
Schema applied from /opt/etl/data-engineering/silver/schema.sql
Truncated Silver child tables to clear partial/corrupted state
  [1/6] Starting title.basics -> silver.title_basics...
  title.basics: 12678890 rows -> silver.title_basics
  silver.title_basics: 2228464 expired, 12678890 inserted (SCD2)
  silver.title_basics: 12678890 rows loaded
  [2/6] Starting title.akas -> silver.title_akas...
  title.akas: 58686380 rows -> silver.title_akas
  ...
[CHECKPOINT] parents_done saved (batch=20260730_..., rows=199754772)
  [1/8] Starting silver.title_genre...
  ...
[CHECKPOINT] children_done saved (batch=20260730_..., parent_rows=199754772, child_rows=...)
"status": "complete", "message": "199754772 parent + ... child rows"
```

**Key behavior changes from previous version:**
- No DuckDB temp tables are materialized for parent tables — `COPY` reads directly from `read_parquet()`
- For child tables, a source temp table is materialized **only** when chunked processing is required (>5M rows); otherwise streams directly
- `max_temp_directory_size` is capped at `1.25GB` to respect the Airflow container memory limit
- Checkpoint resume verifies marker + S3/local Parquet **row counts** (not just object existence) — any mismatch forces a re-ingest

**Verify PostgreSQL tables:**
```powershell
# Row counts for all 14 silver tables
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "
SELECT schemaname, tablename, n_live_tup AS row_estimate
FROM pg_stat_user_tables
WHERE schemaname = 'silver'
ORDER BY tablename;"

# Check for stale gold tables from prior runs
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "\dt gold.*"
```

**Check checkpoint table:**
```powershell
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "
SELECT stage, batch_id, completed_at FROM silver.pipeline_checkpoints WHERE pipeline_name = 'silver';"
```

**Plug-and-play check:** If Silver was already loaded (checkpoint exists), re-running should print:
```
[CHECKPOINT] Parents already completed (batch=..., at=...), skipping parents
[CHECKPOINT] Children already completed (batch=..., at=...), skipping all Silver ETL
```

---

## Layer 3: Gold dbt + Export → Parquet + Manifest

### Step 3a — dbt Run (build gold views/tables)

```powershell
docker exec elyssa-airflow dbt run --project-dir /opt/airflow/data-engineering/gold --profiles-dir /opt/airflow/data-engineering/gold --target prod --full-refresh --no-partial-parse
```

**Expected log pattern:**
```
00:00:00  Running dbt...
00:00:00  Found X models, Y tests, ...
00:00:05  1 of 6 START view gold.stg_title_basics ...
00:00:10  2 of 6 START view gold.stg_title_ratings ...
...
00:02:00  5 of 6 START table gold.fact_title_rating ...
00:02:30  6 of 6 START table gold.episodic_content ...
00:02:30  Finished running X views, Y tables, Z ephemeral
```

### Step 3b — dbt Test

```powershell
docker exec elyssa-airflow dbt test --project-dir /opt/airflow/data-engineering/gold --profiles-dir /opt/airflow/data-engineering/gold --target prod --no-partial-parse
```

**Expected log pattern:**
```
00:00:00  Running dbt...
00:00:05  1 of X PASS gold_unique_dim_title_title_id ...
00:00:10  2 of X PASS gold_not_null_dim_title_title_id ...
...
00:01:00  Finished running X tests (all PASS)
```

### Verify gold schema

```powershell
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "\dt gold.*"
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "
SELECT table_name, n_live_tup FROM pg_stat_user_tables WHERE schemaname = 'gold' ORDER BY table_name;"
```

### Step 3c — Gold Export (Parquet + manifest)

```powershell
docker exec elyssa-airflow python -c "
import os; os.environ['GOLD_EXPORT_PG_PASSWORD'] = 'elyssa_pg_2026'
from operators.gold_export_operator import GoldExportOperator
GoldExportOperator(task_id='gold_export').execute({})
"
```

**Expected log pattern:**
```
Exported dim_person: ... rows -> /opt/airflow/output/gold/dim_person.parquet
Exported dim_title: ... rows -> /opt/airflow/output/gold/dim_title.parquet
...
Manifest written: /opt/airflow/output/gold/_MANIFEST.json
Tar archive created: /tmp/gold_marts.tar.gz (... MB)
[CHECKPOINT] gold export_done saved (..., total rows)
```

### Final verification

```powershell
# Check gold parquet files
docker exec elyssa-airflow ls -lh /opt/airflow/output/gold/*.parquet

# Read manifest
docker exec elyssa-airflow python -c "import json; m=json.load(open('/opt/airflow/output/gold/_MANIFEST.json')); print(json.dumps(m, indent=2))"

# Check bind mount (DS consumption path)
ls -lh data-science/marts/gold/*.parquet

# Count rows in exported parquets via DuckDB
docker exec elyssa-airflow python -c "
import duckdb
conn = duckdb.connect(':memory:')
for t in ['dim_person','dim_title','fact_episode','fact_performance','fact_title_principal','fact_title_rating']:
    r = conn.execute(f\"SELECT count(*) FROM read_parquet('/opt/airflow/output/gold/{t}.parquet')\").fetchone()[0]
    print(f'{t}: {r:,} rows')
"
```

---

## Layer-by-Layer Dependency Table

| Layer | Reads From | Writes To | Downstream Consumer | Idempotent? |
|-------|-----------|-----------|--------------------|-------------|
| **Download** | IMDb HTTPS | `s3://imdb-source/` | Sensor, Bronze runner | Yes (overwrites) |
| **Trigger** | `s3://imdb-source/` (sensor poll) | DAG run ID / subprocess PID | Bronze subprocess | Yes (re-triggerable) |
| **Bronze** | `s3://imdb-source/` | `s3://bronze/` + local bind mount | Silver, DS notebooks | Yes (checkpoint resume) |
| **Silver** | `s3://bronze/` | PostgreSQL `silver.*` | Gold (dbt) | Yes (checkpoint resume + file lock serializes runs) |
| **Gold dbt** | `silver.*` | `gold.*` (PostgreSQL) | Gold Export | Yes (full-refresh) |
| **Gold Export** | `gold.*` (PostgreSQL) | `data-science/marts/gold/*.parquet` | DS Feature Eng, Web API | Yes (overwrites) |

---

## One-Shot Run (Full Pipeline, No Airflow)

```powershell
# 1. Download (if first time)
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/download_imdb.py

# 2. Bronze
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/run_bronze.py

# 3. Silver
# Uses a file-based lock (silver.lock) to prevent concurrent runs. Direct execution
# will fail fast if another Silver ETL is already running (no PG advisory lock).
# Capture output to docs/silver_live.log for offline inspection:
docker exec elyssa-etl-runner python /opt/etl/data-engineering/orchestration/operators/silver_operator.py 2>&1 | Tee-Object -FilePath docs/silver_live.log

# 4. Gold dbt
docker exec elyssa-airflow dbt run --project-dir /opt/airflow/data-engineering/gold --profiles-dir /opt/airflow/data-engineering/gold --target prod --full-refresh

# 5. Gold export
docker exec elyssa-airflow python -c "
import os; os.environ['GOLD_EXPORT_PG_PASSWORD'] = 'elyssa_pg_2026'
from operators.gold_export_operator import GoldExportOperator
GoldExportOperator(task_id='gold_export').execute({})
"
```

Or via `pipeline-mode.ps1`:
```powershell
.\docker\pipeline-mode.ps1 start
.\docker\pipeline-mode.ps1 run full
```

---

## Monitoring Cheat Sheet

| You Want | Command |
|----------|---------|
| DAG sensor status | `docker compose -f docker/docker-compose.yml logs --tail 20 elyssa-airflow \| grep -i "sensor\|imdb_data\|source"` |
| DAG runs (get run_id) | `docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline -o table` |
| Task states for a run | `docker exec elyssa-airflow airflow tasks states-for-dag-run imdb_pipeline <run_id> -o table` |
| Task state | `docker exec elyssa-airflow airflow tasks state imdb_pipeline <task_id> <run_id>` |
| Task log (Airflow 3.3 has no `airflow tasks logs` — use UI) | open http://localhost:18081 → Runs → log |
| RustFS S3 files | `docker exec elyssa-rustfs rc object list local/<bucket>` |
| Bronze live log | `docker exec elyssa-airflow tail -f /opt/airflow/output/tmp/bronze_runner.log` |
| Bronze completion | `docker exec elyssa-airflow sh -c "cat /opt/airflow/output/bronze/.completed"` |
| Silver live log | `docker exec elyssa-etl-runner tail -f /opt/etl/tmp/silver_etl.log` |
| Silver lock holder | `docker exec elyssa-etl-runner sh -c "cat /opt/etl/tmp/silver.lock 2>/dev/null \|\| echo 'no lock'"` |
| Silver failure marker | `docker exec elyssa-etl-runner sh -c "cat /opt/etl/tmp/.silver.failed 2>/dev/null \|\| echo 'no failure'"` |
| Silver table rows | `docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "SELECT tablename, n_live_tup FROM pg_stat_user_tables WHERE schemaname='silver' ORDER BY tablename;"` |
| Gold dbt live | stdout from `dbt run` / `dbt test` commands |
| Gold export manifest | `docker exec elyssa-airflow python -c "import json; m=json.load(open('/opt/airflow/output/gold/_MANIFEST.json')); print(json.dumps(m,indent=2))"` |
| Pipeline checkpoints | `docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "SELECT * FROM silver.pipeline_checkpoints ORDER BY stage;"` |
| Memory usage | `docker stats --no-stream` |
| Clean slate (start over) | `.\docker\pipeline-mode.ps1 clean` then `docker compose -f docker/docker-compose.yml restart` |
