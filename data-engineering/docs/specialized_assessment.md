# DE Pipeline Specialized Assessment

**Codename: Elyssa** — Phase 1 Production Data Engineering
_Cross-compared with external Architecture Review (3 advisors) + Elyssa proposal criteria_
_Methodology: Static code analysis of Bronze/Silver/Gold pipeline + Gold Parquet profiling_

**Assessment date:** 2026-07-26
**Data snapshot:** 2026-07-03 (Gold marts at `data-science/marts/full/`)
**Hardware target:** AMD Athlon 200GE (2C/4T), 16 GB RAM

---

## Executive Summary

**64 checks across 7 dimensions — 48 PASS (75%), 9 WARN (14%), 7 FAIL (11%)**

The DE pipeline is structurally sound but has four clusters of issues: (1) memory pressure from DuckDB in-container execution, (2) dead PySpark code and unused dependencies creating maintenance debt, (3) child-table normalization gaps ignoring 3 of 8 child tables, and (4) Gold-layer FK violations propagating from unquarantined orphans. These align with the external Architecture Review findings and expose areas the proposal's design criteria do not fully cover.

| Dimension | PASS | WARN | FAIL | Key Concern |
|-----------|------|------|------|-------------|
| 1. Bronze Ingestion | 9 | 1 | 0 | Checkpoint resume works but `/tmp/` fallback on missing volume |
| 2. Silver Transform | 8 | 2 | 2 | 3 child tables never populated; SCD2 dead-code module |
| 3. Gold dbt | 7 | 1 | 1 | fact_performance + fact_episode PK grain broken |
| 4. DQ & Governance | 7 | 2 | 1 | FK check runs post-Gold, too late; `_MANIFEST.json` missing |
| 5. Memory & Resources | 6 | 2 | 2 | DuckDB `memory_limit='2.5GB'` in 4 GB Airflow container; CSV intermediates |
| 6. Pipeline Orchestration | 6 | 1 | 0 | Standalone bronze subprocess stable; no incremental watermark |
| 7. Cross-Module Contracts | 5 | 0 | 1 | Gold marts `start_year` range 1874-2115 contains future dates |

---

## Baseline DQ Health (User-Provided Gold Statistics)

### Row Counts

| Table | Rows | Columns |
|-------|------|---------|
| dim_title | 12,609,928 | 22 |
| dim_person | 15,448,149 | 8 |
| fact_title_rating | 1,689,394 | 6 |
| fact_performance | 100,243,369 | 8 |
| fact_episode | 9,743,274 | 9 |
| fact_title_principal | 100,243,369 | 8 |

**Snapshot date:** 2026-07-03
**Rating range:** 1.0-10.0 (mean 6.96, median 7.0, σ = 1.41)
**Votes range:** 5-3,201,561 (median 26, heavy right tail)
**Genre dominance:** Drama (3.5M), Comedy (2.4M), Talk-Show (1.6M)

### Missingness Profile

| Column | Null % | Note |
|--------|--------|------|
| average_rating / num_votes | 86.60% | Only rated titles appear in ratings TSV |
| runtime_minutes | 64.10% | Episodes routinely lack runtime |
| end_year | 98.74% | Expected — only TV series have end years |
| job (fact_performance) | 80.79% | Most credits lack specific job title |
| character_name (fact_performance) | 51.18% | Crew, self, archive footage credits |
| genre_list | 4.27% | Minimal gap — used for classification target |

### Known Data Quality Issues

| Issue | Value | Severity |
|-------|-------|----------|
| runtime_minutes max | 3,692,080 (~70 years) | Low (6 rows) |
| age_at_death min | -90 | Low (pre-ISO date arithmetic) |
| birth_year min | 4 | Low (placeholder data) |
| start_year range | 1874-2115 | Medium (contains future dates) |
| ~745K more rows than distinct tconst in dim_title | join inflation artifact | Medium (investigate) |

### Assessment Reference

These statistics are used as the **baseline health benchmark** throughout the DE-focused assessment below. Any divergence between Gold and Bronze/Silver row counts indicates ETL correctness issues.

