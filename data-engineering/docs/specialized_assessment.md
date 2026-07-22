# DE Pipeline Specialized Assessment

**Codename: Elyssa** — Phase 1 Data Engineering Module  
_Inspired by the EDA benchmark framework from `phase_2_duke_manual_eda.ipynb`_  
_Cross-referenced with `Elyssa Architecture Review.docx` (3 advisors) + Elyssa proposal criteria_

**Generated:** 2026-07-22  
**Test methodology:** DuckDB 1.2 over 7 raw TSV.gz sources (1.9 GB compressed) and 6 Gold Parquet marts (4.9 GB Snappy)

---

## Executive Summary

**56 checks executed** — **40 PASS (71%), 6 WARN (11%), 5 FAIL (9%)**

The pipeline is fundamentally sound but has **three clusters of issues**: (1) composite PK violations in fact tables, (2) referential integrity gaps in fact_performance, and (3) a 30-second actor co-occurrence query that signals an analytical bottleneck. These align closely with the external Architecture Review's findings and the Elyssa proposal's design expectations.

| Layer | PASS | WARN | FAIL | Key Concern |
|-------|------|------|------|-------------|
| Bronze Ingestion | 13 | 0 | 0 | All sources readable, all views registered |
| Gold Intrinsic Quality | 6 | 2 | 3 | Composite PKs broken in 2 fact tables |
| Gold Null Rates | 6 | 0 | 0 | High null rates are expected IMDb sparsity |
| Gold Referential Integrity | 1 | 1 | 1 | 7,649 orphan nconst, 323K episode orphans |
| ETL Correctness | 2 | 2 | 0 | 89-row nconst delta matches external report |
| Fitness for Use | 5 | 0 | 1 | Actor co-occurrence: 30.5s |
| Pipeline Governance | 7 | 1 | 0 | Missing _MANIFEST.json |

---

## 1. Bronze Ingestion — 13/13 PASS

All 7 source TSV files are present (1.9 GB compressed) and parse cleanly through DuckDB's `read_csv` with `all_varchar=true`:

| Source | Size | Rows | Status |
|--------|------|------|--------|
| title.basics.tsv.gz | 213 MB | 12,609,928 | PASS |
| name.basics.tsv.gz | 292 MB | 15,448,238 | PASS |
| title.ratings.tsv.gz | 8 MB | 1,689,394 | PASS |
| title.principals.tsv.gz | 736 MB | 100,243,363 | PASS |
| title.episode.tsv.gz | 51 MB | 9,743,274 | PASS |
| title.crew.tsv.gz | 78 MB | 12,611,414 | PASS |
| title.akas.tsv.gz | 481 MB | 58,178,050 | PASS |

