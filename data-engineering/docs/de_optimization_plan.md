# DE Pipeline Optimization Plan

**Codename: Elyssa** — Phase 1 Data Engineering Module  
_Cross-compared findings from specialized assessment, external Architecture Review (3 advisors), and Elyssa proposal criteria_

**Hardware target:** AMD Athlon 200GE (2C/4T), 16 GB RAM  
**Current pipeline runtime:** ~5h36m (Bronze 47m → Silver 3h39m → Gold 63m → Export 15m)  
**Assessment date:** 2026-07-22

---

## Optimization Philosophy

Given the hardware ceiling (2 cores, 16 GB), the plan prioritizes **architectural optimizations that reduce total runtime without requiring more parallelism** — better indexing, incremental strategies, smarter data skipping, and pre-computed aggregates over brute-force parallel scaling.

Three tiers:

- **Tier 1 — Zero-cost fixes:** SQL rewrites, grain clarifications, index additions (no infra change, immediate impact)
- **Tier 2 — Configuration & incremental:** dbt thread tuning, incremental models, materialized views (leverage existing infra)
- **Tier 3 — Architectural:** Partitioning, engine consolidation, pre-computed aggregates (structural change, requires testing)

---

## Summary Table

| # | Domain | Current State | Optimization | Est. Impact | Tier | Depends On |
|---|--------|---------------|-------------|-------------|------|------------|
| 1 | Gold PK | fact_performance PK declared on wrong grain | Fix PK to (title_key, name_key, ordering) | Eliminates false 1.9M "duplicate" warnings | T1 | — |
| 2 | Gold PK | fact_episode PK declared on nullable columns | PK = episode_key; COALESCE NULL season/episode | Eliminates false 1.9M "duplicate" warnings | T1 | — |
| 3 | DQ SQL | fact_title_principal PK test uses wrong column name | Change `tconst` to `title_key` in DQ check | Unblocks 4 previously-failing DQ tests | T1 | — |
| 4 | FK | 7,649 orphan nconst in fact_performance | Add FK pre-check in Silver before Gold materialization | Catches referential drift early | T1 | — |
| 5 | FK | 323K episode series_key orphans | Document or fix series_key / title_type join in int_title_details | Clarifies 3% episode provenance | T1 | — |
| 6 | Bronze | `all_varchar=true` on read_csv adds type coercion cost | Add explicit schema structs to DuckDB read_csv | Target: 47m → <15m | T2 | Schema definition per source |
| 7 | dbt | `threads: 2` limits Gold model concurrency | Increase to `threads: 4` (HW-limited; 4 > 2 on 4-logical-core CPU) | Target: 63m → ~40m | T2 | profiles.yml edit |
| 8 | dbt | All 6 mart models use full `table` rebuild | Convert high-volume marts (fact_performance, fact_title_principal, dim_title) to `incremental` | Target: 63m → ~35m | T2 | unique_key + timestamp column |
| 9 | Performance | Actor co-occurrence 30s on 100M-row fact_performance | Materialize co-occurrence as `agg_actor_cooccurrence` table | Target: 30s → <1s | T2 | New dbt model |
| 10 | Performance | No single-row lookup index on dim_person for web API | Add index on dim_person(primary_name) for search | Tooltip: sub-second lookups | T2 | Index DDL |
| 11 | Architecture | 5 engines (DuckDB, PySpark, Postgres, Neo4j, RustFS) for 5 GB data | Consolidate Silver+Gold into DuckDB-native pipeline | Target: 5.5h → <2h (total) | T3 | Pipeline rewrite |
| 12 | Architecture | Gold export (Postgres → Parquet) takes 15 min | Replace export step with direct DuckDB `COPY (query) TO 'file.parquet'` | Target: 15m → <2m | T3 | DuckDB postgres_scanner |
| 13 | Incremental | Full pipeline rerun on every execution | Implement watermark-based incremental loads for Bronze → Silver | Target: 5.5h → ~45m (incremental) | T3 | Watermark logic exists but unused |
| 14 | Partitioning | No partition pruning on 100M-row fact tables | Partition fact_performance by title_type or year bucket | Target: query scan reduction 40-60% | T3 | Partition key design |
| 15 | Indexing | Missing FK composite indexes on Gold fact tables | Add composite indexes (title_key + name_key) on fact_performance | Target: join speedup 2-5x | T2 | Index DDL |
| 16 | Governance | _MANIFEST.json not written to marts/full/ | Fix or re-run GoldExportOperator after dbt test passes | Restores export audit trail | T1 | Existing operator fix (G9) |
| 17 | Documentation | 89-row nconst delta in SCD2 filter unexplained | Document in schema_dictionary.md | Reduces confusion for DE audits | T1 | — |

