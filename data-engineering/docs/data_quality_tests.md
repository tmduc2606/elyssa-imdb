# Elyssa-IMDb — Data Quality Tests

## Test Coverage Summary

| Layer | Tests | Status |
|-------|-------|--------|
| Bronze | 87+ | ✅ Passing |
| Silver | 33 | ⚠️ Blocked (needs Docker PostgreSQL) |
| Gold | 12+ | ✅ (unblocked by profiles.yml) |
| DQ | 6 checks | ✅ Configured |
| Orchestration | 24+ | ✅ Passing |

## Bronze Layer Tests

### Schema Validation (Great Expectations)
- **Column count**: Matches expected schema per source
- **PK uniqueness**: `tconst` / `titleId` / `nconst` unique
- **Null rate**: Required fields (primary_title, title_type) must be 100% non-null
- **Row count**: > 0 per source

### Quarantine Tests
- Inject corrupt `.tsv.gz` → verify quarantined with error metadata
- Inject column-mismatch file → verify quarantined
- Inject empty file → verify quarantined
- Pipeline continues after quarantine

## Silver Layer Tests

### Null Rate Checks
| Check | Table | Column | Threshold |
|-------|-------|--------|-----------|
| null_rate_title_basics | title_basics | primary_title | 0% nulls |
| null_rate_title_rating | title_rating | average_rating | 0% nulls |
| null_rate_title_episode | title_episode | parent_tconst | 0% nulls |

### Referential Integrity
| Check | FK Column | PK Table | Max Orphans |
|-------|-----------|----------|-------------|
| referential_title_episode | parent_tconst | title_basics | 1% |

### Row Count Variance
| Table | Expected Min | Alert Threshold |
|-------|-------------|-----------------|
| title_basics | 100,000 | ±20% |
| name_basics | 100,000 | ±20% |

## Gold Layer Tests (dbt)

### Generic Tests (schema.yml)
- `unique` on PK columns
- `not_null` on required columns
- `accepted_range` on numeric fields:
  - `start_year`: 1874–2030
  - `average_rating`: 0.0–10.0
  - `num_votes`: ≥ 0
  - `runtime_minutes`: 1–1000
  - `birth_year`: 1800–2030

### Singular Tests
- **test_row_count_variance**: Compares current run row count vs previous run; flags >20% deviation
- **test_fk_integrity**: Verifies all `title_key`/`name_key` FKs resolve to existing records

## DQ Runner

```bash
python dq/run_checks.py \
  --config dq/config.yaml \
  --jdbc-url "postgresql://postgres:5432/elyssa_warehouse" \
  --jdbc-user elyssa \
  --jdbc-password elyssa_pg_2026
```

## Alert Behavior

- **PASS**: Logged to `data_quality_log` with `passed=TRUE`
- **FAIL**: Logged to `data_quality_log` with `passed=FALSE`
- **ALERT**: Row count deviation >20% triggers additional ALERT row with metric `row_count_deviation`
- **ERROR**: DQ check execution errors logged to `silver.quarantine`

## How to Run

```bash
# Bronze tests
python -m pytest bronze/tests/ -v

# Silver tests (requires Docker PostgreSQL)
docker compose up -d postgres
python -m pytest silver/tests/ -v

# Gold tests
cd gold && dbt debug && dbt run && dbt test

# DQ checks
python dq/run_checks.py --jdbc-url ... --jdbc-user ... --jdbc-password ...

# Orchestration tests
python -m pytest orchestration/tests/ -v
