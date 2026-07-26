# MLOps Optimization Plan

**Based on:** Unified audit of 21 tasks across MLOPS.1–MLOPS.15
**Date:** 2026-07-26
**Priority:** P0 = blocking, P1 = high, P2 = medium, P3 = low

---

## Priority Matrix

| Priority | Count | Action Required |
|----------|-------|----------------|
| P0 — Critical (blocking MLOPS compliance) | 6 | Immediate |
| P1 — High (significant risk/gap) | 5 | This sprint |
| P2 — Medium (important but not blocking) | 4 | Next sprint |
| P3 — Low (nice to have) | 3 | Backlog |

---

## P0 — Critical (Must Fix Immediately)

### MLOPS.01: Wire Prometheus Metrics to API Service

**Gap:** `prometheus-fastapi-instrumentator==7.0.0` is in `requirements-api.txt` but never imported or initialized. The API exposes no `/metrics` endpoint. All Grafana dashboards and Prometheus alert rules reference metrics that are never produced.

**Implementation:**

Edit `web-application/api/app/main.py` — add Prometheus instrumentator initialization in `create_app()`:

```python
from prometheus_fastapi_instrumentator import Instrumentator

def create_app() -> FastAPI:
    app = FastAPI(...)
    # ... existing middleware and routes ...

    # Instrument for Prometheus
    Instrumentator().instrument(app).expose(app)

    return app
```

**Effort:** 1 hour
**Impact:** Enables MLOPS.7 (Monitoring), MLOPS.8 (Alerting), MLOPS.10 (Observability)
**Files:** `web-application/api/app/main.py`

---

### MLOPS.02: Implement MLflow `log_model()` in DS Training Pipeline

**Gap:** DS models are saved to local disk (`gmu_genre_best.pt`, `catboost_rating_model.cbm`) but never logged to MLflow. The model registry wrapper exists but is not called by any training script.

**Implementation:**

Update `data-science/src/models/genre/gmu.py` and `data-science/src/models/rating/catboost_regressor.py` training entry points to call:

```python
from src.registry.model_registry import ModelRegistry

registry = ModelRegistry(tracking_uri="http://mlflow:5000")
with mlflow.start_run(run_name=f"{model_name}_training_{datetime.now():%Y%m%d_%H%M%S}") as run:
    mlflow.log_params(params)
    mlflow.log_metrics(metrics)
    mlflow.log_artifact("gmu_genre_best.pt")
    mlflow.log_artifact("preprocessor.joblib")
    mlflow.log_artifact("genre_list_mlb.joblib")
    mlflow.log_artifact("feature_columns.json")
    registry.register_model("Elyssa_Genre_GMU", run.info.run_id, metrics)
    registry.promote_to_staging("Elyssa_Genre_GMU", version)
```

Also update `data-science/config/settings.yaml` to change MLflow tracking URI from local SQLite to the server URI:
```yaml
mlflow:
  tracking_uri: "http://mlflow:5000"
  experiment_prefix: "elyssa_phase3"
```

**Effort:** 4 hours
**Impact:** Enables MLOPS.2 (Model Versioning), MLOPS.6 (Model Governance)
**Files:** `data-science/src/models/genre/gmu.py`, `data-science/src/models/rating/catboost_regressor.py`, `data-science/src/registry/model_registry.py`, `data-science/config/settings.yaml`

---

### MLOPS.03: Implement Model Validation Gate in Retraining DAG

**Gap:** The retraining DAG deploys canary unconditionally without comparing new model metrics against the current production model. An underperforming model can be promoted.

**Implementation:**

Add a `validate_model` PythonOperator task between `register_mlflow` and `deploy_canary` in `mlops/airflow/dags/retraining_pipeline.py`:

```python
def _validate_model() -> None:
    import mlflow
    from mlflow.tracking import MlflowClient

    client = MlflowClient()
    new_run = ...  # Get latest run ID from XCom
    new_metrics = client.get_run(new_run).data.metrics

    # Get current production model metrics
    prod_versions = client.get_latest_versions("Elyssa_Genre_GMU", stages=["Production"])
    if prod_versions:
        prod_run = client.get_run(prod_versions[0].run_id)
        prod_metrics = prod_run.data.metrics
        if new_metrics.get("test_macro_f1", 0) < prod_metrics.get("test_macro_f1", 0) * 0.95:
            raise ValueError(
                f"New model F1 ({new_metrics['test_macro_f1']:.4f}) degraded vs "
                f"production ({prod_metrics['test_macro_f1']:.4f}) — blocking deployment"
            )

    print("Validation passed")
```

