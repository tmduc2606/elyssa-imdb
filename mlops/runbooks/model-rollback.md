# Model Rollback Runbook

**Purpose:** Revert a model deployment to a previous production version when the current model exhibits degraded performance.

**Triggers:**
- Error rate spike > 1% after model deployment
- P95 latency increase > 2x baseline
- Manual escalation from DS team
- Drift alert KL divergence > 0.2

---

## Step 1: Identify Status

```bash
# Check current model version in production
curl -s http://localhost:8000/api/v1/models | python -m json.tool

# List MLflow model versions
mlflow models list --model "Elyssa_Genre_GMU"
mlflow models list --model "Elyssa_Rating_CatBoost"
```

## Step 2: Select Rollback Target

```bash
# View version history with metrics
mlflow experiments list --view active
mlflow runs list --experiment-id <ID>

# Transition previous production version back to production
mlflow models transition-stage \
  --model-uri "models:/Elyssa_Genre_GMU/3" \
  --stage "Production"
```

## Step 3: Deploy Rolled-Back Model

```bash
# Option A: Docker Compose (dev)
docker compose -f mlops/docker-compose.yml up -d api --force-recreate

# Option B: Kubernetes (staging/prod)
kubectl set image deployment/elyssa-api \
  api=ghcr.io/tmduc2606/elyssa-api:v3-rollback

# Verify deployment
kubectl rollout status deployment/elyssa-api
```

## Step 4: Canary Verification

```bash
# Send canary traffic
curl -H "x-canary: true" -X POST http://localhost:8000/api/v1/predict/genre \
  -H "Content-Type: application/json" \
  -d '{"runtime_minutes":142,"start_year":1994,"title_type":"movie","is_adult":false}'

# Monitor for 15 minutes
# Check metrics in Grafana dashboard "Model Performance"
```

## Step 5: Full Rollout

```bash
# After 15 min canary OK:
kubectl set image deployment/elyssa-api \
  api=ghcr.io/tmduc2606/elyssa-api:v3-rollback

# Remove canary annotation
kubectl delete virtualservice elyssa-api-canary
```

## Step 6: Post-Mortem

```markdown
## Model Rollback Post-Mortem

**Date:** YYYY-MM-DD
**Model:** Elyssa_Genre_GMU
**Rolled back from:** v5 → v3
**Trigger:** [error rate / latency / manual]

### Root Cause
...
### Action Items
- [ ] ...
```