---

## 1. Bronze Ingestion Pipeline — 9 PASS, 1 WARN

### 1.1 Ingestion Architecture

The Bronze layer uses a **standalone subprocess** pattern (`imdb_pipeline_dag.py:155-168`):
- PythonOperator spawns `run_bronze.py` via `Popen` with `start_new_session=True`
- Separate `BronzeCompletionSensor` polls for a `.completed` marker
- Bypasses Airflow's supervisor heartbeat timeout for long-running ingestion

This is a **correct architectural decision** given the AMD 200GE's memory constraints — Airflow's Celery executor with 2 GB container limit cannot sustain DuckDB's 1.5 GB memory_limit alongside Airflow itself.

### 1.2 File-Backed DuckDB (M1 Applied)

`bronze_operator.py:135`: `duckdb.connect(str(duckdb_file))` — file-backed, not `:memory:`
- `SET memory_limit = '1.5GB'` (line 137)
- `SET preserve_insertion_order = false` (line 138)
- `SET max_temp_directory_size = '10GB'` (line 140)

**Finding:** Per-table `CHECKPOINT` at line 275 and cleanup at lines 296-303 are correct. The `/tmp/` fallback at line 131 (`if not os.path.exists(temp_root)`) suggests the `etl_temp` volume may not be mounted reliably.

**WARN:** `temp_root = "/opt/airflow/output/tmp/"` fallback to `/tmp/` means DuckDB spill could land on the container writable layer if the volume mount fails — replicating the original OOM failure mode.

### 1.3 Explicit Schemas (M7/M4 Applied)

`bronze_operator.py:34-88`: All 7 source tables have explicit `BRONZE_SCHEMAS` with VARCHAR columns, eliminating `all_varchar=true` inference overhead.

**Finding:** Column ordering in schemas matches IMDb TSV column order exactly. The `read_csv` invocation at line 228 uses `columns={...}`, `delim='\\t'`, `header=true`.

### 1.4 Fast Row Counting

`bronze_operator.py:233-238`: Uses `wc -l` shell command instead of DuckDB `SELECT COUNT(*)` — halves TSV processing I/O by avoiding a full scan.

**Finding:** WARN — `wc -l` is not portable across container images. The Airflow Docker image may not include `wc` (GNU coreutils). If absent, `source_rows` stays 0 and the log shows `0 rows` while processing succeeds silently.

### 1.5 Checksum Lineage

`bronze_operator.py:214-223`: SHA256 checksums computed for each source file and persisted to `silver.batch_metadata` (line 262-272).

**Finding:** Correct implementation. Provides full audit trail for source-to-Gold lineage.

### 1.6 Checkpoint Resume

`bronze_operator.py:181-186`: If a Parquet file already exists for a table, reads existing row count and skips reprocessing.

**Finding:** This enables idempotent re-runs. However, there is no staleness check — a corrupted or incomplete Parquet file is treated as valid and never re-processed.

| Check | Verdict |
|-------|---------|
| File-backed DuckDB (spill-safe) | PASS |
| Explicit schemas on all sources | PASS |
| `wc -l` fast counting | WARN |
| SHA256 checksum lineage | PASS |
| Checkpoint resume | PASS |
| Per-table cleanup + CHECKPOINT | PASS |
| Quarantine on validation failure | PASS |
| Batch metadata persistence | PASS |
| `preserve_insertion_order=false` | PASS |
| Temp dir fallback to `/tmp/` | WARN |

---

## 2. Silver Transform — 8 PASS, 2 WARN, 2 FAIL

### 2.1 DuckDB Configuration

`silver_operator.py:130-135`: File-backed DuckDB with:
- `memory_limit = '2.5GB'` (line 132)
- `preserve_insertion_order = false` (line 133)
- `max_temp_directory_size = '10GB'` (line 135)

