# Elyssa-IMDb — Data Engineering Pipeline

End-to-end IMDb pipeline: **Bronze** (Parquet) → **Silver** (PostgreSQL 3NF/SCD2) → **Gold** (dbt star-schema marts).

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 24+ | With `docker compose` plugin |
| Disk space | ~20 GB free | Source TSVs (~10 GB) + Parquet (~5 GB) + Docker images (~6 GB) |
| RAM | 16 GB+ | Docker Desktop resource limit (PostgreSQL 2 GB shm) |

---

## Quick Start

### 1. Download IMDb Source Data

```powershell
$files = @(
    "title.basics", "title.akas", "title.ratings", "title.episode",
    "title.crew", "title.principals", "name.basics"
)
$dest = "data-engineering/duke/gate0/source"
New-Item -ItemType Directory -Force -Path $dest | Out-Null

foreach ($f in $files) {
    $url = "https://datasets.imdbws.com/$f.tsv.gz"
    $out = "$dest/$f.tsv.gz"
    if (-not (Test-Path $out)) {
        Write-Host "Downloading $f ..."
        Invoke-WebRequest -Uri $url -OutFile $out
    } else {
        Write-Host "$f already exists, skipping"
    }
}
```

### 2. Build + Start Infrastructure

```powershell
docker builder prune -f
docker compose up -d --build
docker compose ps
```

Expected:

```
NAME              STATUS       PORTS
elyssa-postgres   healthy      54321 -> 5432
elyssa-neo4j      healthy      7475 -> 7474, 7688 -> 7687
elyssa-rustfs     healthy      9100 -> 9000, 9101 -> 9001
elyssa-airflow    healthy      8081 -> 8080
elyssa-duckdb     healthy      (internal)
```

### 3. Get Airflow Password

```powershell
docker exec elyssa-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Login at http://localhost:8081 with `admin` / \<generated password\>.

### 4. Trigger Pipeline

DAGs are **paused by default** on first deploy. Unpause before triggering.

**CLI method:**

```powershell
# Unpause (required — DAGs start paused)
docker exec elyssa-airflow airflow dags unpause imdb_pipeline -y

# Trigger
docker exec elyssa-airflow airflow dags trigger imdb_pipeline
```

**UI method:**

1. Open Airflow at http://localhost:8081
2. Log in with `admin` / \<generated password\>
3. Find `imdb_pipeline` in the DAG list
4. Toggle the **Pause/Unpause** switch to unpause (grey = unpaused)
5. Click the **Play** button (▶) → **Trigger DAG**

Pipeline tasks: `sensor → bronze_ingest → quarantine_check → silver_transform → gold_dbt_run → gold_dbt_test → dq_checks → freshness_check`

### 5. Monitor

#### Live logs

```powershell
docker compose logs -f airflow
```

#### DAG and task status

```powershell
# DAG run status
docker exec elyssa-airflow airflow dags list-runs imdb_pipeline

# Task-level status for current run
docker exec elyssa-airflow airflow tasks states-for-dag-run imdb_pipeline manual__2026-07-13T01:06:12.255890+00:00

# Single task state
docker exec elyssa-airflow airflow tasks state imdb_pipeline bronze_ingest manual__2026-07-13T01:06:12.255890+00:00
```

#### Task logs (Airflow 3.x REST API)

Airflow 3.x removed `airflow tasks logs` from the CLI. Use the REST API instead.

```powershell
# 1. Get admin password
docker exec elyssa-airflow python3 -c "import json; d=json.load(open('/opt/airflow/simple_auth_manager_passwords.json.generated')); print(list(d.values())[0])"

# 2. Get auth token
$token = curl -s -X POST "http://localhost:8081/auth/token" `
  -H "Content-Type: application/x-www-form-urlencoded" `
  -d "username=admin&password=PASSWORD" | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])"

