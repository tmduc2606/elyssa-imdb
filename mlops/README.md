# Elyssa MLOps — Unified Infrastructure Layer

Wires Data Engineering, Data Science, and Web Application into a single containerised, continuously maintained system.

## Quick Start

```bash
# Full local environment
docker compose -f mlops/docker-compose.yml up -d

# Verify services
curl http://localhost:8000/health      # API
curl http://localhost:5000              # MLflow
curl http://localhost:9090              # Prometheus
curl http://localhost:3000              # Grafana
```

## Directory Structure

```
mlops/
├── README.md                    ← You are here
├── docs/implementation-plan.md  ← Detailed implementation plan
├── docker-compose.yml           ← Full dev environment
├── docker/                      ← Dockerfiles
├── infra/                       ← Terraform templates
├── airflow/dags/                ← Retraining, drift detection DAGs
├── monitoring/                  ← Prometheus / Grafana config
├── runbooks/                    ← DR and rollback procedures
└── checklists/                  ← MLOPS.1–15 audit sheets
```

## Architecture

```
User → Ingress → FastAPI (GraphQL + REST) → DuckDB / Model Service / Redis
                → Grafana (monitoring)
                → Airflow (scheduling)
                → MLflow (model registry)
```

## Key Capabilities

| Capability                 | Tool              | Criterion |
|---------------------------|-------------------|-----------|
| Reproducible builds       | Docker Compose    | MLOPS.1   |
| Model versioning          | MLflow            | MLOPS.2   |
| Infrastructure as Code    | Terraform         | MLOPS.3   |
| Containerisation          | Docker/K8s        | MLOPS.4   |
| Model serving             | FastAPI           | MLOPS.5   |
| Model governance          | MLflow Registry   | MLOPS.6   |
| Monitoring                | Prometheus/Grafana| MLOPS.7   |
| Alerting                  | Alertmanager      | MLOPS.8   |
| Data freshness            | Airflow           | MLOPS.9   |
| Observability             | Structured logs   | MLOPS.10  |
| Security                  | Trivy, non-root   | MLOPS.11  |
| Compliance                | RBAC, encryption  | MLOPS.12  |
| Documentation             | This README       | MLOPS.13  |
| Disaster recovery         | Runbooks          | MLOPS.14  |
| Continuous improvement    | Quarterly review  | MLOPS.15  |

---

## Wiring to Other Modules

| Module | Integration Point | Port | Status |
|--------|------------------|------|--------|
| Data Engineering | Airflow DAG monitoring | Prometheus :9090 | ✅ |
| Data Science | MLflow model registry | MLflow :5000 | ✅ |
| Web Application | API metrics, Grafana dashboards | Grafana :3000 | ✅ |

## Quick Start with Sample Data

```bash
# Ensure MLflow can see DS artifacts
docker compose -f mlops/docker-compose.yml up -d
```