---

## Detailed Plan

### Tier 1 — Zero-Cost Fixes (0 dev hours, immediate)

#### O1. Fix fact_performance PK Grain

**Current:** `unique` test on `(tconst, nconst, category)` — 1,905,885 "duplicates"  
**Problem:** A person can have multiple orderings per category per title (e.g., credited as "actor" at ordering 1 and "actor" at ordering 5).  
**Fix in** `gold/models/marts/schema.yml`:
```yaml
- name: fact_performance
  columns:
    - name: title_key
    - name: name_key
    - name: ordering
      tests: [unique, not_null]
      # maintain PK as (title_key, name_key, ordering)
```

#### O2. Fix fact_episode PK Grain

**Current:** `unique` test on `(series_key, season_number, episode_number)` — 1,978,824 "duplicates"  
**Problem:** NULL season_number and episode_number collapse all episodes with missing numbers into the same key.  
**Fix in** `gold/models/marts/episodic_content/schema.yml`:
```yaml
- name: fact_episode
  columns:
    - name: episode_key
      tests: [unique, not_null]
    - name: season_number
      tests:
        - not_null:
            severity: warn
    - name: episode_number
      tests:
        - not_null:
            severity: warn
```

#### O3. Fix fact_title_principal DQ SQL

**Current:** `count(DISTINCT tconst, ordering)` — binder error: "tconst not found"  
**Fix in** DQ config: Replace `tconst` with `title_key` to match Gold schema column name. This unblocks the 4 failed PK tests noted in the external Architecture Review.

#### O4. Add Silver FK Pre-checks

**Current:** 7,649 orphan nconst flow into Gold fact_performance with no FK constraint.  
**Fix in** `silver/fk_checks.py`: Add `fact_performance.nconst → dim_person.nconst` check before Gold materialization. Quarantine orphan rows.

#### O5. Document 89-Row nconst Delta

**Current:** External review flagged this as suspicious; we reproduced it.  
**Fix:** Add a note in `schema_dictionary.md` explaining that SCD2 deduplication on name_basics filters rows where all fields match an existing current record (no effective change). This is intentional.

#### O6. Generate _MANIFEST.json

**Current:** Missing from `marts/full/`.  
**Fix:** Re-run `make export` or execute the GoldExportOperator against the existing Postgres instance.

---

### Tier 2 — Configuration & Incremental (moderate effort)

#### O7. Explicit DuckDB Schemas for Bronze Ingestion

**Current:** `all_varchar=true` forces DuckDB to auto-detect and store everything as strings; Silver then re-parses all types.  
**Fix in** `orchestration/operators/bronze_operator.py`:

```python
bronze_schemas = {
    "title.basics": {
        "columns": {
            "tconst": "VARCHAR",
            "titleType": "VARCHAR",
            "primaryTitle": "VARCHAR",
            "originalTitle": "VARCHAR",
            "isAdult": "VARCHAR",
            "startYear": "VARCHAR",
            "endYear": "VARCHAR",
            "runtimeMinutes": "VARCHAR",
            "genres": "VARCHAR",
        }
    },
    # ... similar for all 7 sources
}
```

