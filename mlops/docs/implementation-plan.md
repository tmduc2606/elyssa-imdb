# Phase 6 MLOps Infrastructure — Detailed Implementation Plan

**Document Purpose:** Comprehensive, actionable guide wiring all Elyssa modules (DE, DS, Web) into a unified, containerised, continuously maintained system fulfilling MLOps criteria from the Codename: Elyssa proposal.

**Target Audience:** All Elyssa agents (DE, DS, SWE) and future maintainers.

**Outcome:** A single packagable project deployable on any Docker/Kubernetes environment with full CI/CD, monitoring, and disaster recovery.

---

## 1. Introduction & Architecture

### 1.1 System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        External Users                          │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTPS :443
                            ▼
┌──────────────────────────────────────────────────────────────────┐
│                    Ingress / Load Balancer                       │
│                 (nginx-ingress / AWS ALB)                        │
└──┬───────────┬───────────┬──────────────┬───────────────────────┘
   │           │           │              │
   ▼           ▼           ▼              ▼
┌──────┐ ┌──────────┐ ┌────────┐ ┌──────────────┐
│React │ │FastAPI   │ │Grafana │ │   Airflow    │
│SPA   │ │GraphQL   │ │Dashbrd │ │   Webserver  │
│:3000 │ │:8000     │ │:3000   │ │   :8080      │
└──┬───┘ └──┬───────┘ └───┬────┘ └──────┬───────┘
   │        │             │             │
   └────────┼─────────────┼─────────────┘
            │             │             │
            ▼             ▼             ▼
      ┌──────────┐ ┌──────────┐ ┌──────────────┐
      │  Redis   │ │ DuckDB   │ │   MLflow     │
      │  Cache   │ │ Parquet  │ │  Tracking    │
      │  :6379   │ │ Queries  │ │  :5000       │
      └──────────┘ └──────────┘ └──────────────┘
            │             │
            ▼             ▼
      ┌─────────────────────────────────────┐
      │       Bronze / Silver Storage       │
      │  (RustFS S3 — Port 9000)            │
      │  (PostgreSQL — Port 5432)           │
      └─────────────────────────────────────┘
```

### 1.2 Technology Stack (July 2026)

| Component           | Technology                    | Version      |
|--------------------|-------------------------------|--------------|
| API Framework      | FastAPI                       | >=0.115.0    |
| GraphQL            | Strawberry GraphQL            | >=0.256.0    |
| Frontend           | React + Vite + TypeScript     | 19 / 6 / 5   |
| Analytics Engine   | DuckDB                        | >=1.1.0      |
| Model Serving      | PyTorch + CatBoost + sklearn  | 2.13 / 1.2 / 1.8 |
| Orchestration      | Apache Airflow                | 2.x          |
| ML Tracking        | MLflow                        | 2.x          |
| Monitoring         | Prometheus + Grafana          | latest       |
| Logging            | Loki / ELK Stack              | latest       |
| Caching            | Redis 7                       | 7-alpine     |
| Container Runtime  | Docker + Docker Compose       | latest       |
| Orchestration (K8s)| Kubernetes (for staging/prod) | 1.28+        |
| IaC                | Terraform / OpenTofu          | 1.x          |
| CI/CD              | GitHub Actions                | —            |

### 1.3 Repository Layout

```
elyssa-imdb/
├── data-engineering/         # Bronze/Silver/Gold pipelines (Phase 1)
├── data-science/             # ML notebooks, artifacts (Phase 2)
├── web-application/          # FastAPI + React SPA (Phase 3-4)
│   ├── api/                  # Backend
│   └── client/               # Frontend
├── docker/                   # DE Dockerfiles (postgres, neo4j, etc.)
├── docs/                     # Project documentation
├── mlops/                    # ← MLOps layer (Phase 6)
│   ├── README.md             # Master MLOps documentation
│   ├── docs/                 # Detailed plans
│   ├── docker-compose.yml    # Full-stack dev environment
│   ├── infra/                # Terraform templates
│   ├── airflow/dags/         # Retraining, drift detection DAGs
│   ├── monitoring/           # Prometheus rules, Grafana dashboards
│   ├── runbooks/             # DR and rollback procedures
│   └── checklists/           # MLOPS criterion audit sheets
├── docker-compose.yml        # Root compose (legacy, DE-focused)
├── Makefile
└── README.md
```

### 1.4 Environment Parity

| Environment | Infrastructure | MLflow | Monitoring | Notes                |
|-------------|---------------|--------|------------|----------------------|
| Local Dev   | Docker Compose | Yes    | Basic      | Hot-reload enabled   |
| Staging     | K8s (minikube) | Yes    | Full       | Canary deploys       |
| Production  | K8s (cloud)    | Yes    | Full+Alerts| HPA, PDB, HA config  |

---

## 2. Unified CI/CD Pipeline

### 2.1 GitHub Actions Workflows

**`ci-de.yml`** — Data Engineering
```yaml
name: DE CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install ruff
      - run: ruff check data-engineering/
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d postgres rustfs
      - run: pip install -r data-engineering/requirements.txt
      - run: pytest data-engineering/tests/
