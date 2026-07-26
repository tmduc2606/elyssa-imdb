# MLOps Unified Audit — Comparison Report

**Date:** 2026-07-26
**Scope:** MLOPS.1–MLOPS.15 criteria verification across 21 unified tasks
**Methodology:** Static code audit of all mlops/, data-science/, web-application/, data-engineering/, .github/workflows/ files

---

## 1. Executive Summary

| Criterion | Status | Coverage |
|-----------|--------|----------|
| MLOPS.1 — Reproducible Pipelines | ✅ | Docker Compose, Makefile, lock files, CI pipeline |
| MLOPS.2 — Model Versioning | ⚠️ Partial | MLflow infra exists; models lack registered tags and lineage |
| MLOPS.3 — Infrastructure-as-Code | ⚠️ Partial | All 3 envs defined; missing K8s manifests, some resource gaps |
| MLOPS.4 — Containerisation | ✅ | All services have multi-stage Dockerfiles with non-root user |
| MLOPS.5 — Model Serving | ⚠️ Partial | Endpoints exist; no Prometheus metrics instrumentation |
| MLOPS.6 — Model Governance | ⚠️ Partial | Registry wrappers exist; no validation gate before promotion |
| MLOPS.7 — Monitoring | ⚠️ Partial | Grafana dashboards defined; `prometheus-instrumentator` not wired |
| MLOPS.8 — Alerting | ⚠️ Partial | 7 alert rules defined; no alertmanager routing configured |
| MLOPS.9 — Data Freshness | ✅ | Airflow DAG with freshness check scheduled weekly |
| MLOPS.10 — Observability | ⚠️ Partial | structlog in deps but not configured; JSON logging not active |
| MLOPS.11 — Security | ⚠️ Partial | Non-root users, Trivy in CI; no TLS, no network policies |
| MLOPS.12 — Compliance | ⚠️ Partial | RBAC documented but not enforced in infra code |
| MLOPS.13 — Documentation | ✅ | README, implementation plan, 4 runbooks, 3 checklists |
| MLOPS.14 — Disaster Recovery | ⚠️ Partial | 4 runbooks exist; drills not yet executed this quarter |
| MLOPS.15 — Continuous Improvement | ✅ | Post-mortem template, quarterly drill schedule, review process |

---

## 2. Task-by-Task Results

### 2.1 Model & Artifact Registry

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.1 | Verify DS models registered in MLflow | MLflow tracking server defined (v2.18.0, PostgreSQL backend). `model_registry.py` wrapper supports `register_model()`, stage transitions. The Airflow retraining DAG calls `mlflow models register-model`. However, **no actual `log_model()` calls exist in the DS notebooks** that would attach metrics/tags. The notebooks save models to local paths (`gmu_genre_best.pt`, `catboost_rating_model.cbm`) without MLflow logging. | ❌ FAIL |
| 1.2 | Confirm Gold Parquet → feature matrix → model lineage | The retraining DAG has a linear flow (freshness → feature stats → register → canary) but feature statistics and model artifacts are tracked separately. There is **no run ID linkage** connecting the Gold Parquet input to the trained model output. The inference pipeline loads models from local filesystem paths, not from MLflow model URIs. | ❌ FAIL |
| 1.3 | Feature pipeline artifacts versioned in MLflow | `preprocessor.joblib`, `scaler.joblib`, `genre_list_mlb.joblib`, `title_embeddings.npy` are all persisted to `data-science/marts/processed/` on local disk. None are **logged to MLflow as run artifacts**. No artifact URIs are tracked. | ❌ FAIL |

### 2.2 CI/CD & IaC

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.4 | Single CI/CD workflow runs lint, test, build | **8 separate GitHub Actions workflows exist** (`ci.yml`, `ci-de.yml`, `ci-ds.yml`, `ci-web.yml`, `cd.yml`, `trivy-scan.yml`, `ds-tests.yml`, `api-gateway.yml`). They run independently per module rather than as a single unified workflow. The unified `ci.yml` has a matrix across all 3 modules but the module-specific workflows (`ci-web.yml`, `ci-ds.yml`) have more comprehensive checks. CD only builds API + Frontend, not Model or Airflow images. | ⚠️ PASS (with gaps) |
| 1.5 | IaC completeness (Terraform) | Terraform modules exist for networking (VPC, subnets, IGW), compute (ECS Fargate), storage (S3), monitoring (CloudWatch). All 3 envs (dev/staging/prod) are configured. **Missing elements:** no Kubernetes manifests (HPA, PDB, NetworkPolicy), no RDS instance definition, no ElastiCache, no IAM policies beyond the managed ECS execution role, monitoring alarm actions are empty arrays no SNS topics defined. | ⚠️ PARTIAL |
| 1.6 | IaC state stored remotely with locked access | `backend.tf` configures S3 backend (`elyssa-terraform-state` bucket) with DynamoDB table (`elyssa-terraform-locks`) for state locking, `encrypt = true`. No local state files in repo. | ✅ PASS |