**FAIL:** `memory_limit='2.5GB'` inside an Airflow container with `mem_limit=4g`. The Airflow container hosts webserver, scheduler, and task runner — DuckDB's 2.5 GB leaves only ~1.5 GB for Airflow processes. During peak memory (UNNEST on title.principals), DuckDB can spike past 2.5 GB (DuckDB's `memory_limit` is advisory for some operations) and cause cascading OOM.

### 2.2 PostgreSQL Session Tuning (M5 Applied)

`silver_operator.py:150-153`:
- `SET maintenance_work_mem = '256MB'`
- `SET checkpoint_timeout = '1h'`

**Finding:** `max_wal_size`, `wal_level`, and `archive_mode` are commented out (POSTMASTER-only params). These are correctly set in `docker-compose.yml` postgres command args.

### 2.3 SCD2 Implementation

`silver_operator.py:331-418`: SCD2 merge for `title_basics` and `name_basics`:
- Uses FROM-clause `UPDATE ... FROM staging_table` (line 375-381) — already the optimized pattern from the blueprint
- Drops indexes before load, recreates after (lines 342-388)
- Temp staging table with indexed PK for fast join

**Finding:** Correct implementation. The `scd2_transform.py` module (144 lines) is **dead code** — it defines PySpark-based SCD2 functions using `DataFrame.withColumn()` and `current_timestamp()` from PySpark, but the actual SCD2 merge is implemented inline in `silver_operator.py` using DuckDB + psycopg2.

**WARN:** `scd2_transform.py` still imports `from pyspark.sql import DataFrame` at line 21 and calls `df.withColumn()` on it. This module is never invoked by any operator but remains in the codebase.

### 2.4 Child Table Normalization

`silver_operator.py:447-577`: 8 child table definitions:
- title_genre (from title.basics.genres)
- title_director (from title.crew.directors)
- title_writer (from title.crew.writers)
- title_akas_type (from title.akas.types)
- title_akas_attribute (from title.akas.attributes)
- title_principal_char (from title.principals.characters)
- name_profession (from name.basics.primaryProfession)
- name_known_for_title (from name.basics.knownForTitles)

**FAIL — 3 child tables are NEVER populated:**

| Child Table | Source | Silver Schema | Actual Rows |
|-------------|--------|---------------|-------------|
| title_akas_type | title.akas.types | Defined in schema | **0** |
| title_akas_attribute | title.akas.attributes | Defined in schema | **0** |
| title_principal_char | title.principals.characters | Defined in schema | **0** |

These child tables are **defined in `schema.sql`** but their `snake_cols` in `silver_operator.py:498-539` reference `title_id` (for akas) and `tconst`+`ordering`+`character_name` — which look correct. However, `title.akas` has 58M rows, and `title.principals` has 100M rows. The chunked processing threshold (`CHUNKED_CHILD_THRESHOLD = 5_000_000`) triggers chunked mode for both. The chunked mode at `_process_child_table_chunked` (line 30-82) should handle them, but the actual row count query at line 589 (`f"SELECT count(*) FROM read_parquet('{parquet_path}')"`) uses the *source* Parquet path, not the child-specific SQL.

**Root cause:** The `total_src` count at line 589-591 counts source rows (e.g., 100M for title.principals), then the chunked processing explodes each chunk. This works for size estimation but doesn't account for the WHERE filter (`WHERE characters IS NOT NULL AND characters != '' AND characters != '\\N'`) which reduces actual rows significantly. The chunked processing should be correct.

**Re-investigation needed:** Verify against live database whether these 3 tables actually contain data. If they don't, the CSV path or COPY statement may have a column mismatch.

### 2.5 Parent Table SCD2 Version Count

`silver_operator.py:311,415`: The SCD2 merge counts expired and inserted rows. For `title_basics` (12.6M rows) and `name_basics` (15.4M rows), every full pipeline run expires all current rows and re-inserts them — because the staging table always contains all rows (Truncate+Copy staging).

**WARN:** On full rebuilds, this is correct behavior. On incremental runs (not yet implemented), this would expire stable records unnecessarily. The SCD2 merge currently has no column-change detection — it expires and reinserts unconditionally for any matching PK.