```

**`ci-ds.yml`** — Data Science
```yaml
name: DS CI
on: [push, pull_request]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install ruff
      - run: ruff check data-science/
  verify-artifacts:
    runs-on: ubuntu-latest
    steps:
      - run: python -c "
            from joblib import load
            load('data-science/marts/processed/preprocessor.joblib')
            load('data-science/marts/processed/genre_list_mlb.joblib')
            load('data-science/marts/processed/scaler.joblib')
            "
```

**`ci-web.yml`** — Web Application
```yaml
name: Web CI
on: [push, pull_request]
jobs:
  api-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r web-application/api/requirements.txt
      - run: pytest web-application/api/tests/ -q
  frontend-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v4
      - run: npm ci && npm run lint && npm run build
        working-directory: web-application/client
  image-scan:
    uses: ./.github/workflows/trivy-scan.yml
```

**`cd.yml`** — Continuous Deployment
```yaml
name: CD
on:
  push:
    branches: [main]
jobs:
  build-and-push:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose build api
      - run: docker tag elyssa-api ghcr.io/tmduc2606/elyssa-api:${{ github.sha }}
      - run: docker push ghcr.io/tmduc2606/elyssa-api:${{ github.sha }}
```

### 2.2 Blackout Drill Integration

Scheduled nightly via `schedule` trigger:

```yaml
name: Nightly Blackout Drill
on:
  schedule:
    - cron: '0 2 * * *'  # 2 AM UTC daily
jobs:
  surge-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d api redis
      - run: python mlops/drills/surge.py  # 200% data surge
  adversarial-query:
    runs-on: ubuntu-latest
    steps:
      - run: python mlops/drills/adversarial.py  # Malformed requests
  network-latency:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: docker compose up -d api
      - run: python mlops/drills/latency.py  # Simulate 500ms+ latency
```

### 2.3 Release Gates

| Gate         | Criteria                                              | Blocking |
|-------------|-------------------------------------------------------|----------|
| Lint         | Ruff (Python), ESLint (TS) — zero errors              | Yes      |
| Unit Tests   | 100% pass rate                                        | Yes      |
| Integration  | API ↔ DuckDB, API ↔ Model, API ↔ Redis               | Yes      |
| Image Scan   | Trivy: no CRITICAL or HIGH vulnerabilities            | Yes      |
| Contract     | OpenAPI diff against gold-to-api.md, api-to-frontend  | Advisory |
| Performance  | p95 < 500ms, error rate < 0.1%                        | Advisory |

---

## 3. Model Registry & Governance

### 3.1 MLflow Tracking Server

Deployed as a Docker Compose service:

```yaml
mlflow:
  image: ghcr.io/mlflow/mlflow:v2.x
  container_name: elyssa-mlflow
  command: >
    mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri postgresql://elyssa:elyssa_pg_2026@postgres:5432/mlflow
      --default-artifact-root s3://elyssa-mlflow-artifacts/
  ports:
    - "5000:5000"
  depends_on:
    postgres:
      condition: service_healthy
```

### 3.2 Model Registration Workflow

```mermaid
sequenceDiagram
    participant DS as DS Notebook
    participant MLflow
    participant Registry as Model Registry
    participant K8s as K8s Deployment

    DS->>MLflow: log_params(), log_metrics()
    DS->>MLflow: log_model() (PyTorch / CatBoost)
    DS->>Registry: register_model()
    Registry->>Registry: stage = "Staging"
    Note over Registry: Manual approval gate
    Registry->>Registry: stage = "Production"
    K8s->>Registry: fetch latest Production model
    K8s->>K8s: rolling update with canary
