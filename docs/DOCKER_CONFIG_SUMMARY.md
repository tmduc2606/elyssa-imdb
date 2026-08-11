# Docker Configuration & Pipeline Attempts Log

## Service Topology (docker-compose.yml)

| Service | Container | Image | Ports (Host→Int) | RAM | Purpose |
|---------|-----------|-------|-------------------|-----|---------|
| postgres | elyssa-postgres | elyssa-postgres:latest | 54321→5432 | 512MB sb + 2G shm | Silver/Gold warehouse (TimescaleDB) |
| neo4j | elyssa-neo4j | elyssa-neo4j:latest | 7475→7474 HTTP, 7688→7687 Bolt | 2G heap + 4G pagecache | Graph DB for title/person relationships |
| rustfs | elyssa-rustfs | elyssa-rustfs:latest | 9100→9000 S3, 9101→9001 Console | default | S3-compatible Bronze storage |
| duckdb | elyssa-duckdb | elyssa-duckdb:latest | — | 2GB limit | Ephemeral analytics engine (on-demand) |
| airflow | elyssa-airflow | elyssa-airflow:latest | 18081→8080 | — | DAG orchestrator (standalone mode) |

**Network:** `elyssa-net` (bridge)
**Volumes:** pg_data, neo4j_data, neo4j_logs, rustfs_data, airflow_data

### Resource Constraints (Host: 16 GB physical, ~8 GB effective for WSL2/Docker)

| Consumer | Budget | Notes |
|----------|--------|-------|
| Neo4j heap | 2 GB | |
| Neo4j pagecache | 4 GB | |
| Postgres shared_buffers | 512 MB | |
| Postgres shm_size | 2 GB | |
| DuckDB (standalone) | 2 GB limit | Ephemeral, not always running |
| **DuckDB (inside Airflow)** | **700 MB** | Per-bronze_operator memory_limit |
| Airflow standalone | baseline | Includes webserver + scheduler + triggerer |
| OS / WSL2 overhead | ~2–3 GB | |

## Dockerfiles

### Dockerfile.airflow (apache/airflow:3.3.0)
- **Base:** `apache/airflow:3.3.0`
- **Extra packages:** gcc, libpq-dev, wget, procps (for psycopg2, DuckDB, debugging)
- **Python deps:** duckdb==1.1.3, pyarrow==25.0.0, psycopg2-binary==2.9.10, neo4j==6.2.0, dbt-core==1.11.11, dbt-postgres==1.11.0, great-expectations==1.18.2, pyyaml==6.0.3, python-dotenv==1.0.1
- **dbt:** Pre-builds dbt deps from `data-engineering/gold/`
- **Healthcheck:** `curl -f http://localhost:8080/api/v2/monitor/health` (30s interval, 60s start period)
- **Startup:** `CMD ["standalone"]`

### Dockerfile.etl-runner (python:3.11-slim)
- **Base:** `python:3.11-slim`
- **Deps:** duckdb==1.1.3, psycopg2-binary==2.9.10, pyarrow==25.0.0, pyyaml==6.0.3, python-dotenv==1.0.1
- **Memory:** DUCKDB_MEMORY_LIMIT=4GB, threads=2
- **Purpose:** Dedicated ETL engine that does NOT share RAM with Airflow
- **State:** container exists but is **not yet wired into the DAG** — all DuckDB work runs inside Airflow tasks

### Dockerfile.postgres (postgres:16 + timescaledb)
- TimescaleDB 2.28 pre-installed
- Custom postgres config with tuned shared_buffers, effective_cache_size, WAL settings
- Init scripts for schema creation at first boot

### Dockerfile.neo4j (neo4j:community)
- Aura-compatible config, 2G heap, 4G pagecache

### Dockerfile.rustfs (rustfs/rustfs:latest)
- S3-compatible storage, credentials from `docker/.env` (`S3_ACCESS_KEY` / `S3_SECRET_KEY`)

## Airflow DAG: `imdb_pipeline`

**Schedule:** `0 9 1 * *` (9 AM on 1st of each month), catchup=False, max_active_runs=2

### Task Graph
```
imdb_sensor → bronze_ingest → silver_transform → gold_dbt_run
                                                      ↓
                                              gold_dbt_test → dq_checks → freshness_monitor
```

### Key Config
- **bronze_ingest**
  - DuckDB `memory_limit='700MB'`, threads=2
  - Temp directory: `/opt/airflow/output/tmp/duckdb_spill/` (falls back to `/tmp/`)
  - Checkpoint resume: skips tables whose `.parquet` already exists at output path
  - Processes 7 IMDb tables: title.akas, title.basics, title.crew, title.episode, title.principals, title.ratings, name.basics
  - Per-table CHECKPOINT to free temp space between large tables
  - Source: local files at `data-engineering/duke/gate0/source/` (all 7 .tsv.gz exist)
  - Quarantine: invalid rows logged to PostgreSQL `bronze.quarantine_log`
  - `retries=1` (override from default 4)
