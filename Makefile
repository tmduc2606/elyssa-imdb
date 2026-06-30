# Elyssa-IMDb | Makefile
# Build targets with Docker cache pruning to prevent bloat.

.PHONY: build build-all prune up down clean

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