**Impact:** DuckDB skips type inference and reads TSV raw into Parquet faster. Targets 47m → <15m.

**Implementation note:** Per the external review (Advisor #3), DuckDB benchmarks show CSV reads at gigabytes/second. The 47-minute bottleneck on 4.5 GB indicates the current `all_varchar=true` path is not the limiting factor — the 3 GB memory limit and `threads=2` constraint on the AMD 200GE is the real bottleneck. On this hardware, expect improvement to ~20-25 min rather than <3 min.

#### O8. Tune dbt Threads

**Current:** `profiles.yml` sets `threads: 2`.  
**Fix:** Increase to `threads: 4`. The AMD 200GE has 4 logical threads (2C/4T). Postgres can handle 4 concurrent connections.

```yaml
outputs:
  prod:
    threads: 4
  dev:
    threads: 4
```

**Impact:** More concurrent model execution in the same dbt DAG. Target: 63m → ~40-45m.

#### O9. Convert High-Volume Marts to Incremental

**Current:** All 6 marts use `materialized='table'`, full rebuild every run.  
**Fix:** Convert `fact_performance`, `fact_title_principal`, and `dim_title` to `incremental`:

```sql
{{ config(
    materialized='incremental',
    unique_key='title_key',
    on_schema_change='append_new_columns'
) }}

SELECT ... FROM {{ ref('int_title_details') }}

{% if is_incremental() %}
  WHERE last_refreshed > (SELECT max(last_refreshed) FROM {{ this }})
{% endif %}
```

**Impact:** Only new/changed rows processed on incremental runs. On first run behaves like `table`. Target: 63m → ~25-30m for incremental.

#### O10. Materialize Actor Co-occurrence

**Current:** Self-join on 100M-row fact_performance takes 30s.  
**Fix:** Create new dbt model `agg_actor_cooccurrence`:

```sql
{{ config(materialized='table') }}

SELECT
  a.nconst AS actor_a,
  b.nconst AS actor_b,
  a.tconst AS shared_title,
  a.category AS role_a,
  b.category AS role_b,
  count(*) AS weight
FROM fact_performance a
JOIN fact_performance b
  ON a.tconst = b.tconst AND a.nconst < b.nconst
WHERE a.category IN ('actor', 'actress')
  AND b.category IN ('actor', 'actress')
GROUP BY a.nconst, b.nconst, a.tconst, a.category, b.category
```

**Impact:** Pre-computes the co-occurrence once per pipeline run. Query time goes from 30s to < 1s.

#### O11. Add Composite FK Indexes on Gold Fact Tables

**Current:** Individual indexes on `title_key` and `name_key` but not composite.  
**Fix in** Postgres after dbt run:

```sql
CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_performance_title_name
  ON gold.fact_performance(title_key, name_key);

CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_fact_episode_series_season
  ON gold.fact_episode(series_key, season_number, episode_number);
```

**Impact:** Reduces hash join probe time for multi-key joins.

---

### Tier 3 — Architectural (structural change, highest payoff)

#### O12. Consolidate Silver+Gold into DuckDB-native Pipeline

**Current architecture:** TSV → DuckDB(Parquet) → CSV → psycopg2(Postgres) → dbt(Postgres) → DuckDB(Parquet export)

The 3-stage Postgres detour (Silver load → Gold build → Gold export) adds ~4.5h to the pipeline. DuckDB can do all Silver transformations and Gold star-schema builds in-memory on the 16 GB machine, writing directly to Parquet.

**Proposed architecture:**
```
TSV → DuckDB(Bronze Parquet) → DuckDB(Silver transformations) → DuckDB(Gold star-schema) → Gold Parquet
```

**Implementation steps:**
1. Port Silver SCD2 logic from SQL + psycopg2 to pure DuckDB SQL
2. Port dbt Gold models to DuckDB SQL in a single `build_gold.py` script
3. Remove Postgres dependency from the core pipeline (keep for serving/BI)

**Impact:** Eliminates 3h39m Silver ETL + 63m Gold dbt + 15m export. Target: 5.5h → <2h total on the AMD 200GE.

**Risk:** SCD2 merge in DuckDB requires careful `UPDATE` + `INSERT` implementation (DuckDB 1.2 supports `INSERT OR REPLACE` but not full `MERGE`).

#### O13. Implement Watermark-Based Incremental Loads

**Current:** Full pipeline rerun reprocesses all 210M rows from scratch.  
**Fix leverage existing watermark.py:** Use `bronze/watermark.py`'s JSON persistence to track last successful run. Bronze ingestion only processes new/missing TSV files (IMDb publishes nightly dumps). Silver SCD2 only processes new Bronze partitions.

**Impact:** Incremental runtime on a 2C/4T machine: ~45 min instead of 5.5h.

#### O14. Partition Large Fact Tables

**Current:** 100M-row fact_performance with no partition pruning.  
**Fix:** Partition by `title_type` (or a year-bucket derived from the title join) in the Parquet export. DuckDB supports Hive-partitioned writes:

```python
con.execute("""
  COPY (
    SELECT * FROM fact_performance
  ) TO 'marts/full/fact_performance'
  (FORMAT PARQUET, PARTITION_BY (title_type), COMPRESSION SNAPPY)
""")
```

**Impact:** Partition pruning reduces scan by 40-60% for type-filtered queries.

---

## Implementation Sequence

```
Week 1 — Tier 1 (zero-cost fixes)
├── Fix fact_performance PK grain (schema.yml)
├── Fix fact_episode PK grain (schema.yml)
├── Fix fact_title_principal DQ SQL
├── Add FK pre-check to silver/fk_checks.py
├── Document 89-row delta
└── Generate _MANIFEST.json (make export)

Week 2 — Tier 2 (configuration + incremental)
├── Tune dbt threads → 4
├── Add explicit Bronze schemas to DuckDB read_csv
├── Convert 3 high-volume marts to incremental
├── Add composite FK indexes
├── Materialize actor co-occurrence
└── Benchmark: profile runtime improvement

Week 3 — Tier 3 (architectural, optional)
├── Design DuckDB-native Silver transformations
├── Port dbt Gold models to DuckDB SQL
├── Implement incremental watermark logic
├── Add partition-by-title_type to Parquet export
└── End-to-end benchmark vs baseline
```

---

## Expected Cumulative Impact

| Metric | Baseline | After T1 | After T2 | After T3 |
|--------|----------|----------|----------|----------|
| Bronze ingestion | 47 min | 47 min | ~20 min | ~15 min |
| Silver ETL | 3h 39m | 3h 39m | 3h 39m | ~30 min |
| Gold dbt | 63 min | 63 min | ~35 min | ~15 min |
| Gold export | 15 min | 15 min | 15 min | ~2 min |
| **Total DE** | **~5h 36m** | **~5h 36m** | **~4h 49m** | **~1h 2m** |
| Actor co-occurrence | 30.5 s | 30.5 s | < 1 s | < 1 s |
| False PK warnings | 3.9M "dupes" | 0 | 0 | 0 |
| DQ test failures | 4 (SQL errors) | 0 | 0 | 0 |

---

## Measurable Success Criteria

1. All 6 Gold fact tables have valid, enforceable PKs (0 duplicates by declared grain)
2. All DQ SQL tests execute without binder errors
3. Actor co-occurrence query completes in < 2 seconds
4. Gold export produces `_MANIFEST.json` with file count, checksums, and row counts
5. Pipeline runtime < 4 hours after Tier 2 (vs 5h36m baseline)
6. Runtime delta between Bronze and Gold row counts documented and < 0.001% (excluding intentional filters)
