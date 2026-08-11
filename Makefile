# Elyssa-IMDb | Makefile
# Build targets with Docker cache pruning to prevent bloat.
# DE stack uses docker/docker-compose.yml; Web stack uses root docker-compose.yml.

.PHONY: build build-svc build-quick prune up down clean web-up web-down export mlops-up mlops-down mlops-build posters-up

# ─── DE Stack (docker/docker-compose.yml) ──────────────────

# Build all DE services
build:
	docker builder prune -f
	docker compose -f docker/docker-compose.yml build

# Build a specific DE service: make build-svc svc=airflow
build-svc:
	docker builder prune -f
	docker compose -f docker/docker-compose.yml build $(svc)

# Build without pruning (faster, accumulates cache)
build-quick:
	docker compose -f docker/docker-compose.yml build

# Prune Docker build cache only
prune:
	docker builder prune -a -f

# Start all DE services
up:
	docker compose -f docker/docker-compose.yml up -d

# Stop all DE services
down:
	docker compose -f docker/docker-compose.yml down

# Full clean: prune cache + stop + remove volumes
clean:
	docker builder prune -a -f
	docker compose -f docker/docker-compose.yml down -v

# ─── Web Stack (root docker-compose.yml) ───────────────────

web-up:
	docker compose up -d

web-down:
	docker compose down

# ─── Export Gold marts to Parquet ──────────────────────────

# Export Gold marts from PostgreSQL to Parquet (requires DE stack running)
# Credentials come from docker/.env (never hardcoded).
export:
	docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/gold_export_runner.py

# ─── MLOps targets ──────────────────────────────────────────

# Start MLOps full dev environment
mlops-up:
	docker compose -f mlops/docker-compose.yml up -d

# Stop MLOps environment
mlops-down:
	docker compose -f mlops/docker-compose.yml down

# Build MLOps environment
mlops-build:
	docker builder prune -f
	docker compose -f mlops/docker-compose.yml build

# ─── OpenPosterDB (self-hosted poster service) ──────────────

posters-up:
	docker compose -f mlops/docker-compose.yml --profile posters up -d openposterdb
