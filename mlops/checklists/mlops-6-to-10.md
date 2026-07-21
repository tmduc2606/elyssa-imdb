# MLOPS.6–10 — Model Governance, Monitoring, Alerting, Data Freshness, Observability

## MLOPS.6 — Model Governance
- [ ] Model registry with stage transitions working
- [ ] Canary release mechanism documented and testable
- [ ] Rollback procedure documented in `runbooks/model-rollback.md`
- [ ] Model metadata tracked (training date, data range, metrics)
- [ ] Approval workflow for Staging → Production transition

## MLOPS.7 — Monitoring
- [ ] Prometheus metrics exported by all services
- [ ] FastAPI exposes metrics at `/metrics`
- [ ] Grafana dashboard "Elyssa Pipeline Overview" configured
- [ ] Grafana dashboard "Model Performance" configured
- [ ] All exporters deployed (postgres, redis, node)

## MLOPS.8 — Alerting
- [ ] Prometheus alerting rules defined in `alert-rules.yml`
- [ ] Alerts routed to Slack/PagerDuty
- [ ] Alert thresholds aligned with SLAs
- [ ] Test alert fired and received within last 30 days

## MLOPS.9 — Data Freshness
- [ ] Gold mart `snapshot_date` tracked and monitored
- [ ] Alert fires when mart not updated within SLA window
- [ ] Retraining pipeline triggered by data freshness check
- [ ] Airflow DAG `elyssa_retraining_pipeline` scheduled

## MLOPS.10 — Observability
- [ ] Airflow DAG status visible in Grafana
- [ ] API latency metrics available (p50/p95/p99)
- [ ] Error rate by endpoint and status code
- [ ] Model drift metrics (KL divergence) exposed
- [ ] Structured logging in JSON format implemented
