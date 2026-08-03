<div align="center">

# Codename: Elyssa — IMDb Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](docs/SMOKE_TEST.md)
[![Docker](https://img.shields.io/badge/Docker-24%2B-blue.svg)](docker/docker-compose.yml)
[![Airflow](https://img.shields.io/badge/Airflow-Orchestration-orange.svg)](data-engineering/README.md)

**End-to-end IMDb analytics: Bronze→Silver→Gold (DE) → ML (DS) → Web (API + Frontend)**

</div>

## News

- [2026-07] 🚀 Elyssa IMDb platform launched — Bronze→Silver→Gold → ML → Web
- [2026-07] 📊 Tier-3 memory optimization (M1–M10) applied — OOM crash resolved
- [2026-07] 🧪 Smoke test validated — 30-minute zero-Docker walkthrough available at [SMOKE_TEST.md](docs/SMOKE_TEST.md)

## Contents

- [Architecture](#architecture)
- [Install](#install)
- [Docker Stacks](#docker-stacks)
- [Module READMEs](#module-readmes)
- [Repository Structure](#repository-structure)
- [Service URLs](#service-urls)
- [Hardware Requirements](#hardware-requirements)
- [Pipeline Performance](#pipeline-performance)
- [Documentation](#documentation)
- [Contributing](#contributing)
- [License](#license)

## Architecture

```
IMDb .tsv.gz
      ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Data Engineering  (data-engineering/)                                │
│  Bronze (DuckDB) → Silver (PostgreSQL) → Gold (dbt) → Parquet    │
│  └─ Airflow DAG: sensor → ingest → transform → dbt → export       │
└────────────────────────┬────────────────────────────────────────────┘
                         ↓  Gold Parquet marts (marts/gold/)
┌─────────────────────────────────────────────────────────────────────┐
│ Data Science      (data-science/)                                   │
│  Features → GMU (genre) → CatBoost (rating) → Inference pipeline  │
│  └─ Pipeline: eda → features → models → analytics → artifacts     │
└────────────────────────┬────────────────────────────────────────────┘
                         ↓  Trained models (marts/processed/)
┌─────────────────────────────────────────────────────────────────────┐
│ Web Application   (web-application/)                                │
│  FastAPI + GraphQL → DuckDB views → React SPA                      │
│  └─ Auth, search, browse, title/person detail, predictions         │
└────────────────────────┬────────────────────────────────────────────┘
                         ↓  HTML/JSON
                    Browser (React SPA)
```

## Install

| Time | Path | What You Get |
|------|------|-------------|
| 30 min | [Smoke test](docs/SMOKE_TEST.md) | Pre-packaged sample data → all modules operational |
| 3 days | [Full runbook](docs/RUNBOOK.md) | Full IMDb pipeline → trained models → web app |

### Smoke Test
```powershell
docs\SMOKE_TEST.md    # 30-minute walkthrough (no Docker needed)
```

### Full Pipeline (3 days, sequential)
| Day | Phase | Est. Time | Output |
|-----|-------|-----------|--------|
| 1 | Data Engineering | ~9 h active (see [Pipeline Performance](#pipeline-performance)) | `marts/gold/*.parquet` (6 Gold tables ≈ 5.5 GB) |
| 2 | Data Science | 3–4 h | `marts/processed/*` (trained models + artifacts) |
| 3 | Web Application | 15 min | API :8000 |

## Docker Stacks

The project is split into independent compose stacks to fit 16 GB RAM:

| Stack | Compose File | Services | Est. RAM |
|-------|-------------|----------|----------|
| **DE Infra + Orchestration** | `docker/docker-compose.yml` | postgres, rustfs, etl-runner, airflow | ~8 GB |
| **Web Application** | `docker-compose.yml` (root) | api, redis | ~1 GB |
| **MLOps** | `mlops/docker-compose.yml` | mlflow, prometheus, grafana + exporters | ~2-3 GB |

Each service has `mem_limit` + reduced runtime configs. Run only what you need:
```powershell
# DE pipeline work
docker compose -f docker/docker-compose.yml up -d

# Web app only (requires existing marts)
docker compose up -d

# Both together if RAM permits
docker compose -f docker/docker-compose.yml up -d && docker compose up -d
```

## Module READMEs

Each module has its own complete README with module-specific quick starts, architecture, and references:

| Module | Directory | README | Focus |
|--------|-----------|--------|-------|
| **Data Engineering** | `data-engineering/` | [README](data-engineering/README.md) | Bronze→Silver→Gold pipeline, Airflow DAG, dbt, DQ checks |
| **Data Science** | `data-science/` | [README](data-science/README.md) | ML pipeline, feature engineering, model training, quality gates |
| **Web Application** | `web-application/` | [README](web-application/README.md) | FastAPI + GraphQL API, React SPA, endpoints, testing |
| **MLOps** | `mlops/` | [README](mlops/README.md) | Docker Compose, MLflow, monitoring, IaC |

## Repository Structure

```
elyssa-imdb/
├── data-engineering/     # DE pipeline — Bronze, Silver, Gold, Airflow, dbt, DQ
│   ├── bronze/           DuckDB ingestion scripts
│   ├── silver/           PySpark ETL + SCD2 transforms
│   ├── gold/             dbt star-schema models
│   └── orchestration/    Airflow DAGs + custom operators
├── data-science/         # DS pipeline — EDA, features, models, evaluation
│   ├── src/              Importable Python modules (loader, features, models, eval, inference)
│   ├── scripts/          Pipeline runner, contract validation, sample data generator
│   ├── notebooks/        Exploratory notebooks (EDA, FE, Modeling, Analytics)
│   └── marts/            Gold Parquet (gold/) + ML artifacts (processed/)
├── web-application/      # Web layer — API gateway + React SPA
│   ├── api/              FastAPI + GraphQL backend
│   └── client/           React 19 SPA (Vite, TypeScript, Tailwind)
├── mlops/                # MLOps infrastructure
│   ├── docker-compose.yml  MLflow, Prometheus, Grafana
│   ├── monitoring/       Prometheus rules + Grafana dashboards
│   └── infra/            Terraform templates
├── docs/                 # Cross-module documentation
│   ├── RUNBOOK.md        3-day sequential execution guide
│   ├── SMOKE_TEST.md     30-minute smoke test
│   ├── qa_catalog_template.md  58-check QA checklist
│   └── plug_and_play_improvement_plan.md  Master improvement plan
├── docker/               # DE Dockerfiles + DE compose stack
│   └── docker-compose.yml  DE pipeline (postgres, rustfs, etl-runner, airflow)
├── docker-compose.yml    # Web Application stack (api, redis) — separate from DE infra
├── Makefile              # Build targets (DE: -f docker/docker-compose.yml, Web: default)
├── .env.example          # Environment variable reference
└── AGENTS.md             # Root agent orchestration entry point
```

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:18081 | `admin` / generated password |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| RustFS S3 Console | http://localhost:9101 | — |
| API | http://localhost:8000 | — |
| Frontend | http://localhost:5173 | — |
| MLflow | http://localhost:5000 | — |
| Grafana | http://localhost:3000 | `admin` / `admin` |

## Hardware Requirements

| Resource | Minimum | Recommended |
|----------|---------|-------------|
| CPU | 2 cores (AMD Athlon 200GE) | 4+ cores |
| RAM | 16 GB | 32 GB |
| Disk | 20 GB free | 50 GB SSD |
| Docker | 24+ with compose plugin | 24+ |

All containers have explicit `mem_limit` to prevent resource starvation.
Run only the stack you need — see [Docker Stacks](#docker-stacks) above.
Build sequentially (`docker compose build --no-cache <service>`) to avoid
memory pressure during image compilation on constrained hosts.

## Pipeline Performance

Measured on the final Phase 1 run (`manual_20260731160437`). That run doubled as the recovery
vehicle for hotfixes, so wall-clock (~23 h including retries, sensor waits, and an overnight gap)
is **not** representative — the table below shows per-layer active time. See
[`data-engineering/docs/final_pipeline_summary.md`](data-engineering/docs/final_pipeline_summary.md) for the full post-mortem.

| Stage | Duration (Full IMDb, measured) |
|-------|---------------------|
| Bronze Ingestion | ~20 min (7 tables, 212 M rows) |
| Silver ETL | ~5 h 04 min |
| Silver Export | ~41 min (14 tables) |
| Gold dbt Run | ~1 h 55 min (12 models) |
| Gold dbt Test | ~18 min (39 tests; 43 with grain tests ≈ 70 min) |
| Gold Export | ~31 min (6 tables ≈ 5.5 GB) |
| **DE active total** | **~9 h** |
| DS Pipeline | ~3–4 hours |
| Web API startup | ~30 s |

## Documentation

| Document | Description |
|----------|-------------|
| [RUNBOOK.md](docs/RUNBOOK.md) | Sequential 3-day execution guide |
| [SMOKE_TEST.md](docs/SMOKE_TEST.md) | 30-minute smoke test with sample data |
| [QA Catalog](docs/qa_catalog_template.md) | 58-check reusable validation checklist |
| [Improvement Plan](docs/plug_and_play_improvement_plan.md) | Master improvement plan (17 gaps) |
| [DE Final Summary](data-engineering/docs/final_pipeline_summary.md) | Phase 1 post-mortem — layer timings, 27-commit hotfix log, cleanup record |
| `data-engineering/docs/` | DE schema dictionary, architecture, export guide, DR |
| `data-science/docs/` | DS implementation plan, API docs, assessment reports |
| `mlops/checklists/` | MLOPS.1–15 audit sheets |

## Contributing

1. Fork and clone the repository
2. Run the [smoke test](docs/SMOKE_TEST.md) to verify the environment
3. Make changes in the relevant module (`data-engineering/`, `data-science/`, `web-application/`, or `mlops/`)
4. Open a pull request with a description of the change and affected modules

## License

MIT License — see [LICENSE](LICENSE).
