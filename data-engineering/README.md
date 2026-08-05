<div align="center">

# Elyssa Data Engineering — Bronze→Silver→Gold Pipeline

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](../LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](../docs/SMOKE_TEST.md)
[![DuckDB](https://img.shields.io/badge/DuckDB-Analytics-orange.svg)](../data-engineering/README.md)
[![Airflow](https://img.shields.io/badge/Airflow-Orchestration-orange.svg)](../data-engineering/README.md)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-blue.svg)](../data-engineering/README.md)

</div>

## Overview

Medallion architecture processing IMDb `.tsv.gz` into queryable star-schema marts. All layers
read/write through **RustFS** (S3-compatible object store, localhost), with bind mounts for DS notebook consumption.

```
IMDb .tsv.gz ─▶ RustFS S3 (imdb-source/) ─▶ Bronze (DuckDB) ─▶ RustFS S3 (bronze/)
      ▶ Silver (PostgreSQL) ─▶ Gold (dbt) ─▶ Export (DuckDB) ─▶ marts/gold/ (bind mount)
      ▲                                            ▲
      └────────────── Airflow DAG orchestrates all 18 tasks ─────────────┘
```

| Layer | Engine | I/O | Output |
|-------|--------|-----|--------|
| **Bronze** | DuckDB + httpfs | S3 `imdb-source/` → S3 `bronze/` | Raw Parquet (7 tables, 212 M rows) |
| **Silver** | DuckDB → psycopg2 COPY | S3 → PostgreSQL | 3NF/BCNF (14 tables + 3 governance, SCD2) |
| **Gold** | dbt (threads=2) | PostgreSQL → PostgreSQL | Star-schema (12 models, 43 tests) |
| **Export** | DuckDB | PostgreSQL → bind mount | Snappy Parquet (6 marts ≈ 5.7 GB) + `_MANIFEST.json` |

## Performance Baseline

Measured on validated run `manual__2026-08-04T05:33:24` (AMD Athlon 200GE, 13.9 GB RAM).
Full report: [`docs/pipeline_performance_metrics.md`](docs/pipeline_performance_metrics.md) and the
12 figures in [`docs/figures/`](docs/figures/).

| Phase | Duration | Rows In | Rows Out | Bottleneck |
|-------|----------|---------|----------|------------|
| Bronze | 12 s | — | 212 M | Checkpoint reuse |
| Silver (ETL) | skipped | 212 M | 355 M | Checkpoint reuse |
| Silver (export) | 20 m | 355 M | 355 M | PostgreSQL → DuckDB |
| Gold (dbt run) | 2 h 59 m | 355 M | 241 M | Full-refresh, 12 models |
| Gold (dbt test) | 59 m | — | — | 43 tests (37P/6W/0E) |
| Gold (DQ + freshness) | 4 m | — | — | 7/7 PASS, 6/6 PASS |
| Gold (export) | 19 m | 241 M | 241 M | 5.7 GB Parquet |
| **Total** | **7 h 22 m** | | | |

**Memory — container level (RSS inside WSL2):**

| Container | Used | Limit | % of Limit |
|-----------|------|-------|------------|
| Airflow | 1.13 GB | 2.5 GB | 45% (peak ~1.8 GB during ETL) |
| Postgres | 105 MB | 2.0 GB | 5% |
| RustFS | 72 MB | 256 MB | 28% |
| **DE stack** | **~1.3 GB** | **6.76 GB** | no limit hit |

**Memory — host level (Windows + WSL2 VM + Docker Desktop + IDE/agents):**

| Pipeline stage | Observed host RAM (of 13.9 GB usable) |
|----------------|---------------------------------------|
| Bronze + download | ~88% |
| Silver (ETL peak) | **93–98%** (swap-thrashing observed pre-tuning) |
| Overall peak | ~96% |
| Gold (declining) | ~91% |
| Typical steady state | low-to-mid 80s % |

The WSL2 VM is hard-capped at **9 GB** (`.wslconfig`: `memory=9GB`, `swap=4GB`, 2 processors).
DE container caps sum to 6.76 GB, so the host keeps ~4 GB for Windows, Docker Desktop, IDE, and
coding agents. On a 16 GB laptop this pipeline runs at 85–95% host RAM for most of the run —
close other heavy apps during a full run. Tuning history: `.wslconfig` comments (R5/R6).

## Prerequisites

- Docker 24+ with Compose plugin
- 16 GB physical RAM (13.9 GB usable on the reference rig); WSL2 VM hard-capped at 9 GB
- **≥ 150 GB free disk** — the pipeline's on-disk footprint is dominated by Docker/WSL2, not the repo (see below)
- 512 GB SSD (mechanical disks choke on Silver/Gold I/O)

## Disk Footprint

Docker Desktop's WSL2 backend stores everything in a few large `*.vhdx` files (see the
[Q&A](#faq) in the root README for the "disk shows 100–130 GB" effect). Actual data breakdown on a fresh run:

| Consumer | Size |
|----------|------|
| PostgreSQL volumes (Silver 51 GB + Gold 38 GB + governance, in `elyssa_pg_data`) | **97 GB** |
| Docker local volumes (total, incl. RustFS S3 + airflow + etl temp) | 116.5 GB |
| Docker images + build cache | ~14 GB |
| Layer Parquet on host (`data-science/marts/`: bronze 2.6 + silver 4.5 + gold 5.7) | **~13 GB** |
| IMDb source `.tsv.gz` (in RustFS S3) | ~5 GB |
| **Post-trigger total** | **> 140 GB** |

The **97 GB PostgreSQL volume** is the single largest consumer — after a full run, prune or `compact vdisk`
(see root FAQ) to reclaim disk.

## Quick Start

All commands run from the **repo root**. The DE stack is independent from the web-app compose.

### Initial Setup — download IMDb data to RustFS S3

```powershell
docker compose -f docker/docker-compose.yml up -d

# Download 7 .tsv.gz files directly to RustFS S3 (streaming, no local disk)
docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/download_imdb.py
```

This populates `s3://imdb-source/`; the pipeline DAG sensor detects the files and triggers Bronze.

### Selective execution (`docker/pipeline-mode.ps1`)

```powershell
.\docker\pipeline-mode.ps1 start        # postgres + airflow + etl-runner + rustfs
.\docker\pipeline-mode.ps1 run bronze   # Bronze ingestion only
.\docker\pipeline-mode.ps1 run silver   # Silver ETL only
.\docker\pipeline-mode.ps1 run gold     # Gold dbt + export only
.\docker\pipeline-mode.ps1 run full     # Full end-to-end
.\docker\pipeline-mode.ps1 clean        # drop silver/gold schemas, wipe Parquet, restart
.\docker\pipeline-mode.ps1 stop
```

### Full manual run

```powershell
docker compose -f docker/docker-compose.yml build
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps --status running

# Sign in, then unpause + trigger the DAG
start http://localhost:18081             # admin / admin
docker exec elyssa-airflow airflow dags unpause imdb_pipeline
docker exec elyssa-airflow airflow dags trigger imdb_pipeline
```

> **Low-RAM tip:** build one service at a time (`docker compose -f docker/docker-compose.yml build postgres`).
> **WSL2 note:** Docker Desktop defaults to an 8 GB WSL2 memory cap regardless of host RAM — raise it in
> `%USERPROFILE%\.wslconfig` (`[wsl2] memory=12GB`) and check with `wsl --status`.

### Service memory budgets (from `docker/docker-compose.yml`)

| Service | `mem_limit` | Notes |
|---------|-------------|-------|
| postgres | 2.0 GB | + 1 GB `shm_size`; `shared_buffers=1GB`, `work_mem=256MB` |
| rustfs | 256 MB | S3 object store |
| etl-runner | 2.0 GB | `DUCKDB_MEMORY_LIMIT=2GB` |
| airflow | 2.5 GB | DAG orchestrator + webserver |
| **Sum (caps)** | **6.76 GB** | fits the 9 GB WSL2 VM cap with ~4 GB host headroom |

## Key Outputs

| Output | Description |
|--------|-------------|
| `../data-science/marts/gold/` | 6 Gold marts (Snappy Parquet ≈ 5.7 GB: dim_person 594 MB, dim_title 719 MB, fact_episode 133 MB, fact_performance 2.18 GB, fact_title_principal 1.89 GB, fact_title_rating 16 MB) |
| `../data-science/marts/gold/_MANIFEST.json` | Export audit trail with SHA256 checksums |
| `../data-science/marts/gold/.export.completed` | Gold export completion marker |
| `../data-science/marts/bronze/`, `../data-science/marts/silver/` | Layer Parquet + checkpoints/manifest |

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:18081 | `admin` / `admin` |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| RustFS S3 API | http://localhost:9100 | `elyssa` / `elyssa_s3_2026` |
| RustFS Console | http://localhost:9101 | — |

## Idempotency & Checkpoints

Each layer is resumable via completion markers — failed runs resume, never re-ingest:

| Layer | Marker | Behaviour |
|-------|--------|-----------|
| Bronze | `.completed` + per-table `.{table}.completed` | Skip already-ingested tables |
| Silver ETL | `.silver.completed` | Skipped when present |
| Silver export | `.export.completed` / `.export.failed` | Export sensor polls writers |
| Gold dbt | `.dbt.{run\|test}.completed` | Full-refresh; DQ retries ×3 |
| Gold export | `.export.completed` | Export sensor polls writers |
| Freshness | `_resolve_reference_time()` | 6-source fallback chain |

## Known Issues & Fixes

| Issue | Status | Fix / Mitigation |
|-------|--------|------------------|
| Child-table UNNEST hang | Applied | Child SQL uses `LATERAL UNNEST(...) WITH ORDINALITY` (no window fns); lower `DUCKDB_MEMORY_LIMIT` / ensure spill dir if it recurs |
| dbt lock contention | Applied | Exclusive file lock + stale-PID kill + `--full-refresh --no-partial-parse`; residual SIGTERM handling |
| `wait_silver` only checks parents | Applied | `SilverDoneSensor` now polls all 14 tables (up to 480 attempts) |
| Freshness ERROR on `silver.title_director` | Open | `title_director` lacks `ingested_at`; SLA still met |
| Airflow 3.3 deprecation warnings | Open | Cosmetic; migrate in Phase 2 |
| Redundant `gold_marts.tar.gz` | Applied | Tar removed; manifest counts read from Parquet footers |
| dbt test runtime (43 tests) | Mitigated | Non-contractual tests set to `severity: warn`; cooccurrence build serialised |

Historical Phase-1 fixes (orphan-pass kill loop, `title_crew` export, PostgreSQL ENOSPC, dbt contention)
are documented in `docs/final_pipeline_summary.md`.

## Docs

- [`docs/architecture_overview.md`](docs/architecture_overview.md) — medallion architecture & SCD2 design
- [`docs/schema_dictionary.md`](docs/schema_dictionary.md) — Silver/Gold schema reference
- [`docs/disaster_recovery.md`](docs/disaster_recovery.md) — backup & restore procedures
- [`docs/export_guide.md`](docs/export_guide.md) — Gold export + manifest workflow
- [`docs/pipeline_performance_metrics.md`](docs/pipeline_performance_metrics.md) — 2026-08-04 metrics report
- [`docs/figures/`](docs/figures/) — 12 performance charts (regenerate: `python scripts/generate_performance_figures.py`)