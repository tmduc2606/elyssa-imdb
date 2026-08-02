# Final Pipeline Summary — Elyssa-IMDb | Phase 1 Closure

**Scope:** Post-mortem of the last full successful DAG run (`manual_20260731160437`), performance
metrics per layer, log of every hotfix applied after the `rustfs_integration_plan.md` baseline,
cleanup record, and final module state.

**Baseline document:** [`rustfs_integration_plan.md`](rustfs_integration_plan.md) (commit `8383467`).
**This report is the final Phase 1 deliverable — no further pipeline changes are allowed after it.**

---

## 1. Run Metadata

| Field | Value |
|---|---|
| DAG | `imdb_pipeline` |
| Run ID | `manual_20260731160437` (single run in DB) |
| State | **success** |
| Task instances | 18/18 success (after retries; see §4) |
| First task start | 2026-07-31 09:04:43 UTC |
| Last task end | 2026-08-01 08:17:03 UTC |
| Wall-clock (full) | **~23 h 12 m** (dominated by sensor waits, retry loops, overnight gap) |
| Active pipeline segment (per `dag_run` start/end) | 07:22:14 → 08:17:03 = **0.91 h** (covers gold-test → end only) |
| Evidence source | Airflow task logs (JSONL, all attempts), runner logs in `elyssa_etl_temp`, Airflow metadata DB (`public.dag_run`, `public.task_instance`) |

> **Note:** The run doubled as the recovery vehicle for several hotfixes (detached-subprocess
> sensors, `title_crew` export fix, ENOSPC/shm fix). Its heavy retry counts reflect that; a clean
> run on today's code is expected to be materially faster (see §5).

---

## 2. Layer Performance

| Layer / Stage | Runner log | Start (UTC) | End (UTC) | Duration | Rows / Result |
|---|---|---|---|---|---|
| **Bronze ingestion** (7 tables → S3 + local parquet) | `bronze_runner.log` | 07-31 09:04:57 | 07-31 09:24:28 | **19.5 m** (1171.3 s) | 212,018,100 rows (basics 12.68M, akas 58.70M, crew 12.68M, episode 9.80M, principals 100.92M, ratings 1.70M, name 15.53M) |
| **Silver ETL** (DuckDB → PostgreSQL, batch `20260731_092452`) | `silver_etl.log` | 07-31 09:24:52 | ~14:29 | **~5 h 04 m** | 6 tables; title_basics SCD2: 12,681,122 inserted (−1 expired); title_akas 58,696,398; title_episode 9,801,226 |
| **Silver export** (14 tables → parquet) | `silver_export.log` | 07-31 15:20:32 | ~16:01 | **~40.6 m** | title_basics 12,681,122 (77 s); title_akas 58,696,398 (595 s); title_episode 9,801,226 (83 s); title_principal 100,923,228 (744 s); title_rating 1,700,838 (11 s); name_basics 15,534,075 (161 s); title_genre 19,433,025 (83 s); title_director 9,256,663 (45 s); title_writer 14,623,828 (77 s); title_akas_type 18,778,062 (95 s); title_akas_attribute 306,277 (2 s) |
| **Gold dbt run** (12 models: 2 incremental, 5 table, 5 view) | `dbt_run.log` | 08-01 02:06:15 | 04:01:09 | **1 h 55 m** (6893 s) | PASS=11, ERROR=1 (`agg_actor_cooccurrence` ENOSPC — see §4.4); recovered via attempts 2–3 + manual `--select`, table complete ~05:23 |
| **Gold dbt test** | `dbt_test.log` | 07:22:16 | 07:40:33 | **18.3 m** (1097 s) | **PASS=33, WARN=6, ERROR=0, TOTAL=39** |
| **DQ checks** (7 checks + GX Bronze validation) | dq task log | 07:41:04 | 07:43:58 | **2.9 m** | 7/7 PASS (null_rate_title_rating=0.0, orphan/row-count checks); GX bronze suite PASS |
| **Freshness** (SLA 24 h) | freshness task log | 07:44:53 | 07:45:44 | ~51 s | 5/5 PASS (last updated 07-31 09:25:20, within SLA); 1 cosmetic ERROR (title_director — see §6.1) |
| **Gold export** (6 tables → parquet + manifest + tar) | `gold_export.log` | 07:45:47 | 08:16:53 | **~31 m** | dim_person 15,534,075 (82 s); dim_title 12,402,664 (149 s); fact_episode 9,801,226 (42 s); fact_performance 100,923,234 (368 s); fact_title_principal 100,923,228 (404 s); fact_title_rating 1,700,838 (4 s); `_MANIFEST.json` (batch `20260801_080318`); tar.gz 4,029.4 MB (13.6 m); `.export.completed` written |

