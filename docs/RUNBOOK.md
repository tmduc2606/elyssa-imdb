# Elyssa Full Pipeline Runbook

Sequential execution on reference hardware (AMD Athlon 200GE, 16 GB RAM).

**Memory:** pipeline-only compose (postgres + airflow + etl-runner) peaks at ~5 GB. Neo4j/rustfs stopped by `pipeline-mode.ps1 start` to free RAM.

**Airflow version:** 3.3.0 — CLI differs from v2 (`dags list-runs`, `tasks states-for-dag-run`, etc.)

**Code state:** All DE hotfixes + DS Phase 2 optimisations committed (`47c2daf`, `e8b1b8a`, `4e58d21`).

## Day 1 — Data Engineering (~5 h 36 min, full 100% data)

### Phase 0 — Selective Container Build & Start

```powershell
cd C:\Users\Admin\Documents\GitHub\elyssa-imdb

# Build pipeline images only (parallel-safe on 2C/4T)
docker compose -f docker/docker-compose.yml build postgres
docker compose -f docker/docker-compose.yml build etl-runner
docker compose -f docker/docker-compose.yml build airflow

# Start pipeline-only services (uses pipeline-mode.ps1 — stops neo4j/rustfs)
.\docker\pipeline-mode.ps1 start

# Verify all 3 healthy
docker compose -f docker/docker-compose.yml ps
# Expected: elyssa-postgres (healthy), elyssa-etl-runner (healthy), elyssa-airflow (healthy)
```

**OOM workaround:**
```powershell
docker compose -f docker/docker-compose.yml build --no-cache postgres
docker compose -f docker/docker-compose.yml build --no-cache etl-runner
docker compose -f docker/docker-compose.yml build --no-cache airflow
```

### Phase 1 — Unpause & Trigger DAG

```powershell
# Verify Airflow UI at http://localhost:8081 (admin / admin)

docker exec elyssa-airflow airflow dags unpause imdb_pipeline
docker exec elyssa-airflow airflow dags trigger -r e2e_opt_$(Get-Date -Format 'yyyyMMddHHmmss') imdb_pipeline
```

### Phase 2 — Bronze Layer (~47 min, watch live)

Stream Airflow logs for sensor + bronze spawn:
```powershell
docker compose -f docker/docker-compose.yml logs -f --tail=20 airflow
```

Expected sequence:
```
imdb_sensor detects files → run_bronze spawns subprocess (PID=XXXX)
→ wait_bronze polls .completed marker
```

Follow actual bronze ingestion:
```powershell
docker exec elyssa-airflow tail -f /opt/airflow/output/tmp/bronze_runner.log
```
Expected: 7 files processed sequentially (akas, basics, crew, episode, name.basics, principals, ratings).

Checkpoint queries:
```powershell
# .completed marker
docker exec elyssa-airflow sh -c "test -f /opt/airflow/output/bronze/.completed && echo DONE || echo RUNNING"

# Row counts per source via DuckDB
docker exec elyssa-airflow python -c "
import duckdb
con = duckdb.connect(':memory:')
for t in ['title.basics','name.basics','title.ratings','title.principals','title.episode','title.crew','title.akas']:
    path = f's3://imdb-source/{t}.tsv.gz'
    cnt = con.execute(f\"SELECT count(*) FROM read_csv('{path}', delim='\\t', header=true, all_varchar=true, ignore_errors=true, quote='', escape='')\").fetchone()[0]
    print(f'  {t}: {cnt:>12,} rows')
"

# Quarantine rows
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute('SELECT table_name, count(*) FROM silver.quarantine GROUP BY table_name')
for r in cur.fetchall(): print(f'  {r[0]}: {r[1]} quarantined')
"
```

### Phase 3 — Silver Layer (~3 h 39 min, watch live)

Follow Airflow logs for spawn + wait_silver sensor:
```powershell
docker compose -f docker/docker-compose.yml logs -f airflow | Select-String -Pattern "wait_silver|Polling|SilverDoneSensor"
```

Watch actual etl-runner ETL progress:
```powershell
docker exec elyssa-etl-runner tail -f /opt/etl/tmp/silver_etl.log
# (same file visible from airflow: /opt/airflow/output/tmp/silver_etl.log)
```
Expected: 6 parents processed first (title_basics, title_akas, title_episode, title_rating, title_principal, name_basics), then 8 child tables (title_genre, title_director, title_writer, title_akas_type, title_akas_attribute, title_principal_char, name_profession, name_known_for_title). The sensor polls all 14 tables every 30 s (logs every 4th attempt, max 480) and fails fast if the `.silver.failed` marker appears.

Checkpoint — verify all 14 tables have rows:
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
for t in ['title_basics','title_akas','title_episode','title_rating','title_principal','name_basics',
          'title_genre','title_director','title_writer','title_akas_type','title_akas_attribute',
          'title_principal_char','name_profession','name_known_for_title']:
    cur.execute(f'SELECT count(*) FROM silver.{t}')
    cnt = cur.fetchone()[0]
    status = 'OK' if cnt > 0 else 'EMPTY'
    print(f'  silver.{t:30s} {cnt:>12,}  [{status}]')