```

### 3.3 Stage Transition Rules

| Transition          | Trigger          | Approval Required |
|--------------------|------------------|-------------------|
| None → Staging      | `register_model()` | No               |
| Staging → Production| Manual / CI       | Yes (GitHub PR)   |
| Production → Archived| Manual           | Yes               |
| Production → Staging| Rollback (auto)   | No                |

### 3.4 Canary Releases

- **Weighted traffic split**: 5% → 25% → 50% → 100%
- **Tooling**: Istio VirtualService or NGINX Plus
- **Duration per stage**: 15 minutes with automatic rollback on error rate spike

```yaml
apiVersion: networking.istio.io/v1beta1
kind: VirtualService
metadata:
  name: elyssa-api-canary
spec:
  hosts:
  - api.elyssa.local
  http:
  - match:
    - headers:
        x-canary: "true"
    route:
    - destination:
        host: elyssa-api-canary
      weight: 5
    - destination:
        host: elyssa-api-stable
      weight: 95
```

---

## 4. Containerisation & Docker Standards

### 4.1 Base Images

| Component    | Base Image              | Final Image Size Target |
|-------------|------------------------|------------------------|
| API          | python:3.13-slim       | < 500 MB               |
| Frontend     | node:20-alpine → nginx:alpine | < 100 MB         |
| Model Server | python:3.13-slim       | < 800 MB (includes torch) |
| Airflow      | apache/airflow:2.x     | < 1 GB                 |

### 4.2 Dockerfiles

**`mlops/docker/Dockerfile.api`** (updated from web-application/api/Dockerfile)
```dockerfile
FROM python:3.13-slim AS builder
WORKDIR /build
COPY web-application/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin
WORKDIR /app
COPY web-application/api/app/ /app/app/
RUN useradd -r -s /bin/false elyssa && chown -R elyssa:elyssa /app
USER elyssa
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --retries=3 CMD curl -f http://localhost:8000/health || exit 1
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

**`mlops/docker/Dockerfile.frontend`**
```dockerfile
FROM node:20-alpine AS builder
WORKDIR /build
COPY web-application/client/package*.json ./
RUN npm ci
COPY web-application/client/ .
RUN npm run build

FROM nginx:alpine
COPY --from=builder /build/dist/ /usr/share/nginx/html/
COPY mlops/docker/nginx.conf /etc/nginx/conf.d/default.conf
RUN adduser -D -H -s /sbin/nologin nginx
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

### 4.3 Version Pinning Policy

- `requirements.txt`: exact versions (`scikit-learn==1.8.0`, `torch==2.13.0`)
- `package.json`: exact versions in `resolutions` field
- Lock files committed: `poetry.lock`, `package-lock.json`
- Docker images: pin major-minor (`python:3.13-slim`, `node:20-alpine`)

### 4.4 Security Standards

| Requirement          | Implementation                                    |
|---------------------|----------------------------------------------------|
| Non-root user        | `USER elyssa` in Dockerfiles                       |
| No shell in prod     | Distroless or slim images                          |
| Vulnerability scan   | Trivy in CI (fail on CRITICAL)                     |
| Secrets              | Docker secrets / K8s secrets, never in images      |
| Image signing        | cosign on production images                        |

---

## 5. Infrastructure-as-Code

### 5.1 Terraform Module Structure

```
mlops/infra/
├── backend.tf                  # S3 state backend + provider config
├── envs/
│   ├── dev/
│   │   ├── main.tf             # Module calls (dev config)
│   │   ├── variables.tf        # Input variables
│   │   └── outputs.tf          # Output values
│   ├── staging/
│   │   ├── main.tf
│   │   ├── variables.tf
│   │   └── outputs.tf
│   └── prod/
│       ├── main.tf
│       ├── variables.tf
│       └── outputs.tf
├── modules/
│   ├── compute/
│   │   ├── main.tf             # ECS cluster, task definitions, services
│   │   ├── variables.tf        # environment, instance_type, desired_count, vpc_id, subnet_ids
│   │   └── outputs.tf          # cluster_id, api_dns_name, mlflow_dns_name
│   ├── storage/
│   │   ├── main.tf             # S3 buckets (gold, mlflow, backups)
│   │   ├── variables.tf        # environment, lifecycle_rules_enabled
│   │   └── outputs.tf          # gold_marts_bucket, mlflow_artifacts_bucket, backup_bucket_name
│   ├── networking/
│   │   ├── main.tf             # VPC, subnets, IGW, route tables
│   │   ├── variables.tf        # environment, vpc_cidr
│   │   └── outputs.tf          # vpc_id, public_subnet_ids, private_subnet_ids
│   └── monitoring/
│       ├── main.tf             # CloudWatch log groups, alarms
│       ├── variables.tf        # environment, alerting_enabled
│       └── outputs.tf          # cloudwatch_log_group_*, grafana_dns_name
```

### 5.2 Core Resources (AWS Example)

```hcl
# modules/compute/main.tf
resource "aws_ecs_cluster" "elyssa" {
  name = "elyssa-${var.environment}"
}

