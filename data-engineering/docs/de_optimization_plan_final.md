# Elyssa‑IMDb | Ultimate Optimization & Infrastructure | Phase 1: Production DE — Architecture & Optimization Plan (Final)

**Status:** Analysis-only — approved for review. **No pipeline changes applied.**
**Baseline:** Frozen Phase 1 end-state (commit `6781afe`), measured run `manual_20260731160437`.
**Hardware:** AMD Athlon 200GE (2c/4t), 13.9 GB usable RAM, 512 GB SSD.
**Constraint:** All items keep peak RAM ≤ 13.5 GB, stay within Bronze–Silver–Gold + PostgreSQL + DuckDB + RustFS architecture, and do not alter core data flow, schema, or functional logic.

---

## 1. Analysis Summary

The pipeline is functionally complete and stable, but the measured active run (~9 h) is dominated by one algorithmic pathology and several redundant data movements. Silver ETL takes **5 h 04 m**, of which **~4 h 30 m** is the 8 child-normalization tables processed with `LIMIT/OFFSET` chunking over a re-read source (O(n²) behavior: `title_principal_char` scans a 100.9 M-row source 101 times, `title_akas_attribute` scans a 58.7 M-row source 59 times to emit 306 K rows). The Gold export stage wastes ~19 m on a redundant 4.0 GB tar archive plus post-export `COUNT(*)` re-reads of every table. The SCD2 merge on `title_basics`/`name_basics` expires-and-reinserts **every** row on each full reload (12.7 M + 15.5 M new versions per run), inflating Silver rows and every downstream dbt scan with no change-detection. Secondary findings: per-table double passes (count-then-COPY), runtime `INSTALL postgres_scanner` (network dependency), a 53-minute dbt uniqueness test on `fact_performance` (`gold.fact_performance`, 100.9 M rows) in the daily test gate, and an internal mart (`agg_actor_cooccurrence`) whose parallel-gather plan already ENOSPC'd once. Fixing the top three items is expected to cut the active pipeline from ~9 h to ~4.5–5 h with **no increase** in peak memory (the current peak ~11.5–12 GB stays; several items lower it).

---

## 2. Prioritised Improvements

| Rank | Area | Description | Expected Impact (runtime / RAM / disk) |
|---|---|---|---|
| P0‑1 | Silver ETL (child tables) | Replace `LIMIT/OFFSET` chunking with **hash-sharded single-pass** processing (shard source once by PK hash; per-shard `UNNEST`+`DISTINCT` is globally correct). | **−3.5 h runtime** (children 4 h 30 m → ~60–80 m) · RAM unchanged (bounded per shard) · disk −(CSV churn) |
| P0‑2 | Gold export | Remove redundant `gold_marts.tar.gz` creation (parquet dir is host bind-mount); derive manifest counts from parquet row-groups instead of post-export `COUNT(*)` re-reads. | **−19 m runtime** (31 m → ~12 m) · RAM −(DuckDB peak during tar) · disk −4.0 GB in container `/tmp` |
| P0‑3 | Silver SCD2 | Add change-detection to SCD2 merge (compare business-key attribute hash; expire+insert only changed rows). | **−20–40 m Silver / dbt** · RAM unchanged · disk/rows: stops +12.7 M title +15.5 M person versions per run; Gold dims stay lean |
| P1‑4 | Silver export | Replace post-export `COUNT(*)` re-reads with parquet footer row counts (or `pg_stat_user_tables` after `ANALYZE`). | **−5–8 m runtime** (40.6 m → ~33 m) · RAM − |
| P1‑5 | Gold dbt tests | Move the 4 `fact_performance` grain tests (`unique_combination`, ~53 m) to `severity: warn` / weekly gate; keep 39-test daily suite. | **−50 m per daily run** (test 70 m → ~18 m) · none |
| P1‑6 | Gold dbt (cooccurrence) | Per-model `pre_hook` disabling parallel gather on `agg_actor_cooccurrence` (removes DSM ENOSPC risk; 2-core box gains little from parallel hash join). | −5–15 m (avoids 1–2 h failure/retry tail) · RAM − (no DSM pressure) |
| P2‑7 | Bronze ingestion | Drop the pre-ingest full `read_csv` count pass; take row count from written local parquet footer instead. | **−2–4 m runtime** (19.5 m → ~16 m) · RAM − |
| P2‑8 | Image / offline resilience | Bake `postgres_scanner`+`httpfs` DuckDB extensions into `Dockerfile.etl-runner` (runtime `INSTALL` needs network); pin `rustfs/rustfs` image tag. | −1–3 m per cold start · reliability (works offline) · disk ~+50 MB |
| P2‑9 | Gold dbt (int model) | Drop non-contractual `ORDER BY` from `STRING_AGG` for `genre_list`/`region_list`/`language_list` (director/writer ordering stays). | **−5–10 m runtime** (dbt 1 h 55 m → ~1 h 45 m) · RAM − (smaller sorts) |
| P3‑10 | Docker build layers | Multi-stage Airflow image (build deps out of runtime), split `pip` layers to improve cache reuse, pin all base-image tags. | Build-time −30–40% · runtime ~0 · disk ~−1 GB image |
| P3‑11 | PG session | `SET LOCAL synchronous_commit=off` (and optionally `wal_compression=on`) during bulk COPY sessions. | −5–10 % on Silver COPY legs · crash-safety trade-off (documented, acceptable: pipeline is checkpointed/idempotent) |
| P3‑12 | Sensor polling | `wait_silver` uses `COUNT(*)` fallback already; add `ANALYZE silver.<t>` after child load so `n_live_tup` is meaningful on next sensor poll. | −1–3 m effective (fewer false-positive polls) · none |