**Gold parquet deliverables — verified on host** (`data-science/marts/gold/`, bind mount `docker/docker-compose.yml:178`):

| File | Size (host) |
|---|---|
| `dim_person.parquet` | 594 MB |
| `dim_title.parquet` | 719 MB |
| `fact_episode.parquet` | 133 MB |
| `fact_performance.parquet` | 2.18 GB |
| `fact_title_principal.parquet` | 1.89 GB |
| `fact_title_rating.parquet` | 16 MB |
| `_MANIFEST.json` + `.export.completed` | present |
| **Total** | **≈ 5.5 GB** |

---

## 3. Data Quality Summary

- **DQ checks (7):** `null_rate_title_basics`, `null_rate_title_rating` (= 0.0000, PASS), `orphan_title_episode`, `row_count_title_basics`, `row_count_name_basics`, `row_count_title_episode`, `null_rate_title_episode` — **all PASS** (`dq/config.yaml`).
- **Great Expectations Bronze suite:** PASS (run against `data-science/marts/bronze/`).
- **dbt generic tests:** PASS=33, WARN=6, ERROR=0 (TOTAL=39) in 18.3 m.
  - The 4 cooccurrence tests (3 × not_null + 1 × `unique_combination_of_columns`) added after this
    run (`f131a3c`) bring the suite to **43 tests**; the uniqueness test alone ≈ 53 m, so a scheduled
    `gold_dbt_test` now runs ≈ 70+ m. Consider `severity: warn` if runtime matters.
- **Freshness:** all silver tables within the 24 h SLA (pipeline timestamp 07-31 09:25:20, check ran 08-01 07:45).

---

## 4. Retry / Incident Inventory (per task attempts)

| Task | Attempts | Notes |
|---|---|---|
| `wait_bronze` | 2 | Attempt 1: 36 sensor poll cycles, then `[ALERT:HIGH] API_SERVER_ERROR` fail. Attempt 2: success on `.bronze.completed`. |
| `wait_silver` | 62 | Kill-loop era (300 s orphan-pass). Attempt 62 success. |
| `silver_export` | 11 | Attempts 1–10: killed at ~5 min each (`Server indicated the task shouldn't be running anymore`); attempts 3–7 also hit `title_crew` Catalog Error. Attempt 11 (after fix) success. |
| `gold_dbt_run` | 3 | Spawner successes; real work in `dbt_run.log` (attempt 1 = full run, ENOSPC; attempts 2–3 + manual `--select agg_actor_cooccurrence` = recovery). |
| `wait_dbt_run` | 7 | Attempt 3/5: `Task failed with exception`; attempt 4: `Failed to report terminal task state`; attempt 7 success. |
| `gold_dbt_test` | 3 | Spawner successes. |
| `wait_dbt_test` | 5 | Attempt 2/4: `[ALERT:MEDIUM] DBT test failed!` (pre-repair test suite); attempt 5 success. |
| `dq_checks` | 1 | Success. |
| `freshness_check` | 2 | Attempt 1 killed (`Task Instance not found — moved to history`); attempt 2 success. |
| `gold_export` / `wait_gold_export` / `pipeline_end` | 1 each | Success. |

**Root causes evidenced in run logs:**
1. **300 s orphan-pass kill loop** — every long-running task killed at ~5 min by Airflow's stale-task
   pass (fixed by `b4453bd` detached-subprocess pattern).
