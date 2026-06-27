# Elyssa-IMDb — Data Engineering Pipeline

## Quick Start

```bash
# Clone
git clone <repo-url> && cd elyssa-imdb

# Start infrastructure
docker compose up -d

# Wait for PostgreSQL healthcheck
docker compose ps
```

## Architecture

```
IMDb .tsv.gz → [Bronze: PySpark] → Parquet (RustFS)
PostgreSQL CDC → [Bronze: DuckDB/Spark] → Parquet
Parquet → [Silver: Spark ETL] → PostgreSQL (SCD2)
Silver → [Gold: dbt] → Star-schema marts
Gold → [Neo4j Sync] → Graph DB
Silver → [DQ Checks] → data_quality_log
```

## Running the Pipeline

### Option 1: Docker (Recommended)

```bash
# Full stack (Postgres, Neo4j, RustFS, Airflow, DuckDB)
docker compose up -d

# Trigger DAG via Airflow UI
open http://localhost:8081
# Enable `imdb_pipeline` dag → trigger manually
# Enable `neo4j_sync_dag` → auto-triggered after main pipeline
# Enable `quarterly_review_dag` → auto-triggers quarterly
```

### Option 2: Local (for development)

```bash
# 1. Start only PostgreSQL
docker compose up -d postgres

# 2. Create virtual environment
python -m venv .venv && source .venv/bin/activate  # or Scripts\activate on Windows
pip install -r data-engineering/requirements.txt

# 3. Initialize Silver schema + migrations
docker compose exec -U postgres postgres psql -f data-engineering/silver/schema.sql
docker compose exec -U postgres postgres psql -f data-engineering/silver/migrations/001_initial_schema.sql

# 4. Bronze ingestion (requires Spark running or local mode)
python data-engineering/bronze/ingest_imdb.py \
  data/title.akas.tsv.gz data/title.basics.tsv.gz data/title.crew.tsv.gz \
  data/title.episode.tsv.gz data/title.principals.tsv.gz data/title.ratings.tsv.gz \
  data/name.basics.tsv.gz

# 5. Silver ETL
spark-submit data-engineering/scripts/etl_runner.py \
  --bronze-path bronze/parquet/ \
  --jdbc-url "postgresql://elyssa:elyssa_pg_2026@localhost:54321/elyssa_warehouse" \
  --jdbc-user elyssa --jdbc-password elyssa_pg_2026

# 6. Gold dbt
cd data-engineering/gold
dbt debug        # verify connection
dbt run          # build all models
dbt test         # run tests
dbt docs generate # generate lineage docs
```

## Testing

### Unit Tests (no infrastructure required)

```bash
# Bronze layer
python -m pytest data-engineering/bronze/tests/ -v

# Orchestration (operators, sensors, DAG parsing)
python -m pytest data-engineering/orchestration/tests/ -v
```

### Integration Tests (requires Docker PostgreSQL)

```bash
# Start PostgreSQL
docker compose up -d postgres

# Silver layer
python -m pytest data-engineering/silver/tests/ -v

# Gold layer (dbt tests)
cd data-engineering/gold
dbt run && dbt test

# DQ checks
python data-engineering/dq/run_checks.py \
  --config data-engineering/dq/config.yaml \
  --jdbc-url "postgresql://elyssa:elyssa_pg_2026@localhost:54321/elyssa_warehouse" \
  --jdbc-user elyssa --jdbc-password elyssa_pg_2026
```

### Great Expectations (Bronze validation)

```bash
python data-engineering/dq/great_expectations/bronze_suite.py title.basics bronze/parquet/title.basics/
```

## Configuration

### dbt Connection
Edit `data-engineering/gold/profiles.yml` to change database credentials.

### Retry Policy
Edit `data-engineering/orchestration/config/retry.yaml`:
```yaml
max_retries: 4
base_delay_s: 60
max_delay_s: 1800
exponential_factor: 2
```

### DQ Checks
Edit `data-engineering/dq/config.yaml` to add/modify checks.

### Docker Services
Edit `docker/docker-compose.yml` to change ports, memory limits, or add services.

## Key Commands Reference

| Task | Command |
|------|---------|
| Start all services | `docker compose up -d` |
| Stop all services | `docker compose down` |
| View logs | `docker compose logs -f <service>` |
| PostgreSQL shell | `docker compose exec postgres psql -U elyssa -d elyssa_warehouse` |
| Airflow UI | `http://localhost:8081` |
| Neo4j Browser | `http://localhost:7475` |
| RustFS Console | `http://localhost:9101` |
| Run Bronze tests | `python -m pytest data-engineering/bronze/tests/ -v` |
| Run Silver tests | `python -m pytest data-engineering/silver/tests/ -v` |
| Run Gold tests | `cd data-engineering/gold && dbt test` |
| Run DQ checks | `python data-engineering/dq/run_checks.py --jdbc-url ...` |
| Generate dbt docs | `cd data-engineering/gold && dbt docs generate && dbt docs serve` |
| Validation report | `python data-engineering/scripts/validation_report.py` |

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `POSTGRES_USER` | elyssa | Database user |
| `POSTGRES_PASSWORD` | elyssa_pg_2026 | Database password |
| `POSTGRES_DB` | elyssa_warehouse | Database name |
| `NEO4J_AUTH` | neo4j/elyssa_neo_2026 | Neo4j credentials |
| `RUSTFS_ACCESS_KEY` | elyssa | S3 access key |
| `RUSTFS_SECRET_KEY` | elyssa_s3_2026 | S3 secret key |

## Troubleshooting

```bash
# Check service health
docker compose ps
docker compose logs postgres | tail -20

# Reset everything (WARNING: destroys data)
docker compose down -v && docker compose up -d

# Rebuild images after code changes
docker compose build --no-cache

# Check DAG parsing errors
docker compose logs airflow | grep -i error

# Verify dbt connection
cd data-engineering/gold && dbt debug --no-version-check
```