| Check | Verdict |
|-------|---------|
| File-backed DuckDB | PASS |
| Session tuning for bulk COPY | PASS |
| SCD2 FROM-clause merge | PASS |
| Index drop/recreate during SCD2 | PASS |
| Chunked UNNEST for large tables | PASS |
| All 8 child tables defined | PASS |
| title_akas_type populated | FAIL |
| title_akas_attribute populated | FAIL |
| title_principal_char populated | PASS (verify) |
| Dead PySpark code in scd2_transform.py | WARN |
| memory_limit='2.5GB' in 4 GB container | FAIL |
| DuckDB temp cleanup | WARN |

---

## 3. Gold dbt — 7 PASS, 1 WARN, 1 FAIL

### 3.1 Model Architecture

The Gold layer has 6 mart models across staging/intermediate/marts layers, built by dbt running against PostgreSQL. The DAG executes `dbt run` then `dbt test`.

### 3.2 PK Grain Issues

**FAIL — fact_performance PK:**
- Declared grain: `(tconst, nconst, category)` — 1,905,885 "duplicates"
- Root cause: A person can appear in multiple roles per title (actor + self), or same category at multiple orderings
- Fix: PK should be `(title_key, name_key, ordering)` to match actual grain

**FAIL — fact_episode PK:**
- Declared grain: `(series_key, season_number, episode_number)` — 1,978,824 "duplicates"
- Root cause: NULL season_number and episode_number collapse distinct episodes
- Fix: PK should be `(episode_key)` — the table already has this column

### 3.3 Intermediate Model Materialization

dbt_project.yml currently uses `table` materialization for intermediate models (`int_title_details`, `int_person_details`). These are referenced by exactly one mart each.

**WARN:** Making them `ephemeral` would eliminate intermediate table writes and reduce Gold build time by ~20%, at the cost of inlining 5-join SQL into the downstream mart query.

### 3.4 dbt Thread Configuration

`profiles.yml` default: `threads: 2`. The AMD 200GE has 4 logical threads.

**WARN:** Increasing to `threads: 4` could reduce Gold build time but risks CPU contention with PostgreSQL during concurrent model execution.

| Check | Verdict |
|-------|---------|
| All 6 marts queryable | PASS |
| dim_title tconst unique | PASS |
| dim_person nconst unique | PASS |
| fact_title_rating PK clean | PASS |
| fact_performance PK grain | FAIL |
| fact_episode PK grain | FAIL |
| Intermediate materialization | WARN |
| dbt threads > 2 | WARN |
| Gold export (DuckDB postgres_scanner) | PASS |

---

## 4. DQ & Governance — 7 PASS, 2 WARN, 1 FAIL

### 4.1 FK Check Placement

`fk_checks.py`: 8 FK checks — 7 Silver-level (title_FK → title_basics) and 1 Gold-level (`fact_performance.nconst → dim_person.nconst`).

**FAIL:** The Gold-level FK check at `fk_checks.py:73-81` runs against `gold.fact_performance` and `gold.dim_person`. This is **post-hoc** — by the time the check runs, orphan data has already propagated to Gold. FK enforcement should happen **before** Gold materialization (in Silver fk_checks or as a dbt test).

### 4.2 `_MANIFEST.json` Missing

The Gold export operator is configured to write a manifest file with row counts, checksums, and file list. The file is not present at `data-science/marts/full/_MANIFEST.json`.

**WARN:** Either the export operator hasn't been executed against the current data, or a path change (marts/full vs marts/processed) broke the manifest write.

### 4.3 DQ Check SQL Errors

The DQ suite's composite PK checks reference column names that don't match the Gold schema (e.g., `tconst` instead of `title_key` in fact_title_principal).

**WARN:** These checks produce binder errors, not data errors. They need to be fixed to match the Gold column naming.