### 2.3 Containerisation & Orchestration

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.7 | Every service has a Dockerfile | **12 Dockerfiles** across the repo covering: API (`mlops/docker/Dockerfile.api`, `web-application/api/Dockerfile`), Frontend (`mlops/docker/Dockerfile.frontend`), Model (`mlops/docker/Dockerfile.model`), Airflow (`docker/Dockerfile.airflow`), PostgreSQL, Neo4j, RustFS, DuckDB, ETL Runner. All use multi-stage builds. API and Model containers use non-root `elyssa` user. Frontend uses nginx default non-root. | ✅ PASS |
| 1.8 | Single `docker-compose up` starts full stack | `mlops/docker-compose.yml` (288 lines) defines 11 services: postgres, rustfs, redis, mlflow, api, model, frontend, airflow, prometheus, grafana, postgres-exporter, redis-exporter. Healthchecks defined for postgres, api, model services. Dependencies configured with `condition: service_healthy/service_started`. Shared networks and volumes. **Actual `docker compose up` test requires Docker daemon.** | ✅ PASS (static verification) |
| 1.9 | Trivy security scan on images | `trivy-scan.yml` reusable workflow exists. Called from `ci-web.yml`. Scans `elyssa-api:latest` for CRITICAL/HIGH, `exit-code: 1`, `ignore-unfixed: true`. **Only scans the API image** not model, frontend, or airflow images. | ⚠️ PARTIAL |

### 2.4 Automated Retraining & Pipelines

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.10 | Airflow DAG for automated retraining | `mlops/airflow/dags/retraining_pipeline.py` defined with 4 tasks: `check_gold_freshness` (PythonOperator checks `model_inventory.json` mtime), `generate_feature_statistics` (BashOperator), `register_in_mlflow` (BashOperator), `deploy_canary` (echo placeholder). Schedule: Sunday 6 AM UTC. Catchup disabled. Retries: 1 with 5min delay. Email on failure configured. | ✅ PASS |
| 1.11 | Simulate data freshness trigger | `_check_freshness()` function validates `model_inventory.json` age against `FRESHNESS_THRESHOLD_HOURS=168` (7 days). Fails with `RuntimeError` if stale. **Cannot test without running Airflow.** The DAG is not connected to any external data freshness event sensor (no `ExternalTaskSensor` or file sensor). | ⚠️ PARTIAL |
| 1.12 | Model validation gate before promotion | The retraining DAG has **no validation gate** between training and promotion. `deploy_canary` is a simple `echo` placeholder. No metric comparison (e.g., "new RMSE < previous RMSE * 1.05"), no automatic rollback logic, no canary traffic split implementation. The implementation plan describes a validation gate but the code does not implement it. | ❌ FAIL |

### 2.5 Monitoring & Observability

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.13 | Grafana dashboards | Two provisioned dashboards: `pipeline-overview.json` (5 panels: API latency p50/p95/p99, error rate, Airflow DAG status, Redis cache hit ratio, model drift KL) and `model-performance.json` (4 panels: Genre macro F1, Rating RMSE, feature drift heatmap, prediction confidence histogram). Provisioning via `dashboard-provider.yml` with Prometheus datasource. | ✅ PASS |
| 1.14 | Structured JSON logging | `structlog>=24.0.0` is in `requirements-api.txt` but **not imported or configured** in `web-application/api/app/main.py` or any API module. The API uses standard `logging.getLogger(__name__)` with no structured format. The implementation plan documents the expected JSON schema but it is not implemented in code. DS logging uses standard Python logging with plain text format. | ❌ FAIL |
| 1.15 | Model-specific metrics logged after inference | `prometheus-fastapi-instrumentator>=7.0.0` is in `requirements-api.txt` but **NOT imported or initialized** in `main.py`. No Prometheus metrics endpoint exposed. The inference service (`inference.py`) does not emit any Prometheus metrics for prediction counts, latency, or confidence. Grafana dashboards reference `mlflow_metric` and `model_drift_kl_divergence` but these metrics are never produced by the running services. | ❌ FAIL |

### 2.6 Resilience & Disaster Recovery

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.16 | Runbooks exist | 4 runbooks in `mlops/runbooks/`: `node-failure.md` (RTO 15min), `model-rollback.md` (6-step procedure), `database-restore.md` (RPO 24h, RTO 1h), `quarterly-drill.md` (Q1-Q4 rotation, post-mortem template). All have clear step-by-step instructions, commands, and escalation paths. | ✅ PASS |
| 1.17 | Blackout drill (surge, latency, adversarial) | 3 drill scripts in `mlops/drills/`: `surge.py` (50 concurrent workers, 60s, checks <1% error rate), `latency.py` (6 endpoints, 5 runs each, p95 < 500ms threshold), `adversarial.py` (15 adversarial requests, no 5xx allowed). Implementation plan includes nightly GitHub Actions schedule. **Drills not verified by actual execution.** | ✅ PASS (scripts exist) |
| 1.18 | Model rollback procedure | `model-rollback.md` runbook documents: identify status → select rollback target (MLflow `transition-stage`) → deploy (`docker compose --force-recreate` or `kubectl set image`) → canary verification (x-canary header, 15min monitoring) → full rollout → post-mortem template. Implementation plan mentions automated rollback on error rate spike. | ✅ PASS |