---

## 3. Major Changes — Implementation Notes

### P0‑1 — Hash-sharded child-table processing (Silver ETL)
- **File:** `data-engineering/orchestration/operators/silver_operator.py`
  - `_process_child_table_chunked` (line 134) and the child loop (line ~800).
- **What changes:**
  1. Keep the existing single materialization of the source (`CREATE TABLE src_... AS SELECT * FROM read_parquet(...)` — one S3 read).
  2. Add a shard column: `ALTER TABLE src_... ADD COLUMN _shard SMALLINT; UPDATE src_... SET _shard = abs(hash(<pk>)) % 16;` — single local pass.
  3. Loop shards 0..15: `SELECT DISTINCT ... FROM src_... WHERE _shard = i` + same CSV/PG COPY path, but **drop the PG-side `SELECT DISTINCT` + `ON CONFLICT DO NOTHING`** (per-shard DISTINCT is globally correct because PK-hash keeps all rows of a key in one shard). Keep `INSERT` plain; PK violation impossible.
  4. **Ordering guarantee preserved:** `generate_subscripts` per-title ordering is untouched (hash is applied to the key column, not ordering).
- **Why it helps:** eliminates the O(n²) re-scan. `title_principal_char`: 101 re-scans of 100.9 M-row S3 parquet → 1 S3 read + 16 scans of a local DuckDB table; CSV/PG round trips drop from 264 total to ~128, each bounded.
- **Expected impact:** children ~4 h 30 m → 60–80 m. RAM per shard ≤ 1/16 of current worst case.

### P0‑2 — Gold export: remove tar + footer counts
- **File:** `data-engineering/scripts/gold_export_runner.py`
  - Delete tar creation block (lines 137–153) and `tar_path` arg plumbing in `orchestration/dags/imdb_pipeline_dag.py` (line 440) / `orchestration/operators/gold_export_operator.py`.
  - Replace per-table `SELECT count(*) FROM pg.gold.<t>` (line 104) with `pyarrow.parquet.read_metadata(path).num_rows` after export (footer-only read, no data scan).
