# Gold Export Guide

## Overview

Exports 6 Gold Parquet files from PostgreSQL to `data-science/marts/gold/` for Data Science consumption.

## Tables Exported

| Table | Rows | Notes |
|-------|------|-------|
| `dim_person` | ~15.4M | SCD2-dimension |
| `dim_title` | ~12.6M | movies with runtime_minutes > 0 |
| `fact_episode` | ~9.7M | episode hierarchy |
| `fact_performance` | ~100M | cast/crew assignments |
| `fact_title_principal` | ~100M | principal credits |
| `fact_title_rating` | ~1.7M | TimescaleDB hypertable |

Excluded: `agg_actor_cooccurrence` (19 GB — not in DS contract).

## One-Step Export (inside Airflow container)

```bash
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/export_gold.py
```

This runs:
1. DuckDB `postgres_scanner` → Snappy Parquet (6 files)
2. Writes `_MANIFEST.json`
3. Creates `/tmp/gold_marts.tar.gz`
4. Attempts host mount copy (if `/mnt/host/` is mapped)

## Manual Export + Tar + docker cp

```bash
# 1. Run export inside container
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/export_gold.py

# 2. Create tar archive
docker exec elyssa-airflow sh -c "cd /opt/airflow/output/gold && tar -cf /tmp/gold_marts.tar *.parquet _MANIFEST.json && ls -lh /tmp/gold_marts.tar"

# 3. Copy to host
docker cp elyssa-airflow:/tmp/gold_marts.tar "$PWD/tmp_gold_marts.tar"

# 4. Extract to marts directory
tar -xf "$PWD/tmp_gold_marts.tar" -C "$PWD/data-science/marts/gold/"

# 5. Clean up
rm -f "$PWD/tmp_gold_marts.tar"
docker exec elyssa-airflow rm /tmp/gold_marts.tar
```

## Validate

```bash
# Check row counts
python -c "import json; d=json.load(open('data-science/marts/gold/_MANIFEST.json')); print(json.dumps(d['row_counts'], indent=2))"

# Verify Parquet files
python -c "
import pyarrow.parquet as pq
for t in ['dim_person','dim_title','fact_episode','fact_performance','fact_title_principal','fact_title_rating']:
    r = pq.read_metadata(f'data-science/marts/gold/{t}.parquet')
    print(f'{t}: {r.num_rows:,} rows, {r.num_columns} cols')
"
```