**Effort:** 3 hours
**Impact:** Enables MLOPS.6 (Model Governance), prevents regression deployments
**Files:** `mlops/airflow/dags/retraining_pipeline.py`

---

### MLOPS.04: Implement Structured JSON Logging

**Gap:** `structlog` is in dependencies but never configured. All services use standard `logging` with plain text format. No trace IDs, no JSON output, no centralized log shipping.

**Implementation:**

Update `web-application/api/app/main.py` to configure structlog at startup:

```python
import structlog

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)
```

Add trace ID middleware:
```python
import uuid

@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Trace-Id", str(uuid.uuid4()))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(trace_id=trace_id)
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response
```

**Effort:** 3 hours
**Impact:** Enables MLOPS.10 (Observability), incident response
**Files:** `web-application/api/app/main.py`, `web-application/api/requirements-api.txt` (already has structlog)

---

### MLOPS.05: Add Model Inference Metrics to Prometheus

**Gap:** Model inference endpoints (`/predict/genre`, `/predict/rating`) do not emit Prometheus metrics for prediction counts, latency, or confidence.

**Implementation:**

In `web-application/api/app/models/inference.py`, add Prometheus counters/histograms:

```python
from prometheus_client import Counter, Histogram

genre_predictions = Counter(
    "genre_predictions_total", "Total genre predictions", ["status"]
)
rating_predictions = Counter(
    "rating_predictions_total", "Total rating predictions", ["status"]
)
prediction_latency = Histogram(
    "prediction_latency_seconds", "Prediction latency", ["model"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5)
)
prediction_confidence = Histogram(
    "prediction_confidence", "Prediction confidence", ["model"],
    buckets=(0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0)
)
```

Wrap `predict_genre()` and `predict_rating()` methods with timing and counter increments.

**Effort:** 2 hours
**Impact:** Enables MLOPS.7, MLOPS.8, MLOPS.10 — the dashboards and alerts become functional
**Files:** `web-application/api/app/models/inference.py`, `web-application/api/app/api/router.py`

---

### MLOPS.06: Implement Network Security Policies

**Gap:** No Kubernetes NetworkPolicy manifests exist. Docker Compose uses a flat bridge network. The compute module security group allows unrestricted egress.

**Implementation:**

Create `mlops/infra/k8s/network-policy.yaml`:

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: api-network-policy
spec:
  podSelector:
    matchLabels:
      app: elyssa-api
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - podSelector:
            matchLabels:
              app: elyssa-frontend
        - namespaceSelector:
            matchLabels:
              name: elyssa-monitoring
      ports:
        - port: 8000
  egress:
    - to:
        - podSelector:
            matchLabels:
              app: elyssa-redis
      ports:
        - port: 6379
    - to:
        - podSelector:
            matchLabels:
              app: elyssa-mlflow
      ports:
        - port: 5000
