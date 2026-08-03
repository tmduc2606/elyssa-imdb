<div align="center">

# Elyssa MLOps — Unified Infrastructure Layer

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](docs/SMOKE_TEST.md)
[![MLflow](https://img.shields.io/badge/MLflow-Model%20Registry-red.svg)](mlops/docker-compose.yml)
[![Prometheus](https://img.shields.io/badge/Prometheus-Monitoring-orange.svg)](mlops/monitoring)
[![Grafana](https://img.shields.io/badge/Grafana-Dashboards-F46737.svg)](mlops/monitoring)
[![Terraform](https://img.shields.io/badge/Terraform-IaC-7B42BC.svg)](mlops/infra)

</div>

## Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Capabilities Matrix](#capabilities-matrix)
- [Quick Start](#quick-start)
- [Directory Structure](#directory-structure)
- [Wiring to Other Modules](#wiring-to-other-modules)
- [Runbooks Index](#runbooks-index)

## Overview

Wires Data Engineering, Data Science, and Web Application into a single containerised, continuously maintained system.

## Architecture

```
User → Ingress → FastAPI (GraphQL + REST) → DuckDB / Model Service / Redis
                 → Grafana (monitoring)
                 → Airflow (scheduling)
                 → MLflow (model registry)
```

## Capabilities Matrix

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

### Quick Start with Sample Data

```bash
# Ensure MLflow can see DS artifacts
docker compose -f mlops/docker-compose.yml up -d
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

## Wiring to Other Modules

| Module | Integration Point | Port | Status |
|--------|------------------|------|--------|
| Data Engineering | Airflow DAG monitoring | Prometheus :9090 | ✅ |
| Data Science | MLflow model registry | MLflow :5000 | ✅ |
| Web Application | API metrics, Grafana dashboards | Grafana :3000 | ✅ |

## Runbooks Index

| Runbook | Path | Purpose |
|---------|------|---------|
| Quarterly Drill | `runbooks/quarterly-drill.md` | Regularly exercise DR procedures to ensure readiness. Scheduled first Saturday of each quarter, 10:00 AM UTC; 30–60 min. |
| Model Rollback | `runbooks/model-rollback.md` | Revert model deployment to a previous production version when current model exhibits degraded performance. Triggers: error rate spike > 1%, P95 latency increase > 2x baseline, drift alert KL divergence > 0.2. |
| Node Failure | `runbooks/node-failure.md` | Respond to Kubernetes node or Docker host failure. RTO target: 15 minutes (full recovery). |
| Database Restore | `runbooks/database-restore.md` | Restore PostgreSQL database from backup after data corruption or loss. RPO: 24 hours, RTO: 1 hour. |