- **silver_transform**
  - DuckDB `memory_limit='1.2GB'`, threads=2
  - Chunked COPY at 5M rows per chunk
  - SCD2 via effective_date/end_date on dim tables
  - 10 target tables: dim_title, dim_person, dim_date, fact_title_rating, fact_title_principal, fact_performance, fact_episode, dim_region, dim_language, dim_genre
- **gold_dbt_run / gold_dbt_test** — dbt models for star-schema marts
- **dq_checks / freshness_monitor** — Great Expectations + freshness SLA

### Notifications (added but env-var-gated)
- `PIPELINE_NOTIFICATION_URL` — POST webhook on failure (ntfy.sh, Slack, etc.)
- `PIPELINE_STATUS_FILE` — JSON status file written on task success/failure
- Callbacks: `on_success_callback`, `on_failure_callback`, `on_retry_callback`

## Configuration Files

| File | Location |
|------|----------|
| PostgreSQL init | `docker/postgres/init-scripts/` |
| PostgreSQL custom config | `docker/postgres/custom.conf` |
| Retry policy | `data-engineering/orchestration/config/retry.yaml` |
| Pipeline paths | `data-engineering/orchestration/config/paths.yaml` |
| Logging config | `data-engineering/orchestration/config/logging.yaml` |
| dbt profiles | `data-engineering/gold/profiles.yml` |

## Pipeline Attempts Log

### Attempt 1 — Single `standalone` service (pre-session baseline)
- **Status:** Airflow starts, scheduler runs, tasks enqueued
- **Failure:** `bronze_ingest` killed by OS (OOM) — default DuckDB `memory_limit='6GB'` exceeded WSL2 8 GB cap
- **Log signature:** Task exits with code -9 (SIGKILL), no Python exception traceback

### Attempt 2 — Split services (Phase 1d: scheduler/api-server/triggerer/dag-processor)
- **Change:** Replaced `airflow standalone` with 4 separate services to isolate subprocess tree
- **Status:** All 4 services start, db-init succeeds, DAG serialized
- **Failure:** `pipeline_start` (EmptyOperator) never runs — `up_for_retry` permanently
- **Root cause:** Airflow 3.3.0 LocalExecutor uses `ActivitySubprocess` which requires execution API HTTP calls from worker subprocess to api-server. With separate containers, the worker inside scheduler container connects to `localhost:8080` (its own port, not the api-server).
- **Attempted fix 1:** Set `AIRFLOW__CORE__ENDPOINT_URL=http://elyssa-airflow-api-server:8080/` — no effect (wrong config key)
- **Attempted fix 2:** Set `AIRFLOW__CORE__EXECUTION_API_SERVER_URL=http://elyssa-airflow-api-server:8080/execution/` — correct URL resolved, but `httpx.ReadTimeout` persisted
- **Attempted fix 3:** Set `PYTHONPATH` in Dockerfile — didn't help, the issue is execution API connectivity

### Attempt 3 — Single `standalone` (reverted, current state)
- **Change:** Reverted both Dockerfile and compose to single-service standalone
- **Status:** All containers removed, build cache pruned (~3 GB reclaimed), code committed at 3890df4
- **Docker images not yet rebuilt** — `docker compose build` needed before `docker compose up -d`

## Key Issues Found

### 1. Airflow 3.3.0 LocalExecutor + Separate Services
Airflow 3's `standalone` runs scheduler, webserver, api-server, triggerer in one process tree — LocalExecutor workers communicate with api-server via `localhost:8080`. When split into separate containers, worker subprocesses inside the scheduler container cannot reach the api-server container without explicit `EXECUTION_API_SERVER_URL` config. Even when set correctly, `httpx.ReadTimeout` occurs under unknown conditions.

**Workaround:** Use `standalone` (single container) for local dev.

### 2. WSL2 RAM Cap (8 GB effective vs 16 GB host)
Docker Desktop for Windows runs inside a WSL2 VM with a default cap of **8 GB** (configurable in `.wslconfig`). Host shows 93% RAM usage (14.9/16 GB) partly because WSL2 pre-allocates. DuckDB with default 6 GB memory_limit causes OOM kills under this cap.

**Mitigation:** Reduced to 700 MB in bronze_operator, 1.2 GB in silver_operator.

### 3. Python Site-Packages Path Mismatch (multi-stage build)
Builder stage (`python:3.13-slim`) installs to `/usr/local/lib/python3.13/site-packages/`, but runtime image's Python is at `/usr/python/bin/python3.13` with site-packages at `/usr/python/lib/python3.13/site-packages/`. The `apache/airflow` base image configures `--user` installs into `/home/airflow/.local/lib/python3.13/site-packages/`.

**Fix:** Single-stage build avoids this entirely — `pip install` directly into the runtime image's correct Python.

### 4. Local Source Data Exists — No Download Needed
All 7 IMDb `.tsv.gz` files are present at `data-engineering/duke/gate0/source/`. The Bronze operator can read them directly instead of downloading from IMDb. The operator falls back to local path from `paths.yaml` `silver.source_dir`.

### 5. Pipeline Requires Unpaused DAG
After first deployment, the DAG is `paused = True` (Airflow 3 default for non-scheduled DAGs). Must run `airflow dags unpause imdb_pipeline` before tasks execute.
