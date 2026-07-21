# Node Failure Runbook

**Purpose:** Respond to Kubernetes node or Docker host failure.

**RTO Target:** 15 minutes (full recovery)

---

## Automated Recovery (Default Behavior)

| Platform      | Mechanism                      | Recovery Time |
|---------------|--------------------------------|---------------|
| Docker Compose| `restart: unless-stopped`      | Immediate     |
| Kubernetes    | ReplicaSet + node auto-repair  | < 2 minutes   |
| Cloud VM      | Auto-scaling group replacement | < 5 minutes   |

## Manual Intervention

### Docker Compose

```bash
# Check status
docker ps -a --filter name=elyssa

# Restart all services
docker compose -f mlops/docker-compose.yml up -d --force-recreate

# Check logs for crash reason
docker logs elyssa-api --tail 50
docker logs elyssa-postgres --tail 50
```

### Kubernetes

```bash
# Check node status
kubectl get nodes
kubectl describe node <failed-node>

# Check pod status
kubectl get pods -n elyssa
kubectl describe pod <failed-pod>
kubectl logs <failed-pod>

# Force reschedule if needed
kubectl delete pod <failed-pod>
# ReplicaSet will create a replacement automatically
```

## Post-Recovery Verification

```bash
# Health checks
curl http://localhost:8000/health
curl http://localhost:5000               # MLflow
curl http://localhost:9090               # Prometheus

# Data integrity
# Check PostgreSQL
docker exec elyssa-postgres pg_isready -U elyssa

# Check Redis
docker exec elyssa-redis redis-cli ping
```

## Escalation

If recovery exceeds RTO (1 hour):
1. Notify DE lead
2. Notify DS lead
3. Declare incident via PagerDuty / Slack
4. Begin post-mortem
