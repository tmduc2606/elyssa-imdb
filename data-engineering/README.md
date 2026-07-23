# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

## Overview
Medallion architecture processing IMDb `.tsv.gz` into queryable star-schema marts.
- **Bronze** — DuckDB ingestion → Raw Parquet (all_varchar=true, typed schemas available via `BRONZE_SCHEMAS`)
- **Silver** — DuckDB→CSV→psycopg2 COPY → PostgreSQL 3NF/BCNF (14 tables, SCD2 on title_basics + name_basics)
- **Gold** — dbt → Star-schema (13 models: 5 staging views, 2 intermediate ephemeral, 6 mart tables)

## Prerequisites
- Docker 24+ with compose plugin
- 20 GB free disk, 16 GB RAM
- Raw IMDb `.tsv.gz` files in `duke/gate0/source/` (7 files, ~1.9 GB compressed)

---

## Quick Start: Full Pipeline via Airflow

```powershell
# 1. Build all Docker images (cached)
make build-quick

# 2. Start services (PostgreSQL, Airflow, etc.)
make up

# 3. Wait for healthy (30-60s)
docker compose ps --status running

# 4. Trigger the DAG from Airflow UI at http://localhost:8081
#    Or via CLI:
docker exec elyssa-airflow airflow dags trigger imdb_pipeline_dag

# 5. Watch progress
docker compose logs -f airflow
```

---

## Layer-by-Layer Testing & Live Progress

### 1. Bronze Layer (DuckDB TSV→Parquet)

**Trigger standalone:**
```powershell
docker exec elyssa-airflow python -c "
from operators.bronze_operator import BronzeIngestOperator
from airflow.utils.context import Context
op = BronzeIngestOperator(
    task_id='test_bronze',
    source_tables=['title.basics', 'name.basics', 'title.ratings', 'title.principals', 'title.episode', 'title.crew', 'title.akas']
)
# Dry-run: build the SQL strings without executing
print('BRONZE_SCHEMAS loaded:', list(op.BRONZE_SCHEMAS.keys()))
for t in op.source_tables:
    sd = op.BRONZE_SCHEMAS.get(t, {})
    print(f'  {t}: {len(sd)} columns -> {list(sd.keys())[:3]}...')
"
```

**Live progress — Bronze row counts:**
```powershell
docker exec elyssa-airflow python -c "
import duckdb
con = duckdb.connect(':memory:')
for t in ['title.basics','name.basics','title.ratings','title.principals','title.episode','title.crew','title.akas']:
    path = f'/opt/airflow/data-engineering/duke/gate0/source/{t}.tsv.gz'
    cnt = con.execute(f\"SELECT count(*) FROM read_csv('{path}', delim='\\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape='')\").fetchone()[0]
    print(f'  {t}: {cnt:>12,} rows')
"
```

**Bronze output check (Parquet files):**
```powershell
docker exec elyssa-airflow ls -lh /opt/airflow/output/bronze/
```

**Bronze quarantine check:**
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute('SELECT table_name, count(*) FROM silver.quarantine GROUP BY table_name')
for r in cur.fetchall():
    print(f'  {r[0]}: {r[1]} quarantined rows')
cur.execute('SELECT count(*) FROM silver.batch_metadata')
print(f'  batch_metadata records: {cur.fetchone()[0]}')
"
```

---

### 2. Silver Layer (DuckDB→PostgreSQL ETL + SCD2)

**Trigger standalone (single table):**
```powershell
docker exec elyssa-airflow python -c "
from operators.silver_operator import SilverTransformOperator
op = SilverTransformOperator(task_id='test_silver', source_tables=['title_basics'])
print('Silver operator loaded, source_tables:', op.source_tables)
"
```

**Live progress — Silver table row counts:**
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
tables = ['title_basics', 'name_basics', 'title_rating', 'title_episode', 'title_principal',
          'title_genre', 'title_director', 'title_writer', 'name_profession', 'name_known_for_title',
          'title_principal_char']
for t in tables:
    cur.execute(f\"SELECT count(*) FROM silver.{t}\")
    print(f'  silver.{t}: {cur.fetchone()[0]:>12,} rows')
cur.execute(\"SELECT count(*) FROM silver.title_basics WHERE is_current = TRUE\")
print(f'  silver.title_basics (current): {cur.fetchone()[0]:>12,} rows')
cur.execute(\"SELECT count(*) FROM silver.name_basics WHERE is_current = TRUE\")
print(f'  silver.name_basics (current): {cur.fetchone()[0]:>12,} rows')
"
```

