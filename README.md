# Elyssa-IMDb — Data Engineering Pipeline (Phase 1)

End-to-end pipeline for IMDb: Bronze (Parquet) → Silver (PostgreSQL 3NF/SCD2) → Gold (dbt star-schema marts) → Neo4j (graph sync).

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 24+ | With `docker compose` plugin |
| Disk space | **~20 GB free** | Source TSVs (~10 GB) + Bronze Parquet (~2.5 GB) + Docker images (~6 GB) + volumes |
| RAM | 8 GB+ | Docker Desktop resource limit |

---

## Phase 1 — Full Pipeline

### 1. Download IMDb Source Data

```powershell
# Downloads 7 TSV files (~10 GB) to data-engineering/duke/gate0/source/
# Source: https://datasets.imdbws.com/
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
        # Decompress inline
        gunzip -c $out > "$dest/$f.tsv"
        Remove-Item $out
    } else {
        Write-Host "$f already exists, skipping"
    }
}
```

> **Note:** Source TSVs are gitignored under `data-engineering/duke/`. They must be present before the pipeline runs.

### 2. Build + Start Infrastructure

```powershell
# Prune stale build cache (saves ~25 GB over repeated rebuilds)
docker builder prune -f

# Build images and start all services
docker compose up -d --build

# Verify all services healthy (~30s)
docker compose ps
```

Expected output:

```
NAME              STATUS       PORTS
elyssa-postgres   healthy      54321 → 5432
elyssa-neo4j      healthy      7475 → 7474, 7688 → 7687
elyssa-rustfs     healthy      9100 → 9000, 9101 → 9001
elyssa-airflow    healthy      8081 → 8080
elyssa-duckdb     healthy      (internal)
```

### 3. Get Airflow Password

```powershell
docker exec elyssa-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

Login at http://localhost:8081 with `admin` / <generated password>.

### 4. Trigger Pipeline

Open Airflow UI → find `imdb_pipeline` DAG → toggle ON → click **Trigger DAG**.

Or via CLI:

```powershell
docker exec elyssa-airflow airflow dags trigger imdb_pipeline
```

The pipeline runs the following tasks:
`sensor → bronze_ingest → quarantine_check → silver_transform → gold_dbt_run → [gold_dbt_test, neo4j_sync] → dq_checks (+ Great Expectations) → freshness_check`

### 5. Monitor

```powershell
# Watch logs
docker compose logs -f airflow

# PostgreSQL shell (check tables)
docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse
```

---

## Cleanup

Docker named volumes accumulate pipeline data (PostgreSQL WAL, Neo4j store, Bronze Parquet). Free C: drive space:

```powershell
# Stop containers + delete all named volumes
docker compose down -v

# Prune Docker build cache
docker builder prune -a -f
```

To rebuild from scratch after cleanup:

```powershell
docker builder prune -f
docker compose up -d --build
```

---

## Quick Reference

| Task | Command |
|------|---------|
| Build + start | `docker builder prune -f && docker compose up -d --build` |
| Stop | `docker compose down` |
| Stop + delete data | `docker compose down -v` |
| View logs | `docker compose logs -f <service>` |
| PostgreSQL shell | `docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse` |
| Trigger DAG | `docker exec elyssa-airflow airflow dags trigger imdb_pipeline` |
| Test bronze | `python -m pytest data-engineering/bronze/tests/ -v` |

---

## Architecture

```
IMDb .tsv → [Bronze: ingest_imdb.py] → Parquet (RustFS / local)
Parquet  → [Silver: transform.py + upsert.py] → PostgreSQL (14 tables, SCD2)
PostgreSQL → [Gold: dbt] → Star-schema marts (dim_title, fact_performance, ...)
PostgreSQL → [Neo4j Sync] → Graph DB (Title, Person, Genre nodes)
PostgreSQL → [DQ: run_checks.py + GX] → data_quality_log
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8081 | `admin` / generated password |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| Neo4j Browser | http://localhost:7475 | `neo4j` / `elyssa_neo_2026` |
| RustFS Console | http://localhost:9101 | `elyssa` / `elyssa_s3_2026` |
