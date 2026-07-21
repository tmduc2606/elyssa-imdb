# MLOPS.1–5 — Reproducible Pipelines, Model Versioning, IaC, Containerisation, Model Serving

## MLOPS.1 — Reproducible Pipelines
- [ ] `docker compose -f mlops/docker-compose.yml build` completes without error
- [ ] `docker compose -f mlops/docker-compose.yml up -d` starts all services
- [ ] `make build && make up` produces identical environment
- [ ] `pip freeze > requirements.txt` and `npm ci` lock files committed
- [ ] CI pipeline builds from source (no pre-built images)

## MLOPS.2 — Model Versioning
- [ ] MLflow tracking server accessible at http://localhost:5000
- [ ] Every DS training run logs: `params`, `metrics`, `artifacts`
- [ ] Models registered with `mlflow.register_model()`
- [ ] Model stages used: `Staging` → `Production` → `Archived`
- [ ] Latest 5 versions retained per model

## MLOPS.3 — Infrastructure-as-Code
- [ ] Terraform templates exist for dev/staging/prod
- [ ] `terraform plan` succeeds without errors
- [ ] `terraform apply` provisions all required resources
- [ ] State stored remotely (S3/GCS backend)
- [ ] Local Docker Compose mirrors cloud infrastructure

## MLOPS.4 — Containerisation
- [ ] All services have Dockerfiles
- [ ] Multi-stage builds for API and frontend
- [ ] Non-root user (`USER elyssa`) in all containers
- [ ] Trivy scan in CI passes (no CRITICAL)
- [ ] Image sizes documented and tracked

## MLOPS.5 — Model Serving
- [ ] `POST /api/v1/predict/genre` returns predictions (or graceful degradation)
- [ ] `POST /api/v1/predict/rating` returns predictions (or graceful degradation)
- [ ] `GET /api/v1/models` lists all registered models
- [ ] Performance benchmarks: p95 < 500ms for all endpoints
- [ ] Graceful degradation on model unavailability