resource "aws_ecs_service" "api" {
  name            = "elyssa-api"
  cluster         = aws_ecs_cluster.elyssa.id
  task_definition = aws_ecs_task_definition.api.arn
  desired_count   = var.api_replicas

  load_balancer {
    target_group_arn = var.alb_target_group_arn
    container_name   = "api"
    container_port   = 8000
  }
}

# modules/storage/main.tf
resource "aws_s3_bucket" "gold_marts" {
  bucket = "elyssa-${var.environment}-gold-marts"
  lifecycle_rule {
    enabled = true
    expiration {
      days = 90
    }
  }
}

resource "aws_s3_bucket" "mlflow_artifacts" {
  bucket = "elyssa-${var.environment}-mlflow-artifacts"
}
```

### 5.3 Local Fallback (Docker Compose)

See `mlops/docker-compose.yml` for the full local development environment. All cloud services have a local equivalent:
- S3 → RustFS (MinIO-compatible)
- RDS → PostgreSQL
- ElastiCache → Redis
- ECR → local Docker registry

---

## 6. Model Serving & Inference

### 6.1 Deployment Architecture

```
┌──────────────┐     /api/v1/predict/genre     ┌────────────────────┐
│   FastAPI    │ ──────────────────────────────▶│  GMU Model Service │
│  (integrated)│                                │  (PyTorch)         │
│              │     /api/v1/predict/rating     │                    │
│  :8000       │ ──────────────────────────────▶│  CatBoost Service  │
│              │                                │                    │
│              │     /api/v1/models             │  Recommender       │
│              │ ◀─────────────────────────────│  (surprise/sklearn) │
└──────────────┘                                └────────────────────┘
```

### 6.2 Performance Benchmarks

| Endpoint                  | p50 Latency | p95 Latency | Throughput (req/s) |
|--------------------------|------------|------------|-------------------|
| POST /predict/genre       | 15ms       | 45ms        | 500               |
| POST /predict/rating      | 8ms        | 25ms        | 1000              |
| GET /api/v1/titles        | 50ms       | 150ms       | 200               |
| POST /graphql (homepage)  | 80ms       | 250ms       | 100               |

### 6.3 Auto-scaling (Kubernetes HPA)

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: elyssa-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: elyssa-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
  - type: Resource
    resource:
      name: memory
      target:
        type: Utilization
        averageUtilization: 80
```

---

## 7. Monitoring & Observability

### 7.1 Metrics Exposure

| Component     | Exporter                       | Port  |
|--------------|--------------------------------|-------|
| FastAPI       | prometheus-fastapi-instrumentator | 8000 |
| Airflow      | Built-in Prometheus endpoint   | 8080  |
| MLflow        | Built-in metrics               | 5000  |
| PostgreSQL   | postgres_exporter              | 9187  |
| Redis         | redis_exporter                 | 9121  |
| Node (host)  | node_exporter                  | 9100  |

### 7.2 Grafana Dashboards

**Dashboard: Elyssa Pipeline Overview**
- Panel 1: Airflow DAG status (success/failed by hour)
- Panel 2: API p50/p95/p99 latency (line chart, 6h window)
- Panel 3: Model drift KL divergence (gauge per feature)
- Panel 4: Data freshness (max `snapshot_date` per mart, table)
- Panel 5: Error rate by endpoint (bar chart)
- Panel 6: Redis cache hit ratio (gauge)
- Panel 7: GPU/CPU utilization (for training nodes)

**Dashboard: Model Performance**
- Panel 1: Genre macro F1 over time (MLflow metrics)
- Panel 2: Rating RMSE over time
- Panel 3: Feature distribution drift (histogram overlay)
- Panel 4: Prediction confidence distribution

### 7.3 Structured Logging

```json
{
  "pipeline_name": "imdb_pipeline",
  "stage": "gold_load",
  "batch_id": "20260721_220000",
  "timestamp": "2026-07-21T22:00:00Z",
  "status": "completed",
  "duration_ms": 4500,
  "rows_processed": 12500000,
  "error": null,
  "trace_id": "abc-123-def-456"
}
```