- **Why it helps:** the bind-mount already delivers `marts/gold/*.parquet` to the host; the in-container tar adds 13.6 m and 4.0 GB of `/tmp` with zero host benefit (known issue #3). The count re-read costs another ~5 m (two 100.9 M-row tables re-read through `postgres_scanner`).

### P0‑3 — SCD2 change detection
- **File:** `data-engineering/orchestration/operators/silver_operator.py` — SCD2 block (lines 576–620).
- **What changes:**
  1. Add an `md5(concat_ws('|', <business attrs>))` column to the staging temp table during COPY (compute in DuckDB CSV, or in PG after COPY).
  2. Expire query becomes: `UPDATE silver.title_basics tb SET valid_to=NOW(), is_current=FALSE FROM stg s WHERE tb.tconst=s.tconst AND tb.is_current AND tb.attr_hash <> s.attr_hash`.
  3. Insert query becomes: `INSERT ... SELECT ... FROM stg s WHERE NOT EXISTS (SELECT 1 FROM silver.title_basics tb WHERE tb.tconst=s.tconst AND tb.is_current AND tb.attr_hash=s.attr_hash)`.
- **Why it helps:** today every full reload creates a fresh version of all 12.7 M titles + 15.5 M persons. With change detection, unchanged keys keep their current version → Silver tables stay ~constant size, every downstream dbt scan (and the Gold exports) gets cheaper, and the `is_current` index stays effective.
- **Contract note:** no schema change — `attr_hash` is internal (can be dropped or kept as an audit column; keeping it is a **non-breaking additive** change, verified against `gold-to-ds.md` before finalizing).

### P1‑4 — Silver export footer counts
- **File:** `data-engineering/scripts/silver_export_runner.py` (line 96): replace `SELECT count(*) FROM pg."<t>"` with `pyarrow` footer `num_rows` (pyarrow 25.0.0 already pinned in the runner image).
- Saves one full re-read of each of the 14 tables (worst: `title_principal` 100.9 M rows, `title_akas` 58.7 M rows).

### P1‑5 — dbt test gating
- **File:** `data-engineering/gold/tests/schema.yml` (lines ~113, ~153): set the 4 `fact_performance` grain tests (`dbt_utils.unique_combination_of_columns`, not_null on cooccurrence) to `severity: warn`, or gate via `dbt test --exclude` in a weekly DAG. Daily suite returns to 39 tests / ~18 m.

### P1‑6 — cooccurrence parallel-gather hardening
- **File:** `data-engineering/gold/models/marts/agg_actor_cooccurrence.sql`: add `+pre_hook: "SET max_parallel_workers_per_gather = 0"` in its `config()` block. This model already ENOSPC'd on DSM once (`a8779df` fix); removing parallel gather for this single model removes that failure mode entirely with negligible runtime cost on a 2-core host.

### P2‑7 — Bronze count pass removal
- **File:** `data-engineering/scripts/run_bronze.py`: remove the `read_csv` count query (lines 159–166) and instead set `_row_count` from `pyarrow.parquet.read_metadata(local_output).num_rows` after the local write; keep the S3 copy. Checkpoint marker logic unchanged.

### P2‑8 — Offline DuckDB extensions + image pin
- **File:** `docker/Dockerfile.etl-runner`: add `RUN python -c "import duckdb; c=duckdb.connect(); c.execute('INSTALL postgres_scanner'); c.execute('INSTALL httpfs')"` at build time; bump `duckdb==1.2.x` only if regression-tested (1.1.3 is known-good — pin stays unless a clear win).
- **File:** `docker/Dockerfile.rustfs`: replace `FROM rustfs/rustfs:latest` with a pinned tag.

### P2‑9 — STRING_AGG ORDER BY removal (non-contractual lists)
- **File:** `data-engineering/gold/models/intermediate/int_title_details.sql`: remove `ORDER BY TRIM(genre)` (genres) and `ORDER BY region/language` (akas). **Keep** `ORDER BY d.ordering`/`w.ordering` (director/writer order is semantic). Verify against `gold-to-ds.md` (contract requires comma-separated, trimmed — not sorted).

### P3‑10..12 — Low-risk housekeeping
- `docker/Dockerfile.airflow`: multi-stage (build `gcc/libpq-dev` in builder, copy wheels to runtime); `docker/docker-compose.yml`: pin images, keep memory limits as-is.
- `data-engineering/orchestration/operators/silver_operator.py`: after children load, `ANALYZE` the 14 silver tables so `n_live_tup` in `SilverDoneSensor` is accurate.
- PG session tuning (P3‑11) is **optional** — document crash-window trade-off; the pipeline is checkpoint-driven and idempotent, so `synchronous_commit=off` during COPY is acceptable, but it is listed last and can be skipped.

---

## 4. Risk Assessment

| Item | What could go wrong | Detection | Rollback |
|---|---|---|---|
| P0‑1 (shard rewrite) | Shard-column update on 100 M-row table adds one pass; hash collision on non-key column breaks DISTINCT correctness; PG INSERT violates PK. | Row-count reconciliation vs manifest (silver parquet counts must match pre-change values: title_genre 19,433,025; title_director 9,256,663; title_principal_char 47,800,519, etc.); DQ checks 7/7; `gold` counts unchanged. | Git revert of the operator file; old chunked path re-enabled via the retained `LIMIT/OFFSET` code or revert commit. File-lock + checkpoints make re-runs safe. |
| P0‑2 (tar removal) | A consumer relies on `/tmp/gold_marts.tar.gz` (none known — DS contract reads `marts/gold/` parquet; confirmed in `gold-to-ds.md`). | `grep` for `gold_marts.tar.gz` in repo; run gold export and verify 6 parquet + manifest on host. | Re-add tar block (2-line revert). |
| P0‑3 (SCD2 diff) | `attr_hash` mismatch (e.g. `\N` vs NULL, whitespace) causes over- or under-expiry → stale `is_current` rows or missing updates. | Row counts stable across two consecutive runs (no +12.7 M growth); `is_current=TRUE` count equals expected (12,681,122 / 15,534,075); `valid_to` timestamps only for changed rows. | Revert commit; re-run Silver (checkpoint `parents_done` must be cleared) — full reload restores previous semantics. |
| P1‑4/P2‑7 (footer counts) | `pyarrow` footer count differs from DuckDB scan count (row-group `num_rows` is exact for written files — low risk). | Manifest counts vs previous run values. | Revert; counts fall back to `SELECT count(*)`. |
| P1‑5 (test severity) | Grain regression slips through on daily runs. | Weekly deep-test DAG keeps the hard gate; cooccurrence tests still run (warn) daily. | Flip `severity` back to error. |
| P1‑6 (parallel off) | Slight runtime increase on the model (~5–15 m). | Compare `agg_actor_cooccurrence` build time before/after; row count must stay 140.75 M distinct pairs (already tested by 4 grain tests). | Remove `pre_hook`. |
| P2‑8 (extension bake) | Extension version mismatch with DuckDB 1.1.3 at build time. | Build log; container runtime `LOAD postgres_scanner` succeeds without network. | Revert Dockerfile; runtime `INSTALL` path still available. |
| P3‑11 (sync_commit off) | Crash window: up to ~500 ms of COPY work lost on power loss. | Pipeline checkpoints + file lock make re-runs safe; no data corruption possible (PostgreSQL WAL integrity intact). | Remove the `SET LOCAL`; revert commit. |

**Rollback principle:** every item is confined to 1–2 files, fully covered by the existing checkpoint/file-lock recovery, and reversible by `git revert <commit>`; none changes the Bronze–Silver–Gold schema contracts, column names, or exported parquet outputs.

---

## 5. Acceptance Criteria (per pipeline-planning skill)

1. P0‑1: Silver children total ≤ 90 m on a clean run; per-child parquet row counts identical to baseline manifest.
2. P0‑2: Gold export ≤ 15 m; host `marts/gold/` has 6 parquet + manifest; no tar in container `/tmp`.
3. P0‑3: Two consecutive Silver runs keep `title_basics`/`name_basics` row counts flat (±0.1 %); dbt dims unchanged.
4. P1‑4/P2‑7: Manifests match baseline counts (e.g. silver `title_principal` 100,923,228; gold `fact_performance` 100,923,234).
5. P1‑5: Daily dbt test ≤ 20 m; weekly deep gate still runs the 4 grain tests.
6. All: DAG run green end-to-end; peak container RAM ≤ 13.5 GB host total; `docs/final_pipeline_summary.md` numbers reconciled.

---

## 6. Next Steps (no implementation until approval)

1. Review & approve ranked items (suggested: P0‑1..P0‑3 first, then P1‑4..P1‑6, then P2).
2. Implement each as an atomic commit with the acceptance criteria above verified per commit.
3. Re-run the DAG and produce a post-optimization timing report to update this plan's impact estimates.
