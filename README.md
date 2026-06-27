# Elyssa-IMDb — Data Engineering Pipeline

End-to-end data engineering pipeline for IMDb: Bronze (Parquet) → Silver (PostgreSQL 3NF/SCD2) → Gold (dbt star-schema marts) → Neo4j (graph sync).

---

## Quick Start

```powershell
# Clone
git clone <repo-url> && cd elyssa-imdb

# Build + start infrastructure (one-time or after code changes)
docker compose up -d --build

# Wait for PostgreSQL healthcheck
docker compose ps

# Trigger DAG via Airflow UI
open http://localhost:8081
# Enable `imdb_pipeline` dag → trigger manually
```

> **Note:** Always run `docker compose` from the **repo root** (`elyssa-imdb/`), not from `data-engineering/`.

All services should show `healthy`:

```
NAME              STATUS       PORTS
elyssa-postgres   healthy      54321 → 5432
elyssa-neo4j      healthy      7475 → 7474, 7688 → 7687
elyssa-rustfs     healthy      9100 → 9000, 9101 → 9001
elyssa-airflow    healthy      8081 → 8080
elyssa-duckdb     healthy      (internal)
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| **Airflow** | http://localhost:8081 | See below |
| **PostgreSQL** | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| **Neo4j Browser** | http://localhost:7475 | `neo4j` / `elyssa_neo_2026` |
| **RustFS Console** | http://localhost:9101 | `elyssa` / `elyssa_s3_2026` |

### Airflow Login

Airflow 3.x generates a random admin password on first startup. To retrieve it:

```powershell
docker exec elyssa-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

This prints JSON like `{"admin": "VqnH9zQBKCh8n3Ak"}`. Use `admin` as the username and the generated value as the password.

---

## Running the Pipeline

### First Time / After Code Changes

```powershell
# Rebuild images and start all services
docker compose up -d --build
```

### Via Airflow UI

1. Open http://localhost:8081 and log in
2. Find the `imdb_pipeline` DAG
3. Toggle it ON and click **Trigger DAG**

### Via CLI

```powershell
# Trigger the main pipeline
docker exec elyssa-airflow airflow dags trigger imdb_pipeline

# Check DAG status
docker exec elyssa-airflow airflow dags list
```

---

## Architecture

```
IMDb .tsv → [Bronze: ingest_imdb.py] → Parquet (RustFS / local)
Parquet → [Silver: transform.py + upsert.py] → PostgreSQL (14 tables, SCD2)
PostgreSQL → [Gold: dbt] → Star-schema marts (dim_title, fact_performance, ...)
PostgreSQL → [Neo4j Sync] → Graph DB (Title, Person, Genre nodes)
PostgreSQL → [DQ: run_checks.py] → data_quality_log
```

---

## Local Development (No Docker for PySpark)

```powershell
# 1. Start only PostgreSQL
docker compose up -d postgres

# 2. Python environment
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r data-engineering/requirements.txt

# 3. Initialize Silver schema
docker exec -i elyssa-postgres psql -U elyssa -d elyssa_warehouse < data-engineering/silver/schema.sql

# 4. Run unit tests (no DB needed)
python -m pytest data-engineering/bronze/tests/ -v
python -m pytest data-engineering/orchestration/tests/ -v

# 5. Run live benchmark (DuckDB, reads real Parquet)
python data-engineering/scripts/live_benchmark.py
```

---

## Testing

```powershell
# All bronze tests (87 tests)
python -m pytest data-engineering/bronze/tests/ -v

# Orchestration tests (24 tests)
python -m pytest data-engineering/orchestration/tests/ -v

# Full test suite (111 tests)
python -m pytest data-engineering/bronze/tests/ data-engineering/orchestration/tests/ -v
```

---

## Project Structure

```
elyssa-imdb/
├── data-engineering/
│   ├── bronze/          # Ingestion: ingest_imdb.py, db_reader.py, watermark.py
│   ├── silver/          # ETL: schema.sql (14 tables), transform.py, upsert.py, fk_checks.py
│   ├── gold/            # dbt project: staging → intermediate → marts
│   ├── orchestration/   # Airflow: DAG + 7 operators
│   ├── dq/              # Data quality: config.yaml, run_checks.py
│   ├── scripts/         # ETL runner, benchmarks, neo4j sync, validation
│   └── docs/            # Blueprints, evaluation, patch-ups
├── docker/              # Dockerfiles + docker-compose.yml
├── docker-compose.yml   # Root compose file (run from here)
└── docs/overview/       # Main proposal
```

---

## Key Commands

| Task | Command |
|------|---------|
| Start all | `docker compose up -d` |
| Stop all | `docker compose down` |
| Stop + delete data | `docker compose down -v` |
| Rebuild images | `docker compose build --no-cache` |
| View logs | `docker compose logs -f <service>` |
| PostgreSQL shell | `docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse` |
| Get Airflow password | `docker exec elyssa-airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated` |
| Trigger DAG | `docker exec elyssa-airflow airflow dags trigger imdb_pipeline` |
| dbt run | `docker exec elyssa-airflow bash -c "cd /opt/dbt && dbt run"` |
| Run tests | `python -m pytest data-engineering/bronze/tests/ -v` |

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_USER` | elyssa | Database user |
| `POSTGRES_PASSWORD` | elyssa_pg_2026 | Database password |
| `POSTGRES_DB` | elyssa_warehouse | Database name |
| `NEO4J_AUTH` | neo4j/elyssa_neo_2026 | Neo4j credentials |
| `RUSTFS_ACCESS_KEY` | elyssa | S3 access key |
| `RUSTFS_SECRET_KEY` | elyssa_s3_2026 | S3 secret key |

---

## Troubleshooting

```powershell
# Service won't start
docker compose ps
docker compose logs <service> | Select-Object -Last 20

# PostgreSQL unhealthy (stale volume)
docker compose down -v
docker compose up -d

# Airflow can't find DAGs
docker compose restart airflow

# Reset everything
docker compose down -v && docker compose build --no-cache && docker compose up -d
```
