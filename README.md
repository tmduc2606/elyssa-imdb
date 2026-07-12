# Elyssa-IMDb — Data Engineering Pipeline

End-to-end IMDb pipeline: **Bronze** (Parquet) → **Silver** (PostgreSQL 3NF/SCD2) → **Gold** (dbt star-schema marts) → **Neo4j** (graph sync).

---

## Prerequisites

| Requirement | Version | Notes |
|-------------|---------|-------|
| Docker | 24+ | With `docker compose` plugin |
| Disk space | ~20 GB free | Source TSVs (~10 GB) + Parquet (~5 GB) + Docker images (~6 GB) |
| RAM | 16 GB+ | Docker Desktop resource limit (PostgreSQL 2 GB shm, Neo4j 6 GB heap+cache) |

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

```powershell
docker exec elyssa-airflow airflow dags trigger imdb_pipeline
```

Pipeline tasks: `sensor → bronze_ingest → quarantine_check → silver_transform → gold_dbt_run → [gold_dbt_test, neo4j_sync] → dq_checks → freshness_check`

### 5. Monitor

```powershell
docker compose logs -f airflow
docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse
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
| View logs | `docker compose logs -f <service>` |
| PostgreSQL shell | `docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse` |
| Trigger DAG | `docker exec elyssa-airflow airflow dags trigger imdb_pipeline` |

---

## Architecture

```
IMDb .tsv.gz → [Bronze: DuckDB ingestion] → Parquet on disk
Parquet → [Silver: PySpark ETL] → PostgreSQL (14 tables, SCD2)
PostgreSQL → [Gold: dbt] → Star-schema marts (6 tables, 4 views)
PostgreSQL → [Neo4j Sync] → Graph DB (Title, Person nodes + ACTED_IN relationships)
PostgreSQL → [DQ Checks] → data_quality_log
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8081 | `admin` / generated password |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| Neo4j Browser | http://localhost:7475 | `neo4j` / `elyssa_neo_2026` |
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
