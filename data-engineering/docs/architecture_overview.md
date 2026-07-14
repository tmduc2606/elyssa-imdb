# Elyssa-IMDb Data Engineering — Architecture Overview

## Medallion Architecture

The DE pipeline follows the **Bronze → Silver → Gold** medallion pattern:

### Bronze Layer (Raw Ingestion)
- **Source**: IMDb `.tsv.gz` datasets (7 tables) + PostgreSQL CDC via DuckDB
- **Storage**: Apache Parquet (Snappy compression), partitioned by source table
- **Fidelity**: Raw preservation — `\N` markers kept as literal strings
- **Validation**: Quarantine on corrupt files, column count mismatch, zero rows
- **Metadata**: Each batch tagged with `batch_id`, `ingestion_timestamp`, `source_file`, `row_count`, `checksum`

### Silver Layer (Transformed & Enriched)
- **Storage**: PostgreSQL + TimescaleDB (hypertable for ratings)
- **Schema**: 14-table 3NF/BCNF with SCD2 tracking on `title_basics` and `name_basics`
- **Transformations**:
  - `\N` → SQL NULL conversion
  - Type casting (SMALLINT, BOOLEAN, DECIMAL, DateType)
  - Array normalization (genres, professions, known-for titles, characters)
  - Surrogate key assignment via sequences
- **Upsert Strategy**: MERGE with SCD2 — close old versions (`valid_to = NOW()`, `is_current = FALSE`), insert new

### Gold Layer (Analytics Marts)
- **Tool**: dbt (data build tool) with PostgreSQL adapter
- **Schema**: Star schema with staging → intermediate → marts
- **Marts**:
  - `fact_title_rating` — grain `(title_key, snapshot_date)`
  - `fact_title_principal` — grain `(title_key, name_key, character_key)`
  - `fact_episode` — grain `(episode_key, series_key)`
  - `dim_title` — denormalized title dimension with ratings, genres, directors
  - `dim_person` — person dimension with generation bucket, profession list

## Tech Stack

| Component | Technology | Version |
|-----------|-----------|---------|
| Processing | DuckDB | 1.x |
| Warehouse | PostgreSQL + TimescaleDB | 16 / 2.14 |
| Orchestration | Apache Airflow | 3.0.4 |
| Transformation | dbt (Postgres adapter) | 1.10.2 |
| Data Quality | Custom Python + dbt tests | — |
| Object Storage | RustFS (S3-compatible) | latest |
| Analytics | DuckDB | 1.x |
| Containerization | Docker Compose | — |

## Data Flow

```
IMDb .tsv.gz → [Bronze Ingestion (DuckDB)] → Parquet
Parquet → [Silver ETL (DuckDB→PostgreSQL COPY)] → PostgreSQL (SCD2)
Silver → [dbt run] → Gold Marts (PostgreSQL)
Gold → [DQ Checks] → data_quality_log
```

## SCD2 Logic

Slowly Changing Dimension Type 2 preserves history:
- **Surrogate key**: `title_key` / `name_key` from sequences
- **Tracking**: `valid_from` (TIMESTAMPTZ), `valid_to` (TIMESTAMPTZ), `is_current` (BOOLEAN)
- **On change**: Old row closed (`valid_to = NOW()`, `is_current = FALSE`), new row inserted
- **Query current**: `WHERE is_current = TRUE`
