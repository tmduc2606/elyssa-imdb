# Elyssa-IMDb — ETL Pipeline Documentation

## DAG Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│  imdb_pipeline (sensor-driven)                                      │
│                                                                      │
│  [imdb_data_sensor] ──► [bronze_ingest] ──┐                        │
│                     ──► [db_ingest] ──────┤                        │
│                                           ▼                        │
│                                   [bronze_ingestion_done]           │
│                                           │                        │
│                                           ▼                        │
│                                   [silver_transform]               │
│                                           │                        │
│                           ┌───────────────┼───────────────┐        │
│                           ▼               │               ▼        │
│                   [gold_dbt_run]          │       [gold_dbt_test]  │
│                           │               │               │        │
│                           └───────┬───────┘               │        │
│                                   ▼                       │        │
│                           [neo4j_sync] ◄──────────────────┘        │
│                                   │                                │
│                           [dq_checks]                              │
│                                   │                                │
│                           [freshness_check]                        │
│                                   │                                │
│                           [pipeline_end]                           │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  neo4j_sync_dag (triggered by main DAG completion)                  │
│  schedule_interval: None (external trigger)                         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│  quarterly_review_dag (cron: quarterly)                             │
│  schedule_interval: "0 9 1 1,4,7,10 *"                             │
└─────────────────────────────────────────────────────────────────────┘
```

## Retry Policy

Configured via `orchestration/config/retry.yaml`:

| Parameter | Value |
|-----------|-------|
| max_retries | 4 |
| base_delay | 60s |
| max_delay | 1800s (30 min) |
| backoff_factor | 2x (exponential) |

Retry sequence: 60s → 120s → 240s → 480s

## Failure Handling

1. **Bronze ingestion**: Corrupt files quarantined to `bronze/quarantine/` with error metadata
2. **Silver ETL**: Failed batches logged, pipeline retries with exponential backoff
3. **Gold dbt**: Test failures block downstream tasks, trigger DQ alert
4. **DQ checks**: FAIL status logged to `silver.data_quality_log`, deviation >20% triggers ALERT
5. **Task failure**: `on_failure_callback` emits structured alert (HIGH for Bronze/Silver, MEDIUM for rest)

## Freshness SLA

- **Window**: 24 hours from last `ingested_at` timestamp
- **Check**: `freshness_check` task queries each Silver table
- **Violation**: Raises `AlertFreshnessViolation`

## Backup Strategy

- **Method**: `pg_dump` custom format (compressed) → RustFS S3
- **Operator**: `BackupOperator` in `orchestration/operators/backup.py`
- **Target**: `s3://elyssa-backups/pgdump/`
- **RPO**: < 24 hours (daily backup schedule recommended)
- **RTO**: < 30 minutes (restore from S3 dump)