# 3. View task logs (replace RUN_ID, TASK_ID)
curl -s -H "Authorization: Bearer $token" `
  "http://localhost:8081/api/v2/dags/imdb_pipeline/dagRuns/RUN_ID/taskInstances/TASK_ID/logs/1" | `
  python3 -c "import sys,json; [print(e.get('event','')) for e in json.load(sys.stdin)['content']]"
```

#### Bronze output

```powershell
docker exec elyssa-airflow ls -lh /opt/airflow/output/bronze/
```

#### Quick data checks

```powershell
# Silver: row counts + latest batch
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "SELECT table_name, n_live_tup FROM pg_stat_user_tables WHERE schemaname='silver' ORDER BY table_name;"
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "SELECT batch_id, table_name, row_count, ingested_at FROM silver.batch_metadata ORDER BY ingested_at DESC LIMIT 10;"

# Gold: dbt source freshness
docker exec elyssa-airflow dbt source freshness --project-dir /opt/airflow/data-engineering/gold --profiles-dir /opt/airflow/data-engineering/gold


```

---

## Cleanup

```powershell
docker compose down -v         # Stop + delete all data volumes
docker builder prune -a -f     # Prune all build cache
```

Rebuild from scratch:

```powershell
docker builder prune -f && docker compose up -d --build
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Build + start | `docker builder prune -f && docker compose up -d --build` |
| Stop | `docker compose down` |
| Stop + delete data | `docker compose down -v` |
| View live logs | `docker compose logs -f airflow` |
| DAG run status | `docker exec elyssa-airflow airflow dags list-runs imdb_pipeline` |
| Task state | `docker exec elyssa-airflow airflow tasks state imdb_pipeline <task_id> <run_id>` |
| Task logs | _see §5 REST API — Airflow 3.x has no `tasks logs` CLI_ |
| Bronze files | `docker exec elyssa-airflow ls -lh /opt/airflow/output/bronze/` |
| PostgreSQL shell | `docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse` |
| Trigger DAG | `docker exec elyssa-airflow airflow dags unpause imdb_pipeline -y && docker exec elyssa-airflow airflow dags trigger imdb_pipeline` |

---

## Architecture

```
IMDb .tsv.gz → [Bronze: DuckDB ingestion] → Parquet on disk
Parquet → [Silver: DuckDB→PostgreSQL COPY] → PostgreSQL 3NF/BCNF (14 tables, SCD2)
PostgreSQL → [Gold: dbt] → Star-schema marts (6 tables, 4 views)
PostgreSQL → [DQ Checks] → data_quality_log
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8081 | `admin` / generated password |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |

| RustFS Console | http://localhost:9101 | `elyssa` / `elyssa_s3_2026` |

---

## Documentation

| Document | Description |
|----------|-------------|
| `data-engineering/docs/phase1_summary.md` | Unified Phase 1 summary — row counts, performance, fixes, architecture decisions |
| `data-engineering/docs/architecture_overview.md` | Medallion architecture, tech stack, SCD2 logic |
| `data-engineering/docs/etl_pipeline.md` | DAG flow, retry policies, failure handling |
| `data-engineering/docs/schema_dictionary.md` | Silver + Gold schema reference (all columns, types) |
| `data-engineering/docs/data_quality_tests.md` | Test coverage and how to run |
| `data-engineering/docs/disaster_recovery.md` | RPO/RTO, backup/restore procedures |
| `data-engineering/docs/blueprint_database_ingestion.md` | Phase 2A blueprint |
| `data-engineering/docs/pipeline-optimization-blueprint.md` | Optimization roadmap |
| `data-engineering/docs/etl_pipeline.md` | DAG flow, retry policies, failure handling |
| `data-engineering/docs/schema_dictionary.md` | Silver + Gold schema reference (all columns, types) |
| `data-engineering/docs/data_quality_tests.md` | Test coverage and how to run |
| `data-engineering/docs/disaster_recovery.md` | RPO/RTO, backup/restore procedures |
| `data-engineering/docs/blueprint_database_ingestion.md` | Phase 2A blueprint |
| `data-engineering/docs/pipeline-optimization-blueprint.md` | Optimization roadmap |
