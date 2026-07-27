# Codename: Elyssa — IMDb Intelligence Platform

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

End-to-end IMDb analytics platform: **Bronze→Silver→Gold data pipeline** (DE) → **ML models** (DS) → **Web application** (API + frontend).

---

## System Architecture

```
IMDb .tsv.gz
      ↓
┌─────────────────────────────────────────────────────────────────────┐
│ Data Engineering  (data-engineering/)                                │
│  Bronze (DuckDB) → Silver (PostgreSQL) → Gold (dbt) → Parquet    │
│  └─ Airflow DAG: sensor → ingest → transform → dbt → export       │
└────────────────────────┬────────────────────────────────────────────┘
                         ↓  Gold Parquet marts (marts/full/)
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

---

## Quick Start

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
| 1 | Data Engineering | 5–6 h | `marts/full/*.parquet` (6 Gold tables) |
| 2 | Data Science | 3–4 h | `marts/processed/*` (trained models + artifacts) |
| 3 | Web Application | 15 min | API :8000 |

## Docker Stacks

The project is split into independent compose stacks to fit 16 GB RAM:

| Stack | Compose File | Services | Est. RAM |
|-------|-------------|----------|----------|
| **DE Infra + Orchestration** | `docker/docker-compose.yml` | postgres, neo4j, rustfs, airflow, etl-runner | ~5-7 GB |
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

---

## Module READMEs — Distinctive per Directory

Each module has its own complete README with module-specific quick starts, architecture, and references:

| Module | Directory | README | Focus |
|--------|-----------|--------|-------|
| **Data Engineering** | `data-engineering/` | [README](data-engineering/README.md) | Bronze→Silver→Gold pipeline, Airflow DAG, dbt, DQ checks |
| **Data Science** | `data-science/` | [README](data-science/README.md) | ML pipeline, feature engineering, model training, quality gates |
| **Web Application** | `web-application/` | [README](web-application/README.md) | FastAPI + GraphQL API, React SPA, endpoints, testing |
| **MLOps** | `mlops/` | [README](mlops/README.md) | Docker Compose, MLflow, monitoring, IaC |

---

## Cross-Module Contracts

```
DE (Gold Parquet) ──gold-to-ds.md──▶ DS (feature engineering + modeling)
DE (Gold Parquet) ─gold-to-api.md──▶ Web (API data sources)
DS (MLflow) ────────ds-to-web.md──▶ Web (ML model serving)
Web (API) ─────api-to-frontend.md──▶ Frontend (React SPA)
```

Each contract is version-controlled in the consumer module's `contracts/` directory.

---

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
│   └── marts/            Gold Parquet (full/) + ML artifacts (processed/)
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
│   └── docker-compose.yml  DE Infra + Orchestration (postgres, neo4j, rustfs, airflow, etl-runner)
├── docker-compose.yml    # Web Application stack (api, redis) — separate from DE infra
├── Makefile              # Build targets (DE: -f docker/docker-compose.yml, Web: default)
├── .env.example          # Environment variable reference
└── AGENTS.md             # Root agent orchestration entry point
```

---

## Service URLs

| Service | URL | Credentials |
|---------|-----|-------------|
| Airflow | http://localhost:8081 | `admin` / generated password |
| PostgreSQL | `localhost:54321` | `elyssa` / `elyssa_pg_2026` |
| RustFS Console | http://localhost:9101 | `elyssa` / `elyssa_s3_2026` |
| API | http://localhost:8000 | — |
| Frontend | http://localhost:5173 | — |
| MLflow | http://localhost:5000 | — |
| Grafana | http://localhost:3000 | `admin` / `admin` |

---

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

---

## Pipeline Performance

| Stage | Duration (Full IMDb) |
|-------|---------------------|
| Bronze Ingestion | ~47 min |
| Silver ETL | ~3h 39min |
| Gold dbt Run + Test | ~70 min |
| Gold Export | ~15 min |
| **DE Total** | **~5h 36min** |
| DS Pipeline | ~3–4 hours |
| Web API startup | ~30 s |

---

## Documentation

| Document | Description |
|----------|-------------|
| [RUNBOOK.md](docs/RUNBOOK.md) | Sequential 3-day execution guide |
| [SMOKE_TEST.md](docs/SMOKE_TEST.md) | 30-minute smoke test with sample data |
| [QA Catalog](docs/qa_catalog_template.md) | 58-check reusable validation checklist |
| [Improvement Plan](docs/plug_and_play_improvement_plan.md) | Master improvement plan (17 gaps) |
| `data-engineering/docs/` | DE schema dictionary, architecture, DR, DQ tests |
| `data-science/docs/` | DS implementation plan, API docs, assessment reports |
| `mlops/checklists/` | MLOPS.1–15 audit sheets |

---

## License

MIT License — see [LICENSE](LICENSE).
