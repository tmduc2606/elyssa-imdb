# Database Restore Runbook

**Purpose:** Restore PostgreSQL database from backup after data corruption or loss.

**RPO Target:** 24 hours (daily backups)
**RTO Target:** 1 hour

---

## Prerequisites

```bash
# Required tools
pg_dump / pg_restore (PostgreSQL 16+)
aws s3 CLI configured (for cloud backups)
```

## Step 1: Assess Damage

```bash
# Check database health
docker exec elyssa-postgres pg_isready -U elyssa

# List recent errors in logs
docker logs elyssa-postgres --tail 100

# Check data integrity
docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse \
  -c "SELECT count(*) FROM information_schema.tables;"
```

## Step 2: Locate Backup

```bash
# Local backups
ls -la /var/backups/postgres/

# Cloud backups (S3)
aws s3 ls s3://elyssa-prod-backups/postgres/

# List available backup timestamps
# Format: elyssa_warehouse_YYYY-MM-DD_HHMMSS.dump
```

## Step 3: Restore

```bash
# Stop services that depend on the database
docker compose -f mlops/docker-compose.yml stop api airflow

# Option A: Restore from local backup
docker exec -i elyssa-postgres pg_restore -U elyssa -d elyssa_warehouse \
  --clean --if-exists \
  < /var/backups/postgres/elyssa_warehouse_2026-07-21_220000.dump

# Option B: Restore from S3
aws s3 cp s3://elyssa-prod-backups/postgres/elyssa_warehouse_2026-07-21_220000.dump .
docker cp elyssa_warehouse_2026-07-21_220000.dump elyssa-postgres:/tmp/
docker exec elyssa-postgres pg_restore -U elyssa -d elyssa_warehouse \
  --clean --if-exists /tmp/elyssa_warehouse_2026-07-21_220000.dump
```

## Step 4: Verify

```bash
# Check row counts match expected
docker exec -it elyssa-postgres psql -U elyssa -d elyssa_warehouse \
  -c "SELECT schemaname, tablename, n_live_tup FROM pg_stat_user_tables ORDER BY n_live_tup DESC;"

# Restart services
docker compose -f mlops/docker-compose.yml up -d api airflow

# Verify API health
curl http://localhost:8000/health
```

## Step 5: Post-Recovery

```bash
# Trigger a fresh backup immediately
pg_dump -U elyssa -h localhost -p 54321 elyssa_warehouse \
  > elyssa_warehouse_post_recovery.dump

# Document incident
```

> **Note:** For point-in-time recovery (PITR), the database must be configured with WAL archiving. Contact the DE team for PITR procedures.
