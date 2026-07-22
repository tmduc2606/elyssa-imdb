# Elyssa-IMDb | Makefile
# Build targets with Docker cache pruning to prevent bloat.

.PHONY: build build-all prune up down clean export mlops-up mlops-down mlops-build

# Build all services (prunes build cache first)
build:
	docker builder prune -f
	docker compose build

# Build a specific service: make build-svc svc=airflow
build-svc:
	docker builder prune -f
	docker compose build $(svc)

# Build without pruning (faster, accumulates cache)
build-quick:
	docker compose build

# Prune Docker build cache only
prune:
	docker builder prune -a -f

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Full clean: prune cache + stop + remove volumes
clean:
	docker builder prune -a -f
	docker compose down -v

# ─── Export Gold marts to Parquet ──────────────────────────

# Export Gold marts from PostgreSQL to Parquet (requires docker-compose running)
export:
	docker exec elyssa-airflow python /opt/airflow/data-engineering/scripts/export_marts.py

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