Implementation in FastAPI:
```python
import structlog
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
)
```

### 7.4 Alerting Rules (Prometheus)

```yaml
groups:
  - name: elyssa-alerts
    rules:
      - alert: HighErrorRate
        expr: rate(http_requests_total{status=~"5.*"}[5m]) / rate(http_requests_total[5m]) > 0.01
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "API error rate > 1% for 5 minutes"

      - alert: HighLatency
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "p95 latency > 500ms"

      - alert: AirflowPipelineFailure
        expr: airflow_dag_status{status="failed"} > 0
        for: 2m
        labels:
          severity: critical
        annotations:
          summary: "Airflow DAG {{ $labels.dag_id }} failed"

      - alert: ModelDriftDetected
        expr: model_drift_kl_divergence > 0.1
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Model drift threshold exceeded for feature {{ $labels.feature }}"

      - alert: DataStaleness
        expr: time() - gold_mart_max_snapshot_timestamp_seconds > 86400
        for: 1h
        labels:
          severity: warning
        annotations:
          summary: "Gold mart {{ $labels.mart_name }} not updated in 24+ hours"

      - alert: RedisCacheMissSpike
        expr: rate(redis_cache_miss_total[5m]) / rate(redis_cache_total[5m]) > 0.5
        for: 10m
        labels:
          severity: warning
```

---

## 8. Automated Retraining & Data Freshness

### 8.1 Retraining Airflow DAG

Located at `mlops/airflow/dags/retraining_pipeline.py`:

```python
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.bash import BashOperator

default_args = {
    "owner": "elyssa-mlops",
    "depends_on_past": False,
    "start_date": datetime(2026, 7, 21),
    "retries": 1,
    "retry_delay": timedelta(minutes=5),
}

with DAG(
    "elyssa_retraining_pipeline",
    default_args=default_args,
    schedule_interval="0 6 * * 0",  # Every Sunday 6 AM
    catchup=False,
    tags=["mlops", "retraining"],
) as dag:

    check_freshness = PythonOperator(
        task_id="check_gold_freshness",
        python_callable=lambda: __import__("pathlib").Path("/data/marts/processed/model_inventory.json").stat().st_mtime,
    )

    feature_engineering = BashOperator(
        task_id="run_feature_engineering",
        bash_command="cd /opt/airflow && python data-science/scripts/run_feature_engineering.py",
    )

    train_evaluate = BashOperator(
        task_id="train_and_evaluate",
        bash_command="python data-science/scripts/run_training.py --from-airflow",
    )

    register_mlflow = BashOperator(
        task_id="register_in_mlflow",
        bash_command="python data-science/scripts/register_model.py",
    )

    deploy_canary = PythonOperator(
        task_id="deploy_canary",
        python_callable=lambda: print("Canary deploy triggered"),
    )

    check_freshness >> feature_engineering >> train_evaluate >> register_mlflow >> deploy_canary
```

### 8.2 Drift Detection

```python
# mlops/airflow/dags/drift_detection.py
import numpy as np
from scipy.stats import entropy
from joblib import load

def detect_drift():
    baseline = load("/data/marts/processed/feature_statistics.joblib")
    current = compute_current_statistics("/data/marts/processed/")

    for feature in baseline["columns"]:
        kl_div = entropy(baseline["probs"][feature], current["probs"][feature])
        if kl_div > 0.1:
            send_alert(f"Drift detected for feature {feature}: KL={kl_div:.4f}")
```

### 8.3 Trigger Matrix

| Trigger               | Action                    | Delay      |
|----------------------|---------------------------|------------|
| Weekly cron          | Full retraining pipeline  | Sunday 6AM |
| Drift > 0.1 KL       | Alert + manual approval   | Immediate  |
| New Gold data        | Feature engineering only  | 1 hour     |
| Manual (GitHub PR)   | Full pipeline             | Immediate  |

---

## 9. Disaster Recovery & Rollback

### 9.1 Node Failure Recovery

| Scenario                     | Automated Recovery                                         | RPO   | RTO   |
|------------------------------|-----------------------------------------------------------|-------|-------|
| Single pod crash             | K8s ReplicaSet auto-restart                               | 0     | <30s  |
| Node failure (k8s)           | Pod rescheduled to healthy node                           | 0     | <2m   |
| PostgreSQL crash             | StatefulSet restart + WAL replay                          | <1s   | <5m   |
| Full AZ outage               | Multi-AZ deployment + RDS failover                        | <5m   | <15m  |
| Data corruption              | Point-in-time recovery from backup                        | <24h  | <1h   |