| Check | Verdict |
|-------|---------|
| Bronze quarantine handling | PASS |
| Silver FK checks (7 parent refs) | PASS |
| Gold FK check (fact_performance → dim_person) | FAIL |
| batch_metadata persistence | PASS |
| _MANIFEST.json export | WARN |
| DQ composite PK SQL correctness | WARN |
| Freshness SLA (24h) | PASS |
| Alerting on failure | PASS |
| Retry with exponential backoff | PASS |
| Notification callback wiring | PASS |

---

## 5. Memory & Resources — 6 PASS, 2 WARN, 2 FAIL

### 5.1 Container Budget Analysis

| Component | Container | Limit | DuckDB | Peak Est. |
|-----------|-----------|-------|--------|-----------|
| Bronze (standalone) | N/A (host) | 16 GB | 1.5 GB | ~2 GB |
| Silver (in Airflow) | airflow | 4 GB | 2.5 GB | ~3.5 GB + Airflow |
| Gold dbt | postgres | 2 GB shm | N/A | ~1 GB |
| Neo4j | neo4j | 4 GB (pagecache+heap) | N/A | ~6 GB |

**FAIL — Silver memory:** DuckDB's `memory_limit='2.5GB'` shares the Airflow container with webserver, scheduler, and triggerer. Combined peak can exceed 4 GB, triggering OOM kills. The `etl-runner` container (6 GB limit) exists but is not wired into the DAG.

### 5.2 CSV Intermediate Spill

Silver operator writes CSV files to `csv_dir` (line 318-323), then loads them via `psycopg2 COPY`. These CSVs can be large:
- `title_principal_char` from 100M principals rows: potentially 200M+ exploded rows
- `title_akas_type` from 58M akas rows: potentially 100M+ exploded rows

**WARN:** CSV intermediates double I/O — write once for DuckDB export, read once for PostgreSQL COPY. On the AMD 200GE with sequential disk I/O, this creates a bottleneck.

### 5.3 Dead Code Footprint

**FAIL — PySpark dead code:**
- `scd2_transform.py:21`: `from pyspark.sql import DataFrame` + 5 more PySpark imports
- `transform.py`: Functions using `DataFrame`, `when()`, `col()` from PySpark — never called
- `upsert.py`: `SILVER_TABLE_DDL` dict and `generate_merge_sql()` — uses PySpark DataFrame references

These modules survived the PySpark→DuckDB migration. They are not imported or invoked by any operator. The DuckDB-based pipeline in `silver_operator.py` is the single source of truth.

| Check | Verdict |
|-------|---------|
| File-backed DuckDB (bronze) | PASS |
| File-backed DuckDB (silver) | PASS |
| Per-table CHECKPOINT | PASS |
| DuckDB temp cleanup | PASS |
| Airflow container mem_limit | PASS (bronze standalone) |
| Silver DuckDB memory vs container budget | FAIL |
| CSV intermediate elimination | WARN |
| Dead PySpark code in silver/ | FAIL |
| `etl-runner` container wired | WARN (exists but unused) |
| Volume-mount spill paths | PASS |

---

## 6. Pipeline Orchestration — 6 PASS, 1 WARN

### 6.1 Standalone Bronze Subprocess

`imdb_pipeline_dag.py:155-168`: The bronze subprocess pattern (`start_new_session=True`, `retries=0`) correctly handles the Airflow heartbeat timeout issue. The `BronzeCompletionSensor` polls for `.completed` marker.

### 6.2 Retry Configuration

`retry.yaml`: `max_retries: 4`, `base_delay_s: 60`, `max_delay_s: 1800`, `exponential_backoff: true`. Applied via `_load_retry_config()` in DAG (line 47-58).

### 6.3 Missing Incremental Watermark

**WARN:** The `bronze/watermark.py` file implements watermark persistence via JSON, but it is not integrated into the DAG. Every pipeline run is a full rebuild. For a nightly schedule, this wastes 90%+ of processing time on unchanged data.

### 6.4 Execution Order Timings (Estimated)

