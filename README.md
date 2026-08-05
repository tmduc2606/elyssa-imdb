<div align="center">

# Codename: Elyssa — IMDb Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](docs/SMOKE_TEST.md)
[![Docker](https://img.shields.io/badge/Docker-24%2B-blue.svg)](docker/docker-compose.yml)
[![Airflow](https://img.shields.io/badge/Airflow-Orchestration-orange.svg)](data-engineering/README.md)

**End-to-end IMDb analytics: Bronze→Silver→Gold (DE) · ML models (DS) · Web app (API + Frontend)**

</div>

## Overview

Elyssa is a full-stack IMDb intelligence platform: a medallion data warehouse built from IMDb `.tsv.gz`
exports, a multi-modal ML pipeline (genre classification + rating regression + recommendation), and a
GraphQL/REST web application with a React 19 SPA — all containerised and orchestrated with Airflow.

- **Data Engineering** — DuckDB + PostgreSQL + dbt star-schema marts (212 M → 355 M → 241 M rows)
- **Data Science** — GMU/BiLSTM genre, CatBoost rating, SVD/NCF recommender, MLflow registry
- **Web Application** — FastAPI + Strawberry GraphQL + React 19 (JWT auth, search, watchlist, predictions)
- **MLOps** — Docker Compose, MLflow, Prometheus/Grafana monitoring, Terraform IaC

## Architecture

```
IMDb .tsv.gz
      ↓
┌───────────────────────────── Data Engineering ────────────────────────────┐
│  RustFS S3 ─▶ Bronze (DuckDB) ─▶ Silver (PostgreSQL) ─▶ Gold (dbt)      │
│  └─ Airflow DAG: sensor → ingest → transform → dbt → export → freshness   │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 ↓  Gold Parquet (marts/gold/)
┌───────────────────────────── Data Science ────────────────────────────────┐
│  EDA → Feature Engineering → Modeling (GMU / CatBoost / SVD·NCF)         │
│  └─ Quality gates → MLflow registry → inference artifacts                 │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 ↓  MLflow + artifacts
┌───────────────────────────── Web Application ─────────────────────────────┐
│  FastAPI (GraphQL + REST + Auth) → DuckDB views + Model serving           │
│  └─ React 19 SPA: search, browse, title/person detail, predictions        │
└────────────────────────────────┬──────────────────────────────────────────┘
                                 ↓
                            Browser (SPA)
```

Every DE layer reads/writes through **RustFS** (S3-compatible object store on `localhost:9100/9101`);
Gold output lands on the host bind mount `data-science/marts/gold/` (6 Snappy Parquet marts ≈ 5.7 GB).

## Quick Start

| Path | Time | What You Get |
|------|------|--------------|
| [Smoke Test](docs/SMOKE_TEST.md) | 30 min | Pre-packaged sample data, all modules operational, no Docker |
| [Full Runbook](docs/RUNBOOK.md) | ~3 days | Full IMDb pipeline → trained models → running web app |

Full sequential flow (each step delegates to its module runbook):

| # | Stage | Est. Time | Module | Output |
|---|-------|-----------|--------|--------|
| 1 | Data Engineering | ~7.5 h | [README](data-engineering/README.md) | 6 Gold Parquet marts ≈ 5.7 GB |
| 2 | Data Science | 3–4 h | [README](data-science/README.md) | Trained models + inference artifacts |
| 3 | Web Application | ~15 min | [README](web-application/README.md) | API :8000 + SPA :5173 |
| 4 | MLOps (optional) | — | [README](mlops/README.md) | MLflow, monitoring, retraining |

## Docker Stacks

Independent compose stacks sized for 16 GB RAM — run only what you need:

| Stack | Compose File | Services | Est. RAM |
|-------|-------------|----------|----------|
| DE Infra + Orchestration | `docker/docker-compose.yml` | postgres, rustfs, etl-runner, airflow | ~8 GB |
| Web Application | `docker-compose.yml` (root) | api, redis | ~1 GB |
| MLOps | `mlops/docker-compose.yml` | mlflow, prometheus, grafana, exporters + 6 more | ~2–3 GB |

## Module READMEs

| Module | Directory | README | Focus |
|--------|-----------|--------|-------|
| Data Engineering | `data-engineering/` | [README](data-engineering/README.md) | Pipeline, Airflow DAG, dbt, DQ, performance |
| Data Science | `data-science/` | [README](data-science/README.md) | ML pipeline, model zoo, quality gates |
| Web Application | `web-application/` | [README](web-application/README.md) | API, GraphQL, React SPA, endpoints |
| MLOps | `mlops/` | [README](mlops/README.md) | Docker Compose, MLflow, monitoring |

## Repository Structure

```
elyssa-imdb/
├── data-engineering/    # Bronze/Silver/Gold pipeline, Airflow DAG, dbt, DQ, performance figures
├── data-science/        # EDA → features → models → analytics; contracts; notebook pipeline
├── web-application/     # api/ (FastAPI) + client/ (React 19 SPA); frozen API contracts
├── mlops/               # docker-compose, Dockerfiles, monitoring, runbooks, checklists
├── docs/                # RUNBOOK, SMOKE_TEST, QA catalog (58 checks), improvement plan
├── docker/              # DE Dockerfiles + compose stack
├── docker-compose.yml   # Web app stack (api, redis)
└── Makefile             # Build targets (DE / web)
```

## Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores (AMD Athlon 200GE) | 4+ cores |
| RAM | 16 GB physical (13.9 usable) | 32 GB |
| Disk | **≥ 150 GB free** | 512 GB SSD |
| Docker | 24+ with Compose plugin | 24+ |

**Reality hiccups:**
- **Memory consumption:** the WSL2 VM is hard-capped at 9 GB (`.wslconfig`); DE container caps sum to
6.76 GB. On a 16 GB laptop the host runs at **85–95% RAM for most of a full pipeline run**
(Bronze/download ~88%, Silver ETL peak 93–98%, Gold declines to ~91%) because Docker Desktop, the
IDE, and coding agents share the rest. Close heavy apps during full runs; tuning history is
documented in `%USERPROFILE%\.wslconfig` comments (R5/R6).
- **Disk usage:** a full run's post-trigger footprint is **> 140 GB**, dominated by the
**97 GB PostgreSQL volume** (Silver 51 GB + Gold 38 GB) inside Docker, not the repo (~13 GB of
Parquet marts). Disk analyzers can make Docker appear to use **2–3× more** than reality — see
[FAQ: "My disk is near OOM..."](#faq).

## Pipeline Performance

Validated end-to-end run `2026-08-04` on an AMD Athlon 200GE (13.9 GB RAM): **18/18 tasks success**,
**7 h 22 m** total, quality gates passed (7/7 DQ, 43 dbt tests 37P/6W/0E). Full breakdown and charts:
[`data-engineering/docs/pipeline_performance_metrics.md`](data-engineering/docs/pipeline_performance_metrics.md).

| Phase | Duration | Rows Out |
|-------|----------|----------|
| Bronze (ingestion) | 12 s | 212 M |
| Silver (ETL + export) | 20 m | 355 M |
| Gold (dbt run) | 2 h 59 m | 241 M |
| Gold (test + DQ + freshness) | ~1 h 3 m | — |
| Gold (export) | 19 m | 5.7 GB Parquet |

Host RAM during a full run: ~88% at Bronze/download, **93–98% at Silver peak**, ~91% at Gold —
see [Hardware Requirements](#hardware-requirements) and `data-engineering/README.md` for details.

## FAQ

_Very important before debugging/running on your own repository._

### My disk is near OOM, which later a disk analyzer shows Docker using 100–130 GB (2–3× the real data)

**That's expected, and the analyzer is "right" about the files — not about your real usage.** Docker
Desktop on Windows stores the entire WSL2 backend (PostgreSQL data, RustFS S3 objects, images,
build cache, container layers) inside a few large **virtual disks** (`*.vhdx`):

```
C:\Users\Admin\AppData\Local\Docker\wsl\disk\docker_data.vhdx   ← all Docker volumes + images
C:\Users\Admin\AppData\Local\Docker\wsl\main\ext4.vhdx          ← WSL2 main filesystem
```

These files **grow as you use Docker but never shrink on their own** — deleted data leaves empty
space inside the `.vhdx`, so the analyzer counts the file's full (sparse) size, making Docker appear
to consume **2–3×** its actual data. Example: the pipeline's real data is ~130 GB (97 GB PostgreSQL +
13 GB marts + sources + images), but the analyzer can report 250+ GB.

**Solution — compact the virtual disks (safe, no data loss):**

1. Stop the pipeline and Docker Desktop
2. Open **CMD** (as admin) and run:

```bat
diskpart
select vdisk file="C:\Users\Admin\AppData\Local\Docker\wsl\disk\docker_data.vhdx"
compact vdisk
select vdisk file="C:\Users\Admin\AppData\Local\Docker\wsl\main\ext4.vhdx"
compact vdisk
exit
```

3. Restart Docker Desktop. Empty space inside both disks is returned to the host.

> Reclaim even more: `docker system prune -a` (images/build cache) and, after a full run,
> `docker compose -f docker/docker-compose.yml down -v` (deletes the 97 GB PostgreSQL volume —
> Gold Parquet marts on the host bind mount survive).

### Do I have to re-run the whole pipeline if a stage fails? (DE)

No — every layer writes completion markers (`.completed` / `.export.completed`), so a rerun skips
completed stages and resumes from the failure point. Bronze skips already-ingested tables, Silver
skips ETL when its marker exists, Gold always full-refreshes (idempotent), and export resumes per
table. Details in `data-engineering/README.md`.

### The trained models aren't in the repository — where are they? (DS)

Model binaries (`.pt/.cbm/.joblib/.pkl`, 100–360 MB each) are intentionally gitignored — they are
**regenerated** by the DS pipeline from the Gold marts. Run
`python scripts/run_pipeline.py --stage all` (or the 4 notebooks in order) to reproduce them;
`notebooks/models/shared/model_inventory.json` documents every artifact. Results are verified
against the quality gates (RMSE ≤ 0.55, Macro F1 > 0.60).

### Does the API need the ML models to start? (WA)

No — inference degrades gracefully. The API serves search/browse/detail from the 6 Gold Parquet
marts (loaded into DuckDB at startup, ~30 s for 5.7 GB); `/predict/*` endpoints return a clear
error only if the DS artifacts are absent. The full experience needs `data-science/marts/processed/`
produced by the DS pipeline.

### Why does my WSL2 VM swallow so much RAM even when idle? (Docker)

WSL2 caches freed file pages instead of returning them, and Docker Desktop never gives memory back
until you restart. `wsl --shutdown` (then restart Docker Desktop) resets the VM to its 9 GB cap.
The cap itself lives in `%USERPROFILE%\.wslconfig` (`[wsl2] memory=9GB`, `swap=4GB`).

## Documentation

| Document | Description |
|----------|-------------|
| [RUNBOOK.md](docs/RUNBOOK.md) | Sequential 3-day execution guide |
| [SMOKE_TEST.md](docs/SMOKE_TEST.md) | 30-minute smoke test with sample data |
| [QA Catalog](docs/qa_catalog_template.md) | 58-check reusable validation checklist |
| [Improvement Plan](docs/plug_and_play_improvement_plan.md) | Master improvement plan (17 gaps) |
| [Changelog](CHANGELOG.md) | Project milestones (2026-06 → 2026-08) |
| [FAQ](#faq) | Disk/RAM troubleshooting (Docker WSL2 vhdx compaction, host memory) |

## Contributing

1. Fork and clone the repository
2. Run the [smoke test](docs/SMOKE_TEST.md) to verify the environment
3. Make changes in the relevant module and run its quality gates
4. Cross-module changes go through the frozen contracts in `data-science/contracts/` and `web-application/contracts/`
5. Open a pull request describing the change and affected modules

## License

MIT License — see [LICENSE](LICENSE).