```

Add ingress restriction to the Terraform security group:
```hcl
ingress {
  from_port   = 8000
  to_port     = 8000
  protocol    = "tcp"
  cidr_blocks = var.allowed_cidr_blocks  # Not 0.0.0.0/0
}
```

**Effort:** 3 hours
**Impact:** Enables MLOPS.11 (Security), MLOPS.12 (Compliance)
**Files:** `mlops/infra/k8s/network-policy.yaml`, `mlops/infra/modules/compute/main.tf`

---

## P1 — High (Must Fix This Sprint)

### MLOPS.07: Add Model + Airflow + Frontend Images to CD Pipeline

**Gap:** `cd.yml` only builds and pushes API and Frontend images. Model serving and Airflow images are not part of the CD pipeline.

**Effort:** 2 hours
**Impact:** Complete CI/CD for all services
**Files:** `.github/workflows/cd.yml`

### MLOPS.08: Add TLS/HTTPS Termination

**Gap:** No TLS configuration anywhere. API serves on plain HTTP. No cert-manager or Let's Encrypt setup.

**Effort:** 4 hours
**Impact:** MLOPS.11 Security compliance
**Files:** New `docker/tls/` or configure nginx.conf with SSL

### MLOPS.09: Configure Alertmanager with Slack/PagerDuty Routing

**Gap:** Prometheus alertmanager targets are `[]` (empty). Alerts are defined but never delivered.

**Effort:** 2 hours
**Impact:** MLOPS.8 Alerting operational
**Files:** `mlops/monitoring/prometheus/prometheus.yml`, new `alertmanager.yml`

### MLOPS.10: Add RBAC Implementation (Kubernetes + IAM)

**Gap:** RBAC is documented but not enforced. No K8s Role/ClusterRole/ServiceAccount manifests. No IAM policies beyond ECS execution.

**Effort:** 4 hours
**Impact:** MLOPS.12 Compliance
**Files:** `mlops/infra/k8s/rbac.yaml`, `mlops/infra/modules/compute/iam.tf`

### MLOPS.11: Add Trivy Scanning for All Images

**Gap:** Trivy only scans the API image. Model, Frontend, and Airflow images are not scanned.

**Effort:** 1 hour
**Impact:** Complete vulnerability coverage
**Files:** `.github/workflows/trivy-scan.yml` (make matrix or multi-image)

---

## P2 — Medium (Next Sprint)

### MLOPS.12: Unify CI Workflows

**Gap:** 8 independent workflows with no cross-module gating. Merge into a single workflow with dependency graph.

**Effort:** 3 hours
**Impact:** MLOPS.1 reproducibility, release gates
**Files:** `.github/workflows/ci.yml` (replace with unified workflow)

### MLOPS.13: Implement Canary Traffic Split

**Gap:** Canary is only a placeholder echo command. No actual weighted traffic routing.

**Effort:** 4 hours
**Impact:** MLOPS.6 safe deployments
**Files:** `mlops/airflow/dags/retraining_pipeline.py`, new istio/nginx config

### MLOPS.14: Add S3 Bucket Encryption and Lifecycle Policies

**Gap:** S3 buckets created without explicit server-side encryption configuration.

**Effort:** 1 hour
**Impact:** MLOPS.11 encryption at rest
**Files:** `mlops/infra/modules/storage/main.tf`

### MLOPS.15: Add Data Freshness Event Sensor

**Gap:** Retraining triggered only by weekly cron, not by data arrival events.

**Effort:** 3 hours
**Impact:** MLOPS.9 faster retraining response
**Files:** `mlops/airflow/dags/retraining_pipeline.py`

---

## P3 — Low (Backlog)

### MLOPS.16: Add HPA Kubernetes Manifest

**Gap:** HPA config documented in implementation plan but not as an actual K8s manifest file.

**Effort:** 1 hour

### MLOPS.17: Add cosign Image Signing

**Gap:** Image signing discussed in implementation plan but not implemented.

**Effort:** 2 hours

### MLOPS.18: Add Architecture Diagram Image

**Gap:** MLOPS.13 documentation requirement for architecture diagram not met.

**Effort:** 2 hours

---

## Implementation Roadmap

### Week 1: P0 — Critical
| Day | Focus | Tasks |
|-----|-------|-------|
| Mon | Prometheus metrics + structured logging | MLOPS.01, MLOPS.04 |
| Tue | MLflow model registration | MLOPS.02 |
| Wed | Model validation gate | MLOPS.03 |
| Thu | Inference metrics | MLOPS.05 |
| Fri | Network policies | MLOPS.06 |

### Week 2: P1 — High
| Day | Focus | Tasks |
|-----|-------|-------|
| Mon | CD pipeline expansion + Trivy | MLOPS.07, MLOPS.11 |
| Tue | TLS termination | MLOPS.08 |
| Wed | Alertmanager routing | MLOPS.09 |
| Thu | RBAC implementation | MLOPS.10 |
| Fri | Integration testing, verification | Re-run all 21 audit tasks |

### Week 3: P2 — Medium
| Day | Focus | Tasks |
|-----|-------|-------|
| Mon | Unified CI workflow | MLOPS.12 |
| Tue | Canary traffic split | MLOPS.13 |
| Wed | S3 encryption + lifecycle | MLOPS.14 |
| Thu | Data freshness sensor | MLOPS.15 |
| Fri | Documentation updates | Update checklists, runbooks |

---

## Acceptance Criteria

After implementing P0 items:

1. `curl http://localhost:8000/metrics` returns Prometheus metrics
2. All models have entries in MLflow registry with stage tags and metrics
3. Retraining DAG blocks deployment if new model underperforms production
4. API logs are valid JSON with `service`, `trace_id`, `level`, `message` fields
5. `model_drift_kl_divergence` and `genre_predictions_total` metrics visible in Prometheus
6. Micro-segmentation prevents arbitrary pod-to-pod communication