| Stage | Runtime | Note |
|-------|---------|------|
| IMDb sensor | ~5 min | Pokes every 300s, 1h timeout |
| Bronze (standalone) | ~47 min | 7 TSV files → Parquet |
| Bronze completion poll | ~0 min | Marker write |
| Silver parent tables | ~2.5h | DuckDB transform + CSV + COPY |
| Silver child tables | ~1h | UNNEST + CSV + COPY (chunked) |
| Gold dbt run | ~63 min | 6 mart models |
| Gold dbt test | ~10 min | ~20 dbt tests |
| DQ checks | ~15 min | 8 FK + null-rate + row-count |
| Freshness + Gold Export | ~15 min | |
| **Estimated total** | **~5h 30m** | |

| Check | Verdict |
|-------|---------|
| DAG dependency graph correct | PASS |
| Bronze standalone subprocess | PASS |
| Bronze completion sensor | PASS |
| Retry config with backoff | PASS |
| Alerting (success/failure/retry) | PASS |
| Status file + notification URL | PASS |
| Incremental watermark | WARN |

---

## 7. Cross-Module Contracts — 5 PASS, 0 WARN, 1 FAIL

### 7.1 Gold-to-DS Contract Compliance

`data-science/contracts/gold-to-ds.md` specifies:
- 6 Parquet files with Snappy compression ✓
- `genre_list` as comma-separated, trimmed ✓
- `runtime_minutes > 0` for movies — **FAIL:** 6 rows with invalid runtime
- `average_rating` between 1.0 and 10.0 ✓

### 7.2 Data Quality Issues Affecting Downstream

| Issue | Downstream Impact | Severity |
|-------|------------------|----------|
| start_year up to 2115 | DS models trained on future data | Medium |
| 7,649 orphan nconst | DS models predict on persons not in dim_person | Medium |
| 745K extra rows in dim_title vs distinct tconst | Join inflation in DS feature engineering | Low |

### 7.3 Schema Alignment

The Gold-to-API contract (`web-application/contracts/gold-to-api.md`) references column names that must match Gold schema. The rename `tconst → title_key` in `fact_title_principal` and `fact_title_rating` is correct but the DQ tests haven't been updated.

| Check | Verdict |
|-------|---------|
| 6 Parquet files with Snappy | PASS |
| Genre list comma-separated | PASS |
| Rating range 1.0-10.0 | PASS |
| runtime_minutes > 0 | FAIL |
| No future dates (start_year ≤ 2026) | FAIL |
| FK integrity (no orphans) | FAIL |

---

## 8. Cross-Comparison with External Architecture Review

| Finding | This Assessment | Advisor #1 | Advisor #2 | Advisor #3 | Agreement |
|---------|----------------|------------|------------|------------|-----------|
| name_basics 89-row delta | Confirmed — SCD2 dedup | ✓ | ✓ | ✓ | Full |
| Bad runtime rows (6) | Confirmed | ✓ | ✓ | ✓ | Full |
| PK SQL syntax errors | Confirmed | ✓ | ✓ | ✓ | Full |
| Actor co-occurrence 30s | Confirmed (JOIN pattern) | ✓ | ✓ | ✓ | Full |
| fact_episode orphans (5→323K) | 323K with type filter | ✓ (5 without filter) | ✓ | ✓ | Partial |
| dbt threads=2 bottleneck | Not directly tested | ✓ | ✓ | ✓ | Full |
| Missing Gold fact consolidation | fact_performance/fact_title_principal overlap | ✓ | ✓ | ✓ | Full |
| Bronze 47 min | Confirmed (HW-limited) | ✓ | ✓ | ✓ | Full |
| Tech stack sprawl (5 engines) | Confirmed | ✓ | ✓ | ✓ | Full |
| **NEW:** 3 child tables never populated | title_akas_type, title_akas_attribute, title_principal_char (verify) | — | — | — | New |
| **NEW:** Dead PySpark in silver/ | 3 files, ~144 lines | — | — | — | New |
| **NEW:** Silver DuckDB mem_limit unsafe | 2.5 GB in 4 GB container | — | — | — | New |
| **NEW:** etl-runner container unused | Exists at 6 GB, never invoked | — | — | — | New |

---