2. **`title_crew` export failure** — `Catalog Error: Table with name title_crew does not exist!`
   (silver exports crew-derived `title_director`/`title_writer`; export list fixed to 14 tables).
3. **PostgreSQL shared-memory ENOSPC** — `could not resize shared memory segment ... No space left
   on device` in model `agg_actor_cooccurrence` (fixed by DSM/shm 1 g + sysv, `a8779df`).
4. **API server errors / task-instance-not-found** — Airflow 3.3 supervisor churn during hotfix
   deployments; transient, all self-healed via retries.

---

## 5. Hotfix Log Since `rustfs_integration_plan.md` (baseline `8383467` → HEAD `02ad9ed`)

| # | Commit | Date | Fix |
|---|---|---|---|
| 1 | `4867381` | 07-30 12:44 | docs: plug-and-play pipeline test guide (live log commands per layer) |
| 2 | `c49c09b` | 07-30 12:49 | docs: Trigger Phase between download and bronze (sensor + DAG trigger + direct exec) |
| 3 | `2affd94` | 07-30 13:02 | perf: Docker RAM budget 94% → ~83% peak |
| 4 | `cf8ee15` | 07-30 13:09 | fix: strip protocol prefix from `S3_ENDPOINT` in `s3_config.py` |
| 5 | `f2d02b8` | 07-30 13:24 | fix(rustfs): replace `mc` with `rc` CLI, update all references |
| 6 | `3517cb3` | 07-30 13:24 | chore: remove `check_buckets.py` (superseded by rc CLI) |
| 7 | `11bceb0` | 07-30 13:26 | fix(rustfs): `USER root` for rc CLI install (base image runs non-root) |
| 8 | `5b06d1e` | 07-30 14:38 | fix(download): boto3 with AWS V4 signing for RustFS S3 uploads |
| 9 | `e638980` | 07-30 14:59 | fix(dag): `imdb_data_sensor` file_pattern → `*.tsv.gz` |
| 10 | `4ba2119` | 07-30 15:02 | fix(bronze): `SOURCE_FILES` matches actual S3 filenames |
| 11 | `27fb680` | 07-30 15:04 | cleanup(de): remove 7 redundant scripts |
| 12 | `501ace9` | 07-30 15:30 | fix(download): `put_object` instead of `upload_fileobj` (multipart OOM) |
| 13 | `1818485` | 07-30 15:49 | fix(sensor): boto3 `list_objects_v2` instead of DuckDB `read_csv` (OOM) |
| 14 | `5555e42` | 07-30 15:59 | fix(sensor): missing `import sys` (DAG import error) |
| 15 | `5886981` | 07-30 16:02 | fix(bronze): temp table for COPY instead of nested subquery |
| 16 | `9f431a8` | 07-30 16:09 | fix(bronze): remove `quote=''` from `read_csv`, de-nest subquery |
| 17 | `1053182` | 07-30 21:58 | fix(silver): advisory lock → file-based lock (`silver.lock`) |
| 18 | `51eac10` | 07-31 08:42 | fix(dag): restore from quarantine regression + silver live-log overhaul |
| 19 | `2ac02d3` | 07-31 09:51 | fix(silver): filter orphan `title.episode` rows with NULL `parentTconst` |
| 20 | `c20ef7e` | 07-31 15:10 | fix(bronze): preserve rows with literal quotes (silent data loss) + checkpoint row-count verification |
| 21 | `1363130` | 07-31 15:10 | chore: remove one-off bronze debug scripts |
| 22 | `d3c837c` | 07-31 15:33 | docs: refresh expected counts + Airflow 3.3 CLI |
| 23 | `a7b7dc7` | 07-31 15:34 | fix(docker): airflow `mem_limit` 1.5 g → 3 g (silver/gold export OOM + retry loop) |
| 24 | `b4453bd` | 07-31 22:28 | **fix: detached-subprocess pattern** for silver_export, gold_export, dbt tasks (300 s orphan-pass kill loop) + new sensors/spawners |
| 25 | `a8779df` | 08-01 15:20 | **fix: gold pipeline handoff + DSM/shm 1 g + sysv hardening + gold test-suite repair** |
| 26 | `f131a3c` | 08-01 21:19 | **fix(gold): `agg_actor_cooccurrence` grain violation (multiplicity: 154.7 M → 140.75 M distinct pairs) + wrong schema (`gold_gold`→`gold`) + 4 new tests** |
| 27 | `02ad9ed` | 08-01 21:33 | **fix(gold): `VACUUM (ANALYZE)` of `fact_performance` in index migration → enables index-only scan** (DISTINCT plan: HashAggregate seq-scan → Unique index-only scan) |

