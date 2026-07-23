# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

## Overview
Medallion architecture processing IMDb `.tsv.gz` into queryable star-schema marts.

| Layer | Engine | Output | Est. Time |
|-------|--------|--------|-----------|
| **Bronze** | DuckDB | Raw Parquet (7 tables) | ~47 min |
| **Silver** | DuckDB → psycopg2 COPY | PostgreSQL 3NF/BCNF (14 tables, SCD2) | ~3h 39m |
| **Gold** | dbt | Star-schema (6 fact/dim tables, 4.9 GB) | ~63 min |
| **Export** | DuckDB | Snappy Parquet → `marts/full/` | ~15 min |

## Prerequisites
- Docker 24+ with compose plugin
- 20 GB free disk, 16 GB RAM
- Raw IMDb `.tsv.gz` files in `duke/gate0/source/` (7 files, ~1.9 GB compressed)

---

## 1. Build & Start

```powershell
# Build all images (cached layers)
docker compose build

# Start services in background
docker compose up -d

# Wait for healthy state (30-60s)
docker compose ps --status running
```

## 2. Unpause & Trigger the DAG

```powershell
# Unpause the pipeline DAG (disabled by default)
docker exec elyssa-airflow airflow dags unpause imdb_pipeline_dag

# Trigger a fresh run
docker exec elyssa-airflow airflow dags trigger imdb_pipeline_dag
```

## 3. Watch Progress Layer by Layer

```powershell
# Follow all Airflow logs in real-time
docker compose logs -f airflow
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
Look for task `silver_transform` completing. Check output:
```powershell
# Silver table row counts
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
for t in ['title_basics','name_basics','title_rating','title_episode','title_principal','title_genre','title_director','title_writer','name_profession','name_known_for_title','title_principal_char']:
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
docker compose logs -f airflow | Select-String -Pattern "bronze_ingest|silver_transform|gold_dbt"

# Check for slow queries in PostgreSQL
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "
SELECT query, calls, round(mean_time::numeric, 1) AS mean_ms, rows
FROM pg_stat_statements ORDER BY mean_time DESC LIMIT 10;"
"
```

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
- [`docs/de_optimization_plan.md`](docs/de_optimization_plan.md) — 17-item optimization plan
- [`docs/schema_dictionary.md`](docs/schema_dictionary.md) — Column-level schema + known deltas