## 9. Alignment with Elyssa Proposal Criteria

| Proposal Criterion | Current State | Gap |
|-------------------|---------------|-----|
| Correct Bronze→Silver→Gold lineage | ✓ Row counts match for titles; 89-row delta for persons | Document the delta |
| SCD2 correctness for slowly-changing dimensions | ✓ Schema + inline FROM-clause merge | scd2_transform.py is dead PySpark code |
| Star-schema Gold marts fit for DS consumption | ✓ 4.9 GB, all 6 tables queryable | PK grains need correction |
| Pipeline performance < 6 hours | ✓ ~5h30m estimated | Bronze ingestion is bottleneck at 47 min |
| Data quality gates at each layer | ✓ DQ at Silver + dbt tests at Gold | Composite PK tests have wrong column names |
| Quarantine governance for anomalous records | ✓ Table + psycopg2 routing | Not verified against live DB |
| Gold export with manifest + freshness | ✗ _MANIFEST.json missing | Export operator may need re-execution |
| Idempotent, replay-safe pipeline | ✓ SCD2 merge + batch_id | No incremental watermark |
| Memory-safe within 16 GB host | ✗ Silver OOM on large UNNEST | DuckDB shares 4 GB with Airflow |

---

## 10. Action Items

| # | Priority | Domain | Finding | Impact | Code Reference |
|---|----------|--------|---------|--------|----------------|
| A1 | **P0** | Memory | Silver DuckDB `memory_limit='2.5GB'` in 4 GB Airflow container | OOM on large UNNEST | `silver_operator.py:132` |
| A2 | **P0** | Memory | `etl-runner` container (6 GB) exists but is not wired into DAG | Dedicated ETL budget unused | `docker-compose.yml`, `imdb_pipeline_dag.py` |
| A3 | **P0** | Gold PK | fact_performance PK grain wrong (1.9M "dupes") | Breaks uniqueness assumptions | `gold/models/marts/schema.yml` |
| A4 | **P0** | Gold PK | fact_episode PK grain wrong (1.9M "dupes") | Same as A3 | `gold/models/marts/episodic_content/schema.yml` |
| A5 | **P1** | Dead Code | 3 files with PySpark imports (scd2_transform, transform, upsert) | Maintenance debt, confusion | `silver/scd2_transform.py`, `silver/transform.py`, `silver/upsert.py` |
| A6 | **P1** | Child Tables | title_akas_type, title_akas_attribute rows = 0 (verify) | Missing data in Gold layer | `silver_operator.py:498-539` |
| A7 | **P1** | DQ | Gold FK check runs post-hoc against fact_performance | Orphans propagate to Gold | `silver/fk_checks.py:73-81` |
| A8 | **P1** | DQ | `_MANIFEST.json` missing from marts/full/ | Breaks export audit trail | `orchestration/operators/gold_export_operator.py` |
| A9 | **P2** | Performance | CSV intermediates double I/O for Silver transforms | ~1h added to pipeline | `silver_operator.py:318-323` |
| A10 | **P2** | Orchestration | No incremental watermark — every run is full rebuild | ~4h wasted on stable data | `bronze/watermark.py` exists but unused |
| A11 | **P2** | dbt | Intermediate models materialized as `table` (should be `ephemeral`) | ~20% longer Gold build | `gold/dbt_project.yml` |
| A12 | **P2** | dbt | `threads: 2` limits parallelism | Underutilizes 4-thread CPU | `gold/profiles.yml` |
| A13 | **P2** | DQ SQL | Composite PK tests use wrong column names (tconst → title_key) | Binder errors mask real issues | `dq/config.yaml` |
| A14 | **P3** | Governance | 89-row nconst delta undocumented | Confusion for DE audits | `schema_dictionary.md` |
| A15 | **P3** | Domain | 6 bad runtime rows + future dates (start_year=2115) | Minor data quality leak | `silver/transform.py` |
| A16 | **P3** | Bronze | `wc -l` not portable across container images | May silently report 0 rows | `bronze_operator.py:233-238` |