**SCD2 version count:**
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute(\"SELECT count(*) FROM silver.title_basics WHERE is_current = FALSE\")
print(f'  title_basics historical versions: {cur.fetchone()[0]}')
cur.execute(\"SELECT count(*) FROM silver.name_basics WHERE is_current = FALSE\")
print(f'  name_basics historical versions: {cur.fetchone()[0]}')
"
```

---

### 3. Gold Layer (dbt Star-Schema)

**Run dbt standalone:**
```powershell
docker exec elyssa-airflow dbt run --project-dir /opt/airflow/data-engineering/gold --target prod
```

**Run dbt tests:**
```powershell
docker exec elyssa-airflow dbt test --project-dir /opt/airflow/data-engineering/gold --target prod
```

**Live progress — Gold table row counts:**
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
tables = ['dim_title', 'dim_person', 'fact_title_rating', 'fact_title_principal', 'fact_performance', 'fact_episode']
for t in tables:
    cur.execute(f\"SELECT count(*) FROM gold.{t}\")
    print(f'  gold.{t}: {cur.fetchone()[0]:>12,} rows')
"
```

**Gold export to Parquet (after dbt tests pass):**
```powershell
make export
# Verify:
docker exec elyssa-airflow ls -lh /opt/airflow/output/gold/
docker exec elyssa-airflow cat /opt/airflow/output/gold/_MANIFEST.json
```

**Gold DQ log:**
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute('SELECT check_name, metric_name, metric_value, threshold, passed FROM silver.data_quality_log ORDER BY logged_at DESC LIMIT 20')
for r in cur.fetchall():
    print(f'  {r[0]:40s} {str(r[1]):20s} val={str(r[2]):>8s} thresh={r[3]} {\"PASS\" if r[4] else \"FAIL\"}')
"
```

---

## Live Pipeline Monitoring

### Airflow Task Progress
```powershell
# List DAG runs
docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline_dag

# Check task status
docker exec elyssa-airflow tasks states-for-dag-run imdb_pipeline_dag <run_id>

# Stream all service logs
docker compose logs -f airflow postgres

# Watch specific layer in real-time
docker compose logs -f airflow | Select-String -Pattern "bronze_ingest|silver_transform|gold_dbt"
```

### PostgreSQL Query Performance
```powershell
# Slow queries (>1s)
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "
SELECT query, calls, mean_time_ms, rows
FROM pg_stat_statements
ORDER BY mean_time_ms DESC
LIMIT 10;"
"

# Current running queries
docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "
SELECT pid, state, query_start, query
FROM pg_stat_activity
WHERE state != 'idle'
ORDER BY query_start DESC;"
"
```

### Gold Export Audit Trail
```powershell
# Read the manifest
docker exec elyssa-airflow python -c "
import json
m = json.load(open('/opt/airflow/output/gold/_MANIFEST.json'))
total_gb = sum(e['file_size_mb'] for e in m) / 1024
print(f'Gold export: {len(m)} files, {total_gb:.1f} GB')
for e in m:
    print(f'  {e[\"table\"]:25s} {e[\"file_size_mb\"]:>8.1f} MB  sha256={e[\"sha256\"][:16]}...')
"
```

---

## Tier 1+2 Optimization Verification

After implementing the [DE Optimization Plan](docs/de_optimization_plan.md), verify each fix:

| # | Fix | Verification Command |
|---|-----|---------------------|
| O1 | fact_performance PK grain | `dbt test --project-dir /opt/airflow/data-engineering/gold --select fact_performance` |
| O2 | fact_episode PK grain | `dbt test --project-dir /opt/airflow/data-engineering/gold --select fact_episode` |
| O3 | fact_title_principal DQ SQL | `dbt test --project-dir /opt/airflow/data-engineering/gold --select fact_title_principal` |
| O4 | FK pre-check | Check `silver.fk_checks` run output for `fact_performance_nconst_exists_in_dim_person` |
| O5 | Documentation | `cat data-engineering/docs/schema_dictionary.md \| grep -A 10 "Known Delta"` |
| O6 | Manifest present | `test -f /opt/airflow/output/gold/_MANIFEST.json && echo "OK"` |
| O7 | dbt threads | `docker exec elyssa-airflow grep threads /opt/airflow/data-engineering/gold/profiles.yml` |
| O8 | Bronze schemas | Check logs for `read_csv(?, columns={...` instead of `all_varchar=true` |
| O9 | Incremental models | `grep -l "materialized='incremental'" /opt/airflow/data-engineering/gold/models/marts/*.sql` |
| O10 | Composite indexes | `docker exec elyssa-postgres psql -U elyssa -d elyssa_warehouse -c "\di gold.*"` |
| O11 | Actor co-occurrence | `docker exec elyssa-airflow dbt run --project-dir /opt/airflow/data-engineering/gold --select agg_actor_cooccurrence` |

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow UI | http://localhost:8081 | `admin` / generated on first start |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| RustFS Console | http://localhost:9101 | `elyssa` / `elyssa_s3_2026` |

---

## Key Files

| File | Description |
|------|-------------|
| `bronze/` | DuckDB ingestion scripts |
| `silver/` | PySpark ETL transforms + SCD2 |
| `gold/` | dbt models (staging, intermediate, marts) |
| `orchestration/dags/` | Airflow DAG definition |
| `orchestration/operators/` | Custom Airflow operators |
| `dq/` | Data quality check runner |
| `docs/specialized_assessment.md` | 56-check DE assessment (40 PASS, 6 WARN, 5 FAIL) |
| `docs/de_optimization_plan.md` | 17 optimizations across 3 tiers |
| `docs/schema_dictionary.md` | Column-level schema + SCD2 delta documentation |

## Outputs
- `../data-science/marts/full/*.parquet` (6 Gold marts, ~4.9 GB Snappy)
- `../data-science/marts/full/_MANIFEST.json` (export audit trail)

## Contracts
- [gold-to-ds.md](../data-science/contracts/gold-to-ds.md) — DE → DS
- [gold-to-api.md](../web-application/contracts/gold-to-api.md) — DE → Web