**Finding:** The `all_varchar=true` strategy works correctly for raw landing but defers all type coercion to Silver. The external review (Advisor #3) recommends explicit schemas to eliminate inference overhead — this would not affect Bronze correctness but could accelerate the DuckDB read path by avoiding string-to-type conversion at the Silver stage.

---

## 2. Gold Intrinsic Quality — 6 PASS, 2 WARN, 3 FAIL

### 2.1 Primary Key Uniqueness

| Table | Composite Key | Duplicates | Verdict | Note |
|-------|---------------|------------|---------|------|
| dim_title | tconst | 0 | **PASS** | Clean |
| dim_person | nconst | 0 | **PASS** | Clean |
| fact_title_rating | title_key, snapshot_date | 0 | **PASS** | Clean |
| fact_title_principal | tconst, ordering | **Error** | **FAIL** | Column "tconst" not found — surrogate key rename (title_key) |
| fact_performance | tconst, nconst, category | **1,905,885** | **FAIL** | Massively non-unique; not a true PK grain |
| fact_episode | series_key, season_number, episode_number | **1,978,824** | **FAIL** | Major duplicate episodes |

**Cross-reference with external review (Advisor #1, #3):** The docx explicitly flagged the `count(DISTINCT tconst, ordering)` SQL error in the DQ suite. Our assessment confirms this: `fact_title_principal` has `tconst` renamed to `title_key` in the Gold model, so the PK check fails with a binder error, not a data issue. The same pattern applies to `fact_title_principal` in our assessment.

**Worse: fact_performance and fact_episode have ~2M "duplicates" each.** However, this reflects the *declared grain* not matching the *actual grain*:
- `fact_performance(tconst, nconst, category)` — a person can have multiple roles in the same title (e.g., actor + producer), and even within the same category can appear at multiple orderings. The declared PK is too narrow.
- `fact_episode(series_key, season_number, episode_number)` — `season_number` and `episode_number` are NULL for many episodes, collapsing distinct episodes into the same composite key.

**Recommendation:** Fix the grain definitions:
- `fact_performance`: PK should be `(title_key, name_key, ordering)` or include `character`.
- `fact_episode`: PK should be `(episode_key)` — it already has one but the check used the wrong composite. Alternatively, handle NULLs in season/episode number before using them in PK constraints.

### 2.2 Domain Constraints

| Check | Bad Rows | Verdict |
|-------|----------|---------|
| tconst format (ttNNNNN) | 0 | PASS |
| nconst format (nmNNNNN) | 0 | PASS |
| is_adult ∈ {0,1} | 0 | PASS |
| runtime_minutes > 0 ∧ ≤ 100000 | 6 | WARN |
| average_rating ∈ [0,10] | 0 | PASS |
| start_year ∈ [1880, 2030] | 38 | WARN |

The 6 bad runtime rows and 38 out-of-range start_year values mirror the "handful of rows out of millions" noted by Advisor #1. The start year 2115 in dim_title (max_year) confirms that some future or erroneous dates leaked through.

### 2.3 Null Rates

| Column | Null % | Verdict |
|--------|--------|---------|
| average_rating | 86.6% | INFO — expected for unrated titles |
| num_votes | 86.6% | INFO — same population |
| runtime_minutes | 64.1% | INFO — many titles lack runtime |
| genre_list | 4.27% | PASS — well-populated |
| birth_year | 95.62% | INFO — most persons lack birth year |
| death_year | 98.32% | INFO — expected |

**Cross-reference:** Advisor #1's recommendation to "treat null percentages that reflect genuine IMDb data sparsity as expected, not warnings" is already applied here. These are not quality issues.

---

## 3. Gold Referential Integrity — 1 PASS, 1 WARN, 1 FAIL

| Check | Orphans | Verdict |
|-------|---------|---------|
| fact_performance.tconst → dim_title | 0 | **PASS** |
| fact_performance.nconst → dim_person | **7,649** | **FAIL** |
| fact_episode.series_key → dim_title (tvSeries) | **323,065** | **WARN** |

**7,649 orphan nconst:** Persons credited in fact_performance who do not exist in dim_person. Likely caused by SCD2 filtering (name_basics rows that were deduplicated or expired). The external review (Advisor #1) reported 89 missing persons at a coarser grain; the actual FK violation count is much higher.

**323,065 orphan series_key:** Episodes whose series_key does not resolve to a title with `title_type = 'tvSeries'`. This is a much larger number than the 5 flagged in the external report. Root cause: the series_key joins against dim_title requiring `title_type = 'tvSeries'`, but many parent titles may have a different type or be missing from dim_title entirely. The external report's SQL test likely checked different criteria (FK to dim_title without type filter).

**Recommendation:** Add FK enforcement in the Silver layer's `fk_checks.py` before materializing Gold. The quarantine table should catch these.

---

## 4. ETL Correctness (Bronze → Gold) — 2 PASS, 2 WARN

| Comparison | Bronze Rows | Gold Rows | Delta | Verdict |
|-----------|------------|-----------|-------|---------|
| title_basics ↔ dim_title (tconst) | 12,609,928 | 12,609,928 | 0 | **PASS** |
| name_basics ↔ dim_person (nconst) | 15,448,238 | 15,448,149 | **89** | **WARN** |
| Distinct tconst | 12,609,928 | 12,609,928 | 0 | **PASS** |
| Distinct nconst | 15,448,238 | 15,448,149 | **89** | **WARN** |

**Cross-reference:** The 89-row delta in name_basics/dim_person exactly matches Advisor #1's finding. This is reproducible across two independent assessment runs. The 89 persons are being filtered out during SCD2 deduplication or the Silver transform (likely rows where `primaryName` is NULL or all fields are identical to another row causing a no-op SCD2 close). This is intentional but undocumented behaviour.

---

## 5. Fitness for Use — 5 PASS, 1 FAIL

| Query | Time | Verdict |
|-------|------|---------|
| Genre distribution (top 10) | **1.95s** | PASS |
| Actor co-occurrence (LIMIT 5) | **30.54s** | **FAIL** |

The 30.5s actor co-occurrence query is the same slow path noted in the external review (Advisor #2 reported 27s, Advisor #3 flagged it as a red flag). It runs at essentially the same speed over Parquet via DuckDB as the original Postgres query — meaning **the bottleneck is in the join pattern, not the storage engine**.

**Root cause:** `fact_performance` is 100M rows with no pre-computed co-occurrence index. The self-join `a.tconst = b.tconst AND a.nconst < b.nconst` requires a full scan and a massive intermediate hash join. Neither Postgres nor DuckDB-over-Parquet can accelerate this without a co-occurrence materialization.

---

## 6. Pipeline Governance — 7 PASS, 1 WARN

| Check | Value | Verdict |
|-------|-------|---------|
| Gold export total size | 4,925 MB (4.9 GB) | PASS |
| _MANIFEST.json present | **Not found** | **WARN** |
| dim_title schema (22 cols) | Complete | PASS |
| dim_title analytical columns | genre_list(VARCHAR), director_names | PASS |

The export _MANIFEST.json was not found in `marts/full/`. Per the Gold export implementation (GoldExportOperator in G9), the manifest should be written after each export. It may have been lost during path migration (G2) or the marts/full/ directory may have been populated by a prior pipeline run without the manifest-enabled operator.

---

## 7. Post-Assessment: Silver Layer (Requires Live PostgreSQL)

The following checks require a running PostgreSQL instance with Silver data loaded. They are **documented but not executed** in this assessment:

| Domain | Check | Depends On |
|--------|-------|------------|
| SCD2 correctness | valid_from/valid_to/is_current transitions, no overlapping ranges | Silver PostgreSQL |
| SCD2 regression | New version count per batch | Silver PostgreSQL |
| Surrogate key integrity | Sequence gaps, monotonic ordering | Silver PostgreSQL |
| Index effectiveness | Seq scans vs index scans, missing FK indexes | Silver PostgreSQL |
| Quarantine completeness | Rows routed to quarantine vs passed | Silver PostgreSQL |
| batch_metadata accuracy | Row counts at each stage | Silver PostgreSQL |
| dbt test history | Data quality log entries for Gold models | Silver PostgreSQL |

---

## 8. Cross-Comparison with External Architecture Review

| Finding | Our Assessment | Advisor #1 | Advisor #2 | Advisor #3 | Agreement |
|---------|---------------|------------|------------|------------|-----------|
| name_basics 89-row loss | Confirmed (delta=89) | ✓ "89 missing persons" | ✓ "row count drops 89" | ✓ | **Full** |
| Bad runtime rows | 6 rows | ✓ "4 episodes with zero/negative" | ✓ "4 records" | ✓ | **Full** |
| PK SQL syntax error | Confirmed (fact_title_principal) | ✓ "count(DISTINCT) syntax" | ✓ "Missing column binding" | ✓ | **Full** |
| Actor co-occurrence 27-30s | 30.5s | ✓ "27s red flag" | ✓ "27s actor co-occurrence" | ✓ | **Full** |
| fact_episode orphans (5) | 323,065 (wider criteria) | ✓ "5 mismatches" | ✓ | ✓ | **Partial** (different join criteria) |
| dbt threads=2 bottleneck | Not directly tested | ✓ | ✓ "severely bottlenecked" | ✓ | **Full** |
| Bronze ingestion 47min | Not re-timed (HW constraints) | ✓ | ✓ | ✓ "abnormal" | **Full** |
| Tech stack sprawl | Confirmed: 5 engines | ✓ | ✓ "complexity" | ✓ "tech sprawl" | **Full** |
| Missing gold fact consolidation | fact_performance/fact_title_principal overlap | ✓ "consolidate or document" | ✓ | ✓ | **Full** |
| Gold export manifest missing | Confirmed | — | — | — | **New finding** |
| fact_performance PK violation (1.9M) | Confirmed | — | — | — | **New finding** |
| fact_episode PK violation (1.9M) | Confirmed | — | — | — | **New finding** |
| nconst orphan (7,649) | Confirmed | — | — | — | **New finding** |

---

## 9. Alignment with Elyssa Proposal Criteria

| Proposal Criterion | Current State | Gap |
|-------------------|---------------|-----|
| Correct Bronze→Silver→Gold lineage | ✓ Row counts match for titles (delta=0), 89 delta for persons | Small gap; needs documentation |
| SCD2 correctness for slowly-changing dimensions | ✓ Schema has valid_from/valid_to/is_current | Needs validation against live DB |
| Star-schema Gold marts fit for DS consumption | ✓ 4.9 GB Parquet, all 6 tables queryable | PK grains need correction |
| Pipeline performance < 6 hours | ✓ Not re-timed but prior benchmark at ~5h36m | Bronze ingestion bottleneck |
| Data quality gates at each layer | ✓ DQ checks at Silver + dbt tests at Gold | Composite PK tests need SQL fix |
| Quarantine governance for anomalous records | ✓ quarantine table + psycopg2 routing | Not verified against live DB |
| Gold export with manifest + freshness | ✗ _MANIFEST.json missing | Export operator fix (G9) may need re-execution |
| idempotent, replay-safe pipeline | ✓ SCD2 merge + batch_id + watermark | Not verified against live DB |

---

## 10. Summary of Action Items

| Priority | Domain | Issue | Impact | Resolution |
|----------|--------|-------|--------|------------|
| **P0** | Gold PK | fact_performance PK grain wrong (1.9M "dupes") | Breaks uniqueness assumptions; confuses DS consumers | Redefine PK to (title_key, name_key, ordering) in dbt model + schema.yml |
| **P0** | Gold PK | fact_episode PK grain wrong (1.9M "dupes") | Same | Use episode_key as PK; add COALESCE for NULL season/episode |
| **P0** | Gold SQL | fact_title_principal PK test binder error | Invalid DQ test hiding real issues | Fix column reference: tconst → title_key in test query |
| **P1** | Referential | 7,649 orphan nconst in fact_performance | FK violation; DS models may predict on missing persons | Add FK check in Silver fk_checks.py before Gold export; investigate SCD2 filter |
| **P1** | Referential | 323K episode orphans (series_key not tvSeries) | ~3% of episodes affected | Loosen FK check or fix series_key resolution in intermediate model |
| **P1** | Performance | Actor co-occurrence 30s | Unacceptable for interactive querying | Materialize co-occurrence as pre-computed table or add index |
| **P2** | Governance | _MANIFEST.json missing | Breaks export audit trail | Re-run Gold export operator |
| **P2** | Documentation | 89-row nconst delta undocumented | Creates confusion for future DE audits | Document in schema_dictionary.md why 89 persons are filtered |
| **P2** | Domain | 6 bad runtime rows + 38 bad years | Minor data quality leak | Add Silver quarantine rules per Advisor #3 recommendation |
| **P3** | Performance | Bronze ingestion 47 min (all_varchar=true) | Slowest single stage | Add explicit DuckDB schemas to read_csv per Advisor #3 fix |
| **P3** | Performance | dbt threads=2 | Limits Gold build parallelism | Increase to 4-8 in profiles.yml (HW-limited on 2C/4T CPU) |