### 9.2 Model Rollback Runbook

```mermaid
flowchart TD
    A[Alert: Model Performance Degraded] --> B{Check MLflow}
    B --> C[Identify previous Production version]
    C --> D[Transition previous version to Production]
    D --> E[Deploy canary with rolled-back model]
    E --> F{Canary OK for 15 min?}
    F -->|Yes| G[Full rollout of rolled-back model]
    F -->|No| H[Escalate to DS team]
    H --> I[Trigger retraining with corrected data]
```

CLI equivalent:
```bash
# Rollback to version 3
mlflow models transition-stage \
  --model-uri "models:/Elyssa_Genre_GMU/3" \
  --stage "Production"
kubectl set image deployment/elyssa-api \
  api=ghcr.io/tmduc2606/elyssa-api:v3-rollback
```

### 9.3 Database Restore

```bash
# List available backups
aws s3 ls s3://elyssa-prod-backups/postgres/

# Restore to point-in-time
pg_restore -h localhost -U elyssa -d elyssa_warehouse \
  --clean --if-exists \
  s3://elyssa-prod-backups/postgres/2026-07-21_220000.dump

# For full PITR (if using WAL archiving):
# 1. Stop the database
# 2. Restore base backup
# 3. Apply WAL files up to desired timestamp
# 4. Start the database
```

### 9.4 Quarterly Drill Procedure

1. Schedule: First Saturday of every quarter, 10 AM UTC
2. Participants: DE, DS, SWE leads
3. Drill scenarios (rotate each quarter):
   - Q1: Full database restore from backup
   - Q2: Model rollback + canary deployment
   - Q3: Kubernetes node failure simulation
   - Q4: Data corruption recovery
4. Post-mortem: Within 48 hours, using this template:

```markdown
## Post-Mortem: Q3 2026 MLOps Drill

**Date:** 2026-10-03
**Scenario:** Kubernetes node failure
**Participants:** [names]

### Timeline
- 10:00 — Drill started
- 10:02 — Node cordoned
- 10:05 — Pods rescheduled
- 10:08 — All services healthy
- 10:15 — Drill ended

### Observations
- API had 45s of degraded performance (missing 1 replica)
- Redis connection pool exhausted briefly

### Action Items
- [ ] Increase Redis max_connections to 200
- [ ] Add pod-disruption-budget for API
- [ ] Review HPA thresholds
```

---

## 10. Security & Compliance

### 10.1 Data Encryption

| Layer          | Mechanism             | Standard   |
|---------------|-----------------------|------------|
| At rest (disk)| LUKS / EBS encryption | AES-256    |
| At rest (S3)  | Server-side encryption| AES-256    |
| In transit    | TLS 1.3               | mTLS for internal services |
| Secrets       | HashiCorp Vault / AWS Secrets Manager | — |

### 10.2 RBAC

| Role          | Kubernetes Access         | Cloud Resources     | MLflow Access      |
|---------------|--------------------------|---------------------|--------------------|
| Admin         | Cluster-admin            | Full                | Full               |
| DE Engineer   | Namespace: elyssa-de     | S3, RDS read/write  | Read-only          |
| DS Engineer   | Namespace: elyssa-ds     | S3 read/write, no RDS| Register models   |
| SWE Engineer  | Namespace: elyssa-swe    | Read-only (S3)      | Read-only          |
| Read-only     | Namespace: elyssa-monitoring | Read-only       | Read-only          |

### 10.3 PII Handling

| Data               | Location               | PII? | Handling                                    |
|--------------------|------------------------|------|---------------------------------------------|
| User email         | SQLite (api/data/)     | Yes  | Hashed, never logged                        |
| User password      | SQLite (bcrypt hash)   | Yes  | One-way hash, never stored plaintext        |
| Watchlist          | SQLite (tconst)        | No   | —                                           |
| Logs               | Loki / ELK             | No   | JSON logging excludes user fields           |

Retention Policies:
- User data: deleted after 1 year of inactivity
- Logs: 90 days (hot), 1 year (cold storage)
- Model artifacts: latest 5 versions kept, older archived to S3 Glacier

---

## 11. Integration Map (Module Wiring)

### 11.1 Service-to-Service Connections

