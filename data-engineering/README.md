# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

## Overview
Medallion architecture processing IMDb `.tsv.gz` into queryable star-schema marts.

## Pipeline Stages
1. **Bronze** — DuckDB ingestion → Raw Parquet
2. **Silver** — PySpark ETL → PostgreSQL 3NF/BCNF (14 tables, SCD2)
3. **Gold** — dbt → Star-schema (6 tables, 4 views)

## Prerequisites
- Docker 24+ (docker compose plugin)
- 20 GB free disk
- 16 GB RAM

## Quick Start
```powershell
docker builder prune -f && docker compose up -d --build
```

## Key Files

| File | Description |
|------|-------------|
| `bronze/` | DuckDB ingestion scripts |
| `silver/` | PySpark ETL transforms + SCD2 |
| `gold/` | dbt models (staging, intermediate, marts) |
| `orchestration/dags/` | Airflow DAG definition |
| `orchestration/operators/` | Custom Airflow operators |
| `dq/` | Data quality check runner |
| `docs/` | Schema dictionary, architecture, tests |

## Output
- `data-science/marts/full/*.parquet` (6 Gold marts)
- `data-science/marts/full/_MANIFEST.json` (export metadata)

## Data Quality
See [docs/data_quality_tests.md](docs/data_quality_tests.md).

## Contracts
- [gold-to-ds.md](../data-science/contracts/gold-to-ds.md) — DE → DS
- [gold-to-api.md](../web-application/contracts/gold-to-api.md) — DE → Web

## Tests
```powershell
pytest bronze/tests/ -v
cd gold && dbt test
```
