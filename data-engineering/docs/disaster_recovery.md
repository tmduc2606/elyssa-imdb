# Elyssa-IMDb — Disaster Recovery

## Recovery Objectives

| Metric | Target | Method |
|--------|--------|--------|
| RPO (Recovery Point Objective) | < 24 hours | Daily pg_dump to RustFS |
| RTO (Recovery Time Objective) | < 30 minutes | Automated restore from S3 dump |

## Backup Strategy

### Automated Backups
- **Tool**: `pg_dump` (custom compressed format)
- **Target**: `s3://elyssa-backups/pgdump/`
- **Operator**: `orchestration/operators/backup.py` (`BackupOperator`)
- **Frequency**: Daily (recommended via Airflow DAG schedule)
- **Retention**: 30 days (S3 lifecycle policy recommended)

### Backup Execution
```bash
pg_dump --host postgres --port 5432 --username elyssa \
  --dbname elyssa_warehouse --format c \
  --file /tmp/elyssa_backup_$(date +%Y%m%d).dump --verbose

aws s3 cp /tmp/elyssa_backup_*.dump \
  s3://elyssa-backups/pgdump/ \
  --endpoint-url http://rustfs:9000
```

## Restore Procedures

### Full Database Restore
```bash
# 1. Download latest backup from S3
aws s3 cp s3://elyssa-backups/pgdump/elyssa_backup_YYYYMMDD.dump /tmp/

# 2. Restore to PostgreSQL
pg_restore --host postgres --port 5432 --username elyssa \
  --dbname elyssa_warehouse --verbose \
  /tmp/elyssa_backup_YYYYMMDD.dump
```

### Point-in-Time Recovery
```bash
# 1. Stop the pipeline
docker compose stop airflow

# 2. Restore base backup
pg_restore --host postgres --port 5432 --username elyssa \
  --dbname elyssa_warehouse --clean --if-exists \
  /tmp/elyssa_backup_YYYYMMDD.dump

# 3. Replay WAL archives (if configured)
# 4. Verify data integrity
python scripts/validation_report.py

# 5. Restart pipeline
docker compose start airflow
```

### Bronze Layer Recovery
Bronze Parquet files are immutable and stored in RustFS:
- **No restore needed** — data is already durable in S3
- **Re-ingestion**: If local Parquet is lost, re-run `ingest_all()` from source `.tsv.gz`

### Silver Layer Recovery
- **Primary**: Restore from pg_dump backup
- **Alternative**: Re-run Silver ETL from Bronze Parquet
  ```bash
  spark-submit silver/etl_runner.py --bronze-path /data/bronze/
  ```

### Gold Layer Recovery
- **Primary**: `dbt run --full-refresh` after Silver restore
- **Idempotent**: dbt models are rebuildable from Silver tables

## Failure Scenarios

### Scenario 1: PostgreSQL Corruption
1. Stop Airflow: `docker compose stop airflow`
2. Restore from latest pg_dump
3. Verify with `python scripts/validation_report.py`
4. Restart Airflow: `docker compose start airflow`
5. Re-run DAG from Bronze (Silver→Gold re-process)

### Scenario 2: Container Failure
```bash
# Restart all services
docker compose down && docker compose up -d

# Verify health
docker compose ps
docker compose logs postgres
```

### Scenario 3: Data Corruption in Silver
1. Identify affected tables from `data_quality_log`
2. Close current SCD2 records:
   ```sql
   UPDATE silver.title_basics SET valid_to = NOW(), is_current = FALSE
   WHERE tconst IN (SELECT tconst FROM ...);
   ```
3. Re-ingest from Bronze for affected records
4. Re-run dbt: `cd gold && dbt run --full-refresh`

### Scenario 4: Accidental Data Deletion
1. Query `silver.quarantine` for recent rejections
2. Restore deleted records from backup using point-in-time recovery
3. Re-ingest corrected data

## Validation After Recovery

```bash
# Verify row counts (credentials from docker/.env — never hardcoded)
python dq/run_checks.py --config dq/config.yaml \
  --jdbc-url "postgresql://postgres:5432/elyssa_warehouse" \
  --jdbc-user "$POSTGRES_USER" --jdbc-password "$POSTGRES_PASSWORD"

# Run dbt tests
cd gold && dbt test --select source:silver
```

## Contact & Escalation

| Severity | Response Time | Action |
|----------|--------------|--------|
| P1 (Data loss) | 15 min | Full restore from backup |
| P2 (Pipeline down) | 30 min | Container restart + DAG re-run |
| P3 (DQ failure) | 2 hours | Investigate + re-ingest affected batch |
| Degraded performance | 4 hours | Scale resources + investigate |