| Source          | Target              | Protocol | Port  | Authentication       |
|----------------|---------------------|----------|-------|----------------------|
| React SPA       | FastAPI             | HTTPS    | 443   | JWT (Bearer token)   |
| FastAPI         | DuckDB (Parquet)    | Filesystem| —    | POSIX permissions    |
| FastAPI         | MLflow              | HTTP     | 5000  | API key              |
| FastAPI         | Redis               | TCP      | 6379  | Password (optional)  |
| Airflow         | PostgreSQL          | TCP      | 5432  | Username/password    |
| Airflow         | DS Notebooks        | Python   | —     | Subprocess           |
| Airflow         | RustFS (S3)         | HTTPS    | 9000  | Access key/secret    |
| Grafana         | Prometheus          | HTTP     | 9090  | —                    |
| Prometheus      | All services        | HTTP     | varied| —                    |

### 11.2 Shared Volumes

```yaml
volumes:
  gold_marts:
    name: elyssa_gold_marts
    driver: local
    driver_opts:
      type: none
      device: ./data-science/marts/
      o: bind

  model_artifacts:
    name: elyssa_model_artifacts
    driver: local
    driver_opts:
      type: none
      device: ./data-science/marts/processed/
      o: bind

  api_data:
    name: elyssa_api_data
```

### 11.3 Network Configuration

```yaml
networks:
  elyssa-net:
    name: elyssa-net
    driver: bridge
    ipam:
      config:
        - subnet: 172.20.0.0/16

  monitoring-net:
    name: elyssa-monitoring
    driver: bridge
```

---

## 12. Implementation Roadmap & Checklists

### 12.1 Phased Rollout Plan

| Phase | Weeks | Deliverables | Dependencies |
|-------|-------|-------------|--------------|
| 6a     | 1-2   | Docker Compose (MLflow + Prometheus + Grafana), CI/CD workflows | Web App (Phase 4) |
| 6b     | 3-4   | Terraform templates, Kubernetes manifests, HPA | Phase 6a |
| 6c     | 5-6   | Retraining DAGs, drift detection, monitoring dashboards | Phase 6b |
| 6d     | 7-8   | Canary deployments, runbooks, quarterly drills, security hardening | Phase 6c |

### 12.2 MLOPS Criterion Verification Checklists

**MLOPS.1 — Reproducible Pipelines**
- [ ] Docker Compose builds all services with single command
- [ ] Makefile targets for build/up/down/clean
- [ ] CI pipeline reproduces local dev environment
- [ ] Lock files committed for Python (pip freeze) and Node (package-lock.json)

**MLOPS.2 — Model Versioning**
- [ ] MLflow tracking server running
- [ ] All DS runs log params, metrics, and artifacts
- [ ] Models registered with stages (Staging → Production → Archived)
- [ ] Latest 5 model versions retained

**MLOPS.3 — Infrastructure-as-Code**
- [ ] Terraform templates for development, staging, production
- [ ] Local Docker Compose mirrors cloud infrastructure
- [ ] State file stored remotely (S3/GCS backend)

**MLOPS.4 — Containerisation**
- [ ] All services have Dockerfiles
- [ ] Multi-stage builds for API and frontend
- [ ] Non-root user in all containers
- [ ] Security scanning in CI (Trivy)

**MLOPS.5 — Model Serving**
- [ ] /predict/genre endpoint returns real predictions
- [ ] /predict/rating endpoint returns real predictions
- [ ] Graceful degradation when models unavailable
- [ ] Performance benchmarks documented

**MLOPS.6 — Model Governance**
- [ ] Model registry with stage transitions
- [ ] Canary release mechanism
- [ ] Rollback procedure documented and tested
- [ ] Model metadata tracked (training date, data range, metrics)

**MLOPS.7 — Monitoring**
- [ ] Prometheus metrics exported by all services
- [ ] Grafana dashboards for pipeline overview and model performance
- [ ] Structured logging in JSON format
- [ ] Logs shipped to centralized store (Loki)

**MLOPS.8 — Alerting**
- [ ] Prometheus alerting rules defined
- [ ] Alerts routed to Slack/PagerDuty
- [ ] Alert thresholds based on SLA targets

**MLOPS.9 — Data Freshness**
- [ ] Gold mart freshness tracked
- [ ] Alert when stale (>24h for weekly marts)
- [ ] Retraining pipeline triggered by data freshness