"
```

### Phase 4 — Gold Layer (~70 min, watch live)

```powershell
docker compose -f docker/docker-compose.yml logs -f airflow | Select-String -Pattern "gold_dbt|Completed|PASS|FAIL|ERROR"
```

Expected dbt build sequence:
```
1/6 dim_title       → 2/6 dim_person
→ 3/6 fact_title_rating → 4/6 fact_title_principal
→ 5/6 fact_performance  → 6/6 fact_episode
```
dbt_operator.py acquires an `fcntl` exclusive lock, kills stale PIDs, cleans `__dbt_tmp`, runs `dbt run --full-refresh --no-partial-parse`, then `dbt test`.

Checkpoint — gold tables + dbt test results:
```powershell
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres', port=5432, user='elyssa', password='elyssa_pg_2026', dbname='elyssa_warehouse')
cur = con.cursor()
for t in ['dim_title','dim_person','fact_title_rating','fact_title_principal','fact_performance','fact_episode']:
    cur.execute(f'SELECT count(*) FROM gold.{t}')
    print(f'  gold.{t}: {cur.fetchone()[0]:>12,} rows')
cur.execute('SELECT check_name, metric_value, threshold, passed FROM silver.data_quality_log ORDER BY logged_at DESC LIMIT 15')
for r in cur.fetchall(): print(f'  {str(r[0]):40s} val={str(r[1]):>8s} thresh={r[2]}  {\"PASS\" if r[3] else \"FAIL\"}')
"
```

### Phase 5 — Data Quality, Freshness, Export (~15 min)

```powershell
docker compose -f docker/docker-compose.yml logs -f airflow | Select-String -Pattern "dq_checks|freshness_check|gold_export|pipeline_end"
```

Verify final outputs:
```powershell
# Check exported files
docker exec elyssa-airflow ls -lh /opt/airflow/output/gold/

# Manifest
docker exec elyssa-airflow python -c "
import json
m = json.load(open('/opt/airflow/output/gold/_MANIFEST.json'))
total_gb = sum(e['file_size_mb'] for e in m) / 1024
print(f'Export: {len(m)} files, {total_gb:.1f} GB')
for e in m: print(f'  {e[\"table\"]:25s} {e[\"file_size_mb\"]:>8.1f} MB')
"

# Verify DS can consume
ls -lh data-science/marts/full/
```

### Airflow 3.X CLI Quick Reference

```powershell
# DAG management
docker exec elyssa-airflow airflow dags list
docker exec elyssa-airflow airflow dags pause|unpause imdb_pipeline
docker exec elyssa-airflow airflow dags trigger -r <run_id> imdb_pipeline
docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline [--output json]
docker exec elyssa-airflow airflow dags delete imdb_pipeline

# Task monitoring
docker exec elyssa-airflow airflow tasks states-for-dag-run imdb_pipeline <run_id>
docker exec elyssa-airflow airflow tasks logs imdb_pipeline <task_id> <exec_date>
docker exec elyssa-airflow airflow tasks list -d imdb_pipeline --state failed|success
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t <task_id>

# System
docker exec elyssa-airflow airflow info
docker stats elyssa-postgres elyssa-airflow elyssa-etl-runner
```

### Quick Status Dashboard (One-Liner)

```powershell
Write-Host "=== Pipeline Status ===" -ForegroundColor Cyan; `
docker compose -f docker/docker-compose.yml ps; `
Write-Host "`nDAG Runs:" -ForegroundColor Cyan; `
docker exec elyssa-airflow airflow dags list-runs -d imdb_pipeline --output json 2>$null | `
  python -c "import sys,json; [print(f'  {r[\"run_id\"][-20:]:20s} state={r[\"state\"]:10s} start={r[\"start_date\"][:19]}') for r in json.load(sys.stdin)[:5]]"; `
Write-Host "`nLast 10 task events:" -ForegroundColor Cyan; `
docker exec elyssa-airflow python -c "
import psycopg2
con = psycopg2.connect(host='postgres',port=5432,user='elyssa',password='elyssa_pg_2026',dbname='elyssa_warehouse')
cur = con.cursor()
cur.execute(\"SELECT task_id, state, start_date FROM task_instance WHERE dag_id='imdb_pipeline' ORDER BY start_date DESC NULLS LAST LIMIT 10\")
for r in cur.fetchall(): print(f'  {r[0]:25s} {str(r[1]):10s} {str(r[2])[:19]}')
"
```

### Recovery — Re-run Specific Layers

```powershell
# Re-run Gold onward (if gold_dbt_run failed)
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t gold_dbt_run
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t gold_dbt_test
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t dq_checks
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t freshness_check
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t gold_export

# Re-run Export only
docker exec elyssa-airflow airflow tasks clear imdb_pipeline -t gold_export

# Full clean restart
.\docker\pipeline-mode.ps1 clean
```

### Estimated Timelines (100% Data)

| Layer | Est. Time | Bottleneck |
|-------|-----------|------------|
| Source sensor | ~5 min | Poke interval |
| Bronze ingestion | ~47 min | DuckDB CSV parsing (title.principals) |
| Bronze quarantine | ~2 min | FK checks |
| Silver (parents) | ~90 min | title_basics SCD2 |
| Silver (children) | ~2h 9m | title_principal_char UNNEST |
| Gold dbt run | ~63 min | fact_performance (episodic_content) |
| Gold dbt test | ~7 min | Referential integrity checks |
| DQ + Freshness | ~10 min | Row-count variance |
| Gold Export | ~15 min | postgres_scanner scan |
| **DE Total** | **~5h 36min** | — |


## Day 2 — Data Science (3-4 hours)

```powershell
Write-Host "=== Phase 2: Data Science Pipeline ===" -ForegroundColor Cyan
cd data-science
if (-not (Test-Path ".venv")) { python -m venv .venv }
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt --quiet

python scripts/run_pipeline.py --stage all
python scripts/validate_contracts.py
```

## Day 3 — Web Application (15 min)

```powershell
Write-Host "=== Phase 3: Web Application ===" -ForegroundColor Cyan
cd web-application/api
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload --port 8000 &

cd ../client
npm install --silent
npm run dev &

Start-Sleep -Seconds 5
curl http://localhost:8000/health
python -m pytest tests/ -q
```