**Also landed (pre-baseline context, kept here for completeness):** 7 composite indexes on
`gold.fact_*` (9.7 GB total, all valid), dbt threads=2, `--no-partial-parse`.

---

## 6. Known Issues (cosmetic / non-blocking — NOT to be changed per Phase 1 freeze)

1. **Freshness ERROR on `silver.title_director`** — `failed to patch ingested_at: current tr...`
   (table lacks the column; `freshness.py` auto-ALTER hit a constraint error). Freshness SLA still
   met. Recommended future fix: add `ingested_at` to the silver child-table schema.
2. **Airflow 3.3 deprecation warnings** — `EmptyOperator`/`PythonOperator` →
   `airflow.providers.standard.*`, `BaseSensorOperator` → `airflow.sdk.bases.sensor` (DAG lines
   32–39, sensors). Cosmetic.
3. **Redundant `gold_marts.tar.gz` (4.0 GB in container `/tmp`)** — the gold parquet dir is
   bind-mounted to the host (`data-science/marts/gold/`), so the tar adds ~13.6 min with no host
   benefit. Candidate for removal in Phase 2.
4. **RAM during run: not captured** — no Docker stats/monitoring was active during the run
   (containers were down at analysis time). Not reported.

---

## 7. Cleanup Log

| Item | Action | Status |
|---|---|---|
| `data-engineering/**/__pycache__` (14 dirs, excl. `.venv`) | Removed | Done (gitignored, no repo change) |
| `gold_gold` schema + `gold_gold.agg_actor_cooccurrence` | Dropped (`f131a3c`) | Done |
| Stale CREATE INDEX sessions / invalid partial index | Cancelled + recreated non-concurrently (`02ad9ed` era) | Done — 7/7 indexes valid |
| One-off bronze debug scripts / `check_buckets.py` | Removed (`1363130`, `3517cb3`) | Done |
| Working tree | `git status` clean at HEAD `02ad9ed` | Verified |
| Airflow run logs | Archived read-only to `%TEMP%\opencode\run_logs` | Kept for reference |

---

## 8. Final Module State

| Module | Status |
|---|---|
| `data-engineering/` | bronze (7 tables, quote-safe COPY), silver (14 tables + 3 governance, file-lock, SCD2), gold (dbt: 12 models, 43 tests, 7 composite indexes, VACUUM-optimized index-only scans), dq (7 checks + GX), orchestration (DAG + detached-subprocess spawners/sensors), scripts, docs (incl. this report) |
| `data-science/` | Gold parquets delivered at `marts/gold/` (≈5.5 GB, 6 tables + manifest) + `marts/bronze/` (7 parquet + markers), `marts/silver/` (14 parquet + manifest); `notebooks/models/` and `figures/` dirs present |
| `docker/` | compose + 4 images intact; `elyssa-postgres` (healthy, 54321), `elyssa-etl-runner`, `elyssa-rustfs` up; `elyssa-airflow` in "Created" (not started) |
| `docs/` (repo root) | plan, runbook, smoke test, QA catalog preserved |
| `src/`, `gate0/` | Not part of this repo layout (module map per root `AGENTS.md`) |

**Phase 1 closure status: ✅ COMPLETE.** Pipeline ran end-to-end to success; all 17+ identified gaps
since the rustfs plan are fixed, tested, and documented; Gold marts are frozen and exported for the
Data Science phase.