**MLOPS.10 — Observability**
- [ ] Airflow DAG status visible in Grafana
- [ ] API latency metrics (p50/p95/p99)
- [ ] Error rate by endpoint and status code
- [ ] Model drift metrics exposed

**MLOPS.11 — Security**
- [ ] No secrets in Docker images
- [ ] Non-root containers
- [ ] TLS 1.3 for public endpoints
- [ ] Trivy scan passes in CI

**MLOPS.12 — Compliance**
- [ ] Data retention policies documented
- [ ] PII handling documented
- [ ] RBAC configured for K8s and cloud

**MLOPS.13 — Documentation**
- [ ] MLOps README written
- [ ] Runbooks for DR scenarios
- [ ] Architecture diagram up-to-date
- [ ] Integration map documented

**MLOPS.14 — Disaster Recovery**
- [ ] Backup strategy documented
- [ ] Point-in-time recovery tested
- [ ] Model rollback procedure tested
- [ ] Quarterly drills scheduled

**MLOPS.15 — Continuous Improvement**
- [ ] Quarterly review process documented
- [ ] Post-mortem template available
- [ ] Checklists reviewed and updated quarterly

---

## Appendix A: File Inventory

```
elyssa-imdb/
├── .github/workflows/
│   ├── ci-de.yml                 # Data Engineering CI
│   ├── ci-ds.yml                 # Data Science CI
│   ├── ci-web.yml                # Web Application CI
│   ├── cd.yml                    # Continuous Deployment
│   └── trivy-scan.yml            # Security scanning
├── data-science/
│   ├── contracts/
│   │   ├── gold-to-ds.md         # DE → DS contract
│   │   └── ds-to-web.md          # DS → Web contract
│   └── scripts/
│       └── feature_statistics.py # Drift baseline generator
├── web-application/
│   ├── contracts/
│   │   ├── gold-to-api.md        # DE → API contract
│   │   └── api-to-frontend.md    # API → Frontend contract
│   └── api/requirements.txt      # +structlog, +prometheus-instrumentator
├── mlops/
│   ├── README.md                 # Master MLOps documentation
│   ├── docs/
│   │   └── implementation-plan.md
│   ├── docker-compose.yml        # Full dev environment
│   ├── docker/
│   │   ├── Dockerfile.api        # API (multi-stage, non-root)
│   │   ├── Dockerfile.frontend   # React SPA (multi-stage, nginx)
│   │   ├── Dockerfile.model      # Model serving (PyTorch/CatBoost)
│   │   └── nginx.conf            # Frontend reverse proxy
│   ├── infra/
│   │   ├── backend.tf            # Terraform state backend
│   │   ├── envs/
│   │   │   ├── dev/              # main.tf + variables.tf + outputs.tf
│   │   │   ├── staging/          # main.tf + variables.tf + outputs.tf
│   │   │   └── prod/             # main.tf + variables.tf + outputs.tf
│   │   └── modules/
│   │       ├── compute/          # main.tf + variables.tf + outputs.tf
│   │       ├── storage/          # main.tf + variables.tf + outputs.tf
│   │       ├── networking/       # main.tf + variables.tf + outputs.tf
│   │       └── monitoring/       # main.tf + variables.tf + outputs.tf
│   ├── airflow/
│   │   └── dags/
│   │       ├── retraining_pipeline.py  # Weekly retraining
│   │       └── drift_detection.py      # Daily drift monitoring
│   ├── drills/
│   │   ├── surge.py              # 200% data surge test
│   │   ├── adversarial.py        # Malformed request test
│   │   └── latency.py            # p95 latency baseline
│   ├── monitoring/
│   │   ├── prometheus/
│   │   │   ├── prometheus.yml
│   │   │   └── alert-rules.yml   # 7 alert rules
│   │   └── grafana/
│   │       ├── dashboards/
│   │       │   ├── dashboard-provider.yml
│   │       │   ├── pipeline-overview.json
│   │       │   └── model-performance.json
│   │       └── datasources/
│   │           └── prometheus.yml
│   ├── runbooks/
│   │   ├── node-failure.md
│   │   ├── model-rollback.md
│   │   ├── database-restore.md
│   │   └── quarterly-drill.md
│   └── checklists/
│       ├── mlops-1-to-5.md
│       ├── mlops-6-to-10.md
│       └── mlops-11-to-15.md
└── Makefile                      # +mlops-up/down/build targets
```

**Total: 65 files** (33 in initial commit + 32 in gap-closure commit)
```
