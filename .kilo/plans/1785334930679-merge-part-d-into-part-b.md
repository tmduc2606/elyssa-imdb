# Plan: Merge Part D into Part B — Gold Marts Benchmark

## Goal

Merge `Part D — Exhaustive Bronze vs Silver vs Gold Layer Assessment` into `Part B — Gold Marts Benchmark` in `data-science/notebooks/phase_2_duke_manual_eda.ipynb`, following the two-strategy pattern from `data-engineering/docs/rustfs_integration_plan.md`.

---

## Layer Registration Order

Reuse Part A's existing DuckDB connection (`imdb_gold.db`). Do **not** create a second connection.

### B.1 — Bronze Registration (7 tables, two-strategy)

For each table in `['title.basics', 'title.akas', 'title.crew', 'title.episode', 'title.principals', 'title.ratings', 'name.basics']`:

1. **Strategy 1:** If `data-science/marts/bronze/{table}.parquet` exists, register view `bronze_{table}` via `read_parquet(...)`.
2. **Strategy 2:** If Strategy 1 fails, install/load `httpfs`, configure S3 settings (`s3_endpoint='rustfs:9000'`, etc.), register view from `s3://imdb-source/{table}.tsv.gz` via `read_csv(... delim='\t' header=True all_varchar=True nullstr='\\N')`.
3. **Failsafe:** If both fail, log WARN and mark table as skipped.

Track which strategy was used per table.

### B.2 — Silver Registration (14 tables, two-strategy)

For each table in `['title_basics', 'title_akas', 'title_crew', 'title_episode', 'title_principal', 'title_rating', 'name_basics', 'title_genre', 'title_director', 'title_writer', 'title_akas_type', 'title_akas_attribute', 'title_principal_char', 'name_profession', 'name_known_for_title']`:

1. **Strategy 1:** If `data-science/marts/silver/{table}.parquet` exists, register view `silver_{table}` via `read_parquet(...)`.
2. **Strategy 2:** If Strategy 1 fails, connect to PostgreSQL (`postgres:5432`, `elyssa_warehouse`, user `elyssa`) via `psycopg2`. Query row count only (`SELECT count(*) FROM silver.{table}`). Register as DuckDB view if needed, or store counts in a dict for reconciliation.
3. **Failsafe:** If both fail, log WARN and mark table as skipped.

### B.3 — Gold Registration

Already done in Part A via `data-science/marts/full/{table}.parquet`. Reuse those views. No fallback needed.

---

## Benchmark Cells

### B.4 — Row Count Reconciliation

Produce `bench` DataFrame entries:
- Row counts for all 7 Bronze tables (from whichever strategy succeeded).
- Row counts for all 14 Silver tables (from whichever strategy succeeded).
- Row counts for all 6 Gold mart tables.
- Cross-layer ratios: `Silver/Bronze`, `Gold/Bronze`, `Gold/Silver` where both sides exist.
- Flag WARN if ratio < 95% or > 105%.
- If an entire layer is unavailable, record a single WARN entry like `"Bronze layer unavailable"` instead of per-table skips.

### B.5 — ETL Correctness (Enhanced)

Keep existing Part B checks, add Silver-aware comparisons when Silver is available:
- Distinct `tconst`/`nconst` counts across Bronze → Silver → Gold.
- Rating consistency: Bronze ratings vs Gold `dim_title.average_rating` (already in Part B).
- Referential integrity: `fact_episode.series_key` → `dim_title.tconst` (already in Part B).

### B.6 — Intrinsic Quality (Enhanced)

Merge Part D's DQ anomaly detection into existing Intrinsic Quality section:
- Out-of-range `start_year` ([1874, 2115]).
- Extreme `runtime_minutes` (> 1000 min).
- Unrealistic `birth_year` ([1800, current_year]).
- `death_year` < `birth_year`.
- Orphaned episode parents (`fact_episode.parent_tconst` → `dim_title.tconst`).
- Keep existing checks: PK uniqueness, format validity, `is_adult` range, `title_type` categorical set, `end_year >= start_year`.

### B.7 — Completeness & Null-Rate Summary

- **MANIFEST.json:** Read `data-science/marts/full/_MANIFEST.json`. Compare declared `row_counts` against actual Parquet row counts. WARN if drift > 1%.
- **Null-rate summary:** Per Gold mart, list columns with null rate > 5%.
- Keep existing Part B null checks for key columns.

### B.8 — Fitness for Use (Retained)

Keep existing Part B checks: query-speed tests, volume-sanity minimums, freshness (`max(start_year)`), key-genre presence.

### B.9 — Benchmark Summary Output

Single `bench` list-of-dicts populated throughout B.4–B.8. Render `df_bench` once at the end. No standalone print blocks.

---

## Cells to Remove

- Part D markdown header and all Part D code cells (D.1–D.8).
- Part B's duplicate Bronze TSV registration cell (replaced by unified B.1).

---

## Validation

1. Run notebook end-to-end with Gold Parquet present (Later with the user approval).
2. Verify `bench` DataFrame contains rows from ETL, Intrinsic, and Fitness sections.
3. Verify graceful skip when Silver/PostgreSQL is unavailable (no hard failures).
4. Verify graceful skip when Bronze local cache is absent (falls back to S3 or logs skip).
5. Verify `httpfs` is installed/loaded before any S3 reads.

---

## Important Constraints

- Never read from live database outside the two-strategy fallback pattern.
- Never break temporal splits (TRAIN < 2015, VAL 2015-2018, TEST 2019+).
- Never load full tables into memory — use DuckDB pushdown or `TABLESAMPLE`.
- Silver fallback queries are **row counts only** (no sample rows or schema pulls).