### 2.7 Security Controls

| # | Task | Finding | Verdict |
|---|------|---------|---------|
| 1.19 | RBAC with minimal permissions | Implementation plan documents RBAC table (5 roles: Admin, DE/DS/SWE Engineer, Read-only) with specific K8s namespace and cloud resource permissions. **No actual Kubernetes RBAC manifests exist.** Terraform has one IAM role for ECS execution with a managed policy. No namespace isolation, no role bindings. | ❌ FAIL |
| 1.20 | Encryption at rest and in transit | Terraform `backend.tf` uses `encrypt = true` for state. Implementation plan documents AES-256 at rest and TLS 1.3 in transit. **No actual TLS certificates configured.** Docker Compose services expose plain HTTP. No mTLS for inter-service communication. No storage bucket encryption configuration in Terraform (S3 default encryption). | ⚠️ PARTIAL |
| 1.21 | Network policies restricting inter-service | **No Kubernetes NetworkPolicy manifests exist.** The compute module's security group allows all egress (`0.0.0.0/0`) and ingress on ports 8000/443 from anywhere (`0.0.0.0/0`). Docker Compose uses a single flat bridge network (`elyssa-net`) with no segmentation between services. The implementation plan mentions network policies but does not provide configurations. | ❌ FAIL |

---

## 3. External vs Internal Perspectives

### Where External Observations Align with Internal Reality

| External Expectation | Internal Reality | Alignment |
|---------------------|-----------------|-----------|
| MLflow server running at :5000 | Defined in docker-compose with PostgreSQL backend | ✅ |
| Docker Compose with all services | 288-line compose with 11 services | ✅ |
| Multi-stage Dockerfiles | All 12 Dockerfiles use multi-stage builds | ✅ |
| Grafana dashboards provisioned | 2 dashboards with auto-provisioning | ✅ |
| Prometheus alert rules defined | 7 rules in alert-rules.yml | ✅ |
| Terraform for dev/staging/prod | 3 envs with 4 modules | ✅ |
| CI workflows exist | 8 workflows covering lint, test, build, scan | ✅ |
| Retraining DAG defined | Weekly schedule, 4 tasks | ✅ |
| Drift detection DAG defined | Daily schedule, 1 task | ✅ |
| Structured runbooks | 4 runbooks with step-by-step instructions | ✅ |

### Where External Observations Diverge from Internal Reality

| External Expectation | Internal Reality | Gap |
|---------------------|-----------------|-----|
| Models registered in MLflow with proper tags | No `log_model()` calls; models saved to local disk only | Critical |
| Full artifact lineage tracked | No run ID linkage from data to model | Critical |
| Prometheus metrics exposed at /metrics | `prometheus-instrumentator` not imported; no metrics endpoint | Critical |
| Structured JSON logging | `structlog` not configured; plain text logging used | Critical |
| Model validation gate before promotion | DAG deploys canary unconditionally; no metric comparison | Critical |
| Single unified CI workflow | 8 independent workflows; no gating between modules | Medium |
| TLS/HTTPS on public endpoints | All services on plain HTTP | High |
| Kubernetes NetworkPolicies | No NetworkPolicy manifests exist | High |
| RBAC enforced in infra code | Only documented, not implemented | High |
| Alerts routed to Slack/PagerDuty | Alertmanager targets are empty array | Medium |
| Canary traffic split implemented | Only documented; no actual traffic routing config | Medium |

---

## 4. MLOPS.1–MLOPS.15 Compliance Summary

| Criterion | Compliance | Blockers |
|-----------|-----------|----------|
| MLOPS.1 Reproducible Pipelines | 80% | No single-command unified CI pipeline |
| MLOPS.2 Model Versioning | 40% | Models not logged to MLflow; no tags |
| MLOPS.3 Infrastructure-as-Code | 60% | Missing K8s manifests, RDS, ElastiCache |
| MLOPS.4 Containerisation | 90% | Trivy only scans API image |
| MLOPS.5 Model Serving | 60% | No Prometheus metrics; no auto-scaling |
| MLOPS.6 Model Governance | 50% | No validation gate; no canary routing |
| MLOPS.7 Monitoring | 50% | Metrics not wired; instrumentator not configured |
| MLOPS.8 Alerting | 50% | No alert receiver routing |
| MLOPS.9 Data Freshness | 80% | No event-driven trigger; only cron |
| MLOPS.10 Observability | 40% | No structured logging; no trace IDs |
| MLOPS.11 Security | 50% | No TLS; no network policies |
| MLOPS.12 Compliance | 40% | RBAC not enforced; no audit logging |
| MLOPS.13 Documentation | 90% | Minor: missing architecture diagram image |
| MLOPS.14 Disaster Recovery | 70% | Drills not yet executed this quarter |
| MLOPS.15 Continuous Improvement | 80% | Action item tracking not verified |

**Overall Compliance:** ~60% (9 of 15 criteria have significant gaps requiring immediate remediation)
