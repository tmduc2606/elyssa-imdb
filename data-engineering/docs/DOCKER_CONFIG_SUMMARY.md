# Docker Configuration Summary

## Stack (docker/docker-compose.yml)

| Service | Image | Mem Limit | Port (Host) | Purpose |
|---------|-------|-----------|-------------|---------|
| postgres | elyssa-postgres:latest | 3g | 54321 | Silver/Gold warehouse |
| airflow | elyssa-airflow:latest | 3g | 18081 | DAG orchestrator |
| etl-runner | elyssa-etl-runner:latest | 2.5g | — | Dedicated DuckDB ETL engine |
| rustfs | elyssa-rustfs:latest | 256m | 9100 / 9101 | S3-compatible object store |

## Memory Budget ~7.75 GB (out of 13.9 GB usable)

- Postgres: 3g + 1g shm
- Airflow: 2g + 1g shm
- etl-runner: 2.5g + 2g shm
- Headroom: ~4 GB for WSL2/system (≤56% of total RAM, well within ≤91% peak)

## Key Ports (Host → Container)

| Host | Container | Service |
|------|-----------|---------|
| 54321 | 5432 | PostgreSQL |
| 18081 | 8080 | Airflow Web UI |

## Volumes

| Volume | Mount | Service |
|--------|-------|---------|
| elyssa_pg_data | /var/lib/postgresql/data | postgres |
| elyssa_airflow_data | /opt/airflow | airflow |
| elyssa_etl_temp | /opt/etl/tmp | etl-runner |

## PostgreSQL Tuning (custom.conf)

- shared_buffers = 1GB
- work_mem = 256MB
- maintenance_work_mem = 512MB
- effective_cache_size = 4GB
- max_connections = 200
- max_wal_size = 4GB
