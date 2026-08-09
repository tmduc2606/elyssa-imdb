# Elyssa-IMDb Final Release Blueprint

**Date:** 2026-08-09  
**Version:** 1.1.0  
**Status:** APPROVED — Open questions resolved; hardware-constrained opt. amendments applied; WA implementation checklist issued (see `WA_IMPLEMENTATION_TODO.md`). Implementation awaits owner go-ahead.  
**Priority Order:** Web Application → Data Science → Data Engineering

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Priority 1 — Web Application](#2-priority-1--web-application)
3. [Priority 2 — Data Science](#3-priority-2--data-science)
4. [Priority 3 — Data Engineering](#4-priority-3--data-engineering)
5. [Cross-cutting — Infrastructure & MLOps](#5-cross-cutting--infrastructure--mlops)
6. [Aggressive Optimisation Plan](#6-aggressive-optimisation-plan)
7. [Open Questions for User Customization](#7-open-questions-for-user-customization)
8. [Deliverables List](#8-deliverables-list)
9. [Review Gates & Approval](#9-review-gates--approval)

---

## 1. Executive Summary

### Current State

Elyssa-IMDb is a data-engineering, data-science, and web-application platform consuming IMDb's public datasets. The system processes 212M rows (Bronze) → 355M (Silver) → 241M (Gold) across 7h 22m on a 2C/4T, 16GB AMD Athlon 200GE. The web application serves a FastAPI + React SPA with GraphQL, but suffers from auth failures, missing poster images, no pagination, and dropped crew data. The data-science models fail quality gates (Genre F1 0.25 vs 0.60 target; Rating RMSE 1.56 vs 0.55 target) due to residual feature leakage and a broken inference pipeline. The data-engineering pipeline has 22+ files with hardcoded credentials, 14 files with stale PySpark references, and a CI gate that passes by construction (`pytest || echo`).

### Priority Sequencing

| Phase | Scope | Est. Effort | Est. Impact |
|-------|-------|-------------|-------------|
| **P1: Web Application** | Auth fix, poster integration, pagination, crew display, Docker build | 3–5 days | Users can actually use the app |
| **P2: Data Science** | Re-run notebooks post-optimization, fix leakage, fix inference pipeline, re-baseline metrics | 2–3 days | Models meet or approach quality gates |
| **P3: Data Engineering** | Credential consolidation, PySpark cleanup, CI gate fix, performance tuning | 3–5 days | Secure, maintainable, faster pipeline |
| **P4: Infrastructure** | Docker build optimization, .dockerignore, MLOps pipeline, cleanup | 2–3 days | Production-ready deployment |

### Critical Bugs (Must-Fix Before Release)

| # | Module | Bug | Severity | Root Cause |
|---|--------|-----|----------|------------|
| C1 | WA | Auth 409/401 — register cookie dropped on HTTP | **Critical** | Register sets `secure=True` even on HTTP; login sets `secure=False` dynamically |
| C2 | WA | No refresh token rotation | **High** | Refresh endpoint reuses same token until 7-day expiry |
| C3 | WA | Posters always `None` | **Medium** | No poster column in Gold marts; resolver hardcodes `poster_url=None` |
| C4 | DS | `avg_rating_genre_year` leakage (91% importance) | **Critical** | Feature computed over sample including target |
| C5 | DS | Inference pipeline broken (zero embeddings, bypass preprocessor) | **Critical** | `src/inference/pipeline.py` never fitted; CLS vs mean-pool mismatch |
| C6 | DE | 22+ files with plaintext credentials | **Critical** | No env-var indirection in DE runtime path |
| C7 | DE | CI gate voided (`pytest \|\| echo`) | **High** | Fallback masks test failures; `data-engineering/tests/` doesn't exist in CI path |
| C8 | Infra | MLOps CD pushes CI fixture models, not trained models | **High** | `cd.yml` stages test fixtures into `marts/processed/` before build |

---

## 2. Priority 1 — Web Application

### 2.1 Root-Cause Analysis: Auth Failures

**Evidence Chain:**

1. **Register 409 →  cookie silently dropped:**  
   - `web-application/api/app/auth/router.py:51-58`: Registration sets `secure=settings.secure_cookies` (static `True` by default, `config.py:39`).  
   - `web-application/api/app/auth/router.py:70-78`: Login dynamically sets `secure=settings.secure_cookies and request.url.scheme == "https"`.  
   - **Result:** On HTTP (dev), registration sets a `secure=True` cookie that browsers silently discard. Users who register never get a valid refresh cookie until they log in again.

2. **No refresh token rotation:**  
   - `web-application/api/app/auth/router.py:82-94`: The `/auth/refresh` endpoint creates a new access token but does NOT issue a new refresh token. The same refresh token is reused for up to 7 days.  
   - **Security risk:** A stolen refresh token grants unlimited access for the full 7-day window.

3. **JWT expiry mismatch:**  
   - `web-application/api/app/config.py:37`: `jwt_expire_minutes = 15` (correct per best practice).  
   - `web-application/contracts/api-to-frontend.md:21`: Claims "24 hours" — contract is wrong.

4. **`/auth/me` 401 cascade:**  
   - `web-application/client/src/hooks/useAuth.tsx:45-72`: On mount, tries `getAccessToken()` + `authFetch("/me")`. If that fails, tries `POST /refresh` with cookie. If refresh fails (no valid cookie due to #1), sets `accessToken=null`, `user=null`.  
   - The 401s are a downstream effect of the dropped registration cookie.

**Fix Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| A1: Unify cookie flags | `auth/router.py:51-58` | Set `secure=False` on HTTP, `secure=True` on HTTPS for both register AND login | 10 min |
| A2: Implement refresh token rotation | `auth/router.py:82-94` | Issue new refresh token on every refresh; invalidate old token; store token family in DB for reuse detection | 2–3 h |
| A3: Fix contract | `contracts/api-to-frontend.md:21` | Change "24 hours" to "15 minutes" | 5 min |
| A4: Rate-limit login/refresh | `auth/router.py` | Add `slowapi` rate limiter (5 attempts/min per IP) | 1 h |

**Best Practice Reference (from web search):**  
FastAPI JWT auth production checklist (KowashLab 2026, Navspace 2026): access tokens ≤30 min, refresh tokens rotated on every use, stored hashed in DB with `family_id` for reuse detection, delivered via httponly/secure/samesite cookies.

### 2.2 Poster Integration — OpenPosterDB

**Current State:**  
- `web-application/api/app/graphql/resolvers.py:125,325`: `poster_url=None` (hardcoded).  
- Gold Parquet schema has no poster column.  
- Frontend (`MediaCard.tsx:40-51`, `TitleHero.tsx:45-56`) gracefully falls back to text placeholders.

**Solution: OpenPosterDB** (self-hosted, RPDB-compatible)  
- API: `http://localhost:3000/v1/{type}/{imdb_id}` (type = `poster`, `logo`, `backdrop`).  
- Free API key: `t0-free-rpdb` (read-only, global defaults).  
- Uses TMDB API under the hood for images.  
- In-memory caching + on-disk storage for fast delivery.

**Integration Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| P1: Add poster service | `api/app/services/poster.py` (new) | HTTP client that calls OpenPosterDB API, caches results in Redis with 7-day TTL | 2 h |
| P2: Wire into resolver | `graphql/resolvers.py:125,325` | Call poster service with `tconst`/`nconst`, return URL instead of `None` | 30 min |
| P3: Add env config | `config.py` | `ELYSSA_POSTER_BASE_URL=http://localhost:3000`, `ELYSSA_POSTER_API_KEY=t0-free-rpdb` | 15 min |
| P4: Pre-populate cache | Startup script or background task | Batch-fetch posters for top-rated titles during API startup | 1 h |
| P5: Docker compose | `docker-compose.yml` | Add `openposterdb` service (self-hosted) or point to external instance | 30 min |

### 2.3 Pagination & Crew Display

**Pagination:**  
- Backend (`resolvers.py:334-358,361-422`) already implements cursor-based pagination with `has_more` and `next_cursor`.  
- Frontend hardcodes `first: 50` (search, `gold.ts:154-161`) and `first: 100` (browse, `gold.ts:164-183`).  
- `Search.tsx:16` reads `data?.search?.items ?? []` with no "load more" mechanism.

**Fix:** Add infinite scroll or "Load More" button using `hasMore`/`cursor` from GraphQL response. Use TanStack Query's `useInfiniteQuery` for cursor-based pagination.

**Crew Display:**  
- `TITLE_DETAIL_QUERY` (`gold.ts:12-47`) fetches `crew { person { id primaryName posterUrl } category job }`.  
- `TitleDetail.tsx:34`: Only `cast` is extracted; `title.crew` is never passed to any component.  
- `CastList.tsx:26-27` filters `crew` from `cast` prop, but `cast` only contains actors/actresses (resolver filters by `category IN ('actor', 'actress', 'self')`).

**Fix:** Extract `title.crew` in `TitleDetail.tsx`, pass to `CastList` or create separate `CrewList` component.

### 2.4 Docker Build Optimization

**Current Issues:**
- Root compose (`docker-compose.yml`): `image: elyssa-api:latest` + `build:` — if image doesn't exist locally, Docker tries to pull from registry (fails).
- `web-application/api/Dockerfile`: Installs ML deps (torch, catboost, scikit-learn) in API-only image; runs as root.
- No `.dockerignore` for `web-application/api/`, `web-application/client/` — ships `node_modules/`, `.venv/`, `dist/` into images.
- Port conflict: `mlops/docker-compose.yml` — frontend `3000:80` vs grafana `3000:3000`.

**Fix Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| D1: Multi-stage Dockerfile | `web-application/api/Dockerfile` | Separate build stage (ML deps) from final stage (API-only); non-root user | 1 h |
| D2: Add .dockerignore | `web-application/api/.dockerignore` | Exclude `.venv/`, `__pycache__/`, `.pytest_cache/`, `tests/`, `*.pyc` | 15 min |
| D3: Add .dockerignore | `web-application/client/.dockerignore` | Exclude `node_modules/`, `dist/`, `test-results/`, `.next/` | 15 min |
| D4: Fix port conflict | `mlops/docker-compose.yml` | Change grafana to `3001:3000` or frontend to `3001:80` | 5 min |
| D5: Add `build:` to root compose | `docker-compose.yml` | Ensure `build:` section is always used; remove `image:` for dev | 15 min |
| D6: Memory limits | `mlops/docker-compose.yml` | Add `mem_limit` to api/model/frontend services | 15 min |

### 2.5 Simulated Subagent Discussion: WA Module

**Dev Agent:** "Auth fix is straightforward — unify cookie flags, implement rotation. The OpenPosterDB integration is clean since it's RPDB-compatible. Main risk is the Docker memory issue during builds."

**Security Agent:** "Refresh token rotation is non-negotiable for production. The current 7-day reuse window is a critical vulnerability. Also, the root Dockerfile runs as root — must fix before any public exposure."

**UX Agent:** "Pagination and crew display are quick wins since the backend already supports them. The poster integration will have the biggest visual impact — currently every title shows a text placeholder."

**Decision:** Auth fix (A1–A4) → Poster (P1–P5) → Pagination + Crew → Docker optimization. All items are independent and can be parallelized.

---

## 3. Priority 2 — Data Science

### 3.1 Critical Finding: Residual Leakage

**Evidence:**  
- `avg_rating_genre_year` has **91.11% feature importance** in CatBoost rating model (from `catboost_rating_model.cbm` analysis).  
- This feature is a genre-year mean rating aggregate computed over the training sample — it leaks the target variable.  
- The optimization plan removed `average_rating` and `num_votes` but did NOT remove `avg_rating_genre_year`.  
- Current Rating RMSE: **1.5602** (gate: ≤0.55). With leakage removed, RMSE will degrade further (expected ~1.5–2.0).

**Root Cause:** The feature engineering step computes `avg_rating_genre_year` by averaging `average_rating` per genre-year group across the sample, including test data. This is a classic data leakage pattern.

**Fix:** Remove `avg_rating_genre_year` from the feature set. Re-run notebooks. Expect Rating RMSE to increase (worsen) — this is correct behavior showing the model's true capability.

### 3.2 Inference Pipeline Broken (Gap G11)

**Evidence from research:**  
- `src/inference/pipeline.py`: `_get_text_embedding()` uses `max_length=428` (line 71) and **mean-pooling** (`outputs.last_hidden_state.mean(dim=1)`).  
- `src/features/text.py` (training): Uses `max_length=32` and **CLS token** (`outputs[0][:, 0]`).  
- `build_feature_vector()` bypasses `preprocessor.joblib` and `scaler.joblib` — uses manual one-hot encoding with zeros instead.  
- **Result:** Train-serve skew — the model was trained on CLS embeddings at max_length=32 but inference uses mean-pooled embeddings at max_length=428.

**Fix:** Align inference pipeline with training: CLS token, max_length=32, use fitted preprocessor/scaler.

### 3.3 Notebooks Not Re-Run Post-Optimization

**Evidence:**  
- All optimization items (float32, batch size, thread pinning, etc.) are implemented in code.  
- But artifacts on disk are still **float64** (from pre-optimization run on 2026-08-02/03).  
- Gold marts were re-exported on 2026-08-04 (after model run).  
- Metrics in `standardized_results.json` are stale baselines.

**Action:** Re-run `python scripts/run_pipeline.py --stage all` end-to-end. This will:
1. Re-compute embeddings (float32, batch 128, 4 threads)
2. Re-train all models with new feature set
3. Produce updated metrics and artifacts
4. Validate quality gates

### 3.4 DistilBERT Embedding Optimization

**Current:** 29.2 titles/s on CPU (AMD Athlon 200GE, 4 threads). Full corpus (250k titles) → ~2.5h.

**Options (from web search):**

| Option | Speedup | Accuracy Impact | Effort |
|--------|---------|-----------------|--------|
| INT8 quantization (Intel Neural Compressor) | 3–4x | <1% F1 loss | 2–3 h |
| MobileBERT (25M params vs 66M) | 2x | ~2% F1 loss | 1 h (swap model) |
| ONNX Runtime optimization | 2–3x | <1% | 1 h |
| Cache embeddings (already done) | Infinite (on cache hit) | None | Done |

**Recommendation:** Implement INT8 quantization for production; keep cached embeddings for development.

### 3.5 Enhancement Catalogue

| # | Item | Priority | Expected Impact | Difficulty | Status |
|---|------|----------|-----------------|------------|--------|
| DS1 | Remove `avg_rating_genre_year` leakage | P0 | Correct RMSE (will worsen to true value) | Low | TODO |
| DS2 | Fix inference pipeline (CLS, max_length, preprocessor) | P0 | Correct train-serve alignment | Medium | TODO |
| DS3 | Re-run notebooks end-to-end | P0 | Updated baselines, float32 artifacts | Medium | TODO |
| DS4 | Add `rating_bucket` to excluded features | P0 | Prevent target leakage | Low | TODO |
| DS5 | INT8 quantize DistilBERT | P1 | 3–4x embedding speedup | Medium | TODO |
| DS6 | Add feature-audit gate (importance threshold) | P1 | Automated leakage detection | Medium | TODO |
| DS7 | Add temporal-split post-hoc enforcement script | P1 | Automated split validation | Low | TODO |
| DS8 | Fix `run_pipeline.py` y_rating target bug | P1 | Correct rating training labels | Low | TODO |
| DS9 | Align BiLSTM epochs (plan says 8, code has 20) | P2 | Consistency with plan | Low | TODO |
| DS10 | Generate model cards | P2 | Documentation completeness | Low | TODO |

### 3.6 Simulated Subagent Discussion: DS Module

**ML Agent:** "The leakage is the #1 blocker. Until `avg_rating_genre_year` is removed, all rating metrics are meaningless. The inference pipeline fix is equally critical — without it, the web app returns garbage predictions."

**Data Agent:** "Re-running notebooks is essential but will take ~55–70 min on the reference hardware. We should add a `--validate-only` flag to skip re-training and just check artifact freshness."

**MLOps Agent:** "The model binaries are gitignored and only exist on the run host. We need a proper model registry (MLflow) to version and retrieve trained models. The current `cd.yml` pushes CI fixtures, not real models."

**Decision:** Fix leakage (DS1) → Fix inference (DS2) → Re-run (DS3) → Add gates (DS6, DS7) → Optimize embeddings (DS5).

---

## 4. Priority 3 — Data Engineering

### 4.1 Credential Consolidation

**Evidence:**  
- 7 distinct plaintext secrets found across 22+ files.  
- Secrets include: `elyssa_pg_2026`, `elyssa_s3_2026`, `elyssa_neo4j_2026`, `elyssa_airflow_secret_2026`, `admin`, `elyssa_ds_2026`, JWT secret.  
- No env-var indirection in the DE runtime path — all hardcoded in compose, DAGs, operators, and scripts.

**Fix Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| C1: Create `.env` template | `.env.example` | Centralize all secrets with placeholder values | 30 min |
| C2: Update docker-compose | `docker/docker-compose.yml` | Replace hardcoded creds with `${VAR}` interpolation | 1 h |
| C3: Update DAGs | `imdb_pipeline_dag.py`, `quarterly_review_dag.py` | Read secrets from Airflow Connections/Variables instead of hardcoded strings | 2 h |
| C4: Update operators | `silver_operator.py`, `imdb_sensor.py` | Use Airflow Connections for DB creds | 1 h |
| C5: Update scripts | `run_bronze.py`, `download_imdb.py` | Accept creds via env vars or CLI args | 1 h |
| C6: Update profiles.yml | `gold/profiles.yml` | Use env-var interpolation for dev/prod creds | 15 min |
| C7: Rotate all secrets | All files | Generate new passwords; update all references | 1 h |

### 4.2 PySpark Cleanup

**Evidence:**  
- 14 files contain PySpark references (code, configs, comments, docs).  
- 4 test files are BROKEN due to PySpark imports (`silver/tests/test_transform.py`, `test_silver_comprehensive.py`, `bronze/tests/test_bronze_comprehensive.py`, `test_ingestion.py`).  
- `bronze/ingest_imdb.py` has live PySpark imports but is parallel/legacy code.  
- `docs/disaster_recovery.md` references `spark-submit` for Silver recovery (dead path).  
- `docs/phase1_summary.md` references "PySpark 4.1.2" (historical).

**Fix Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| R1: Remove PySpark imports from test files | 4 test files | Delete pyspark imports; rewrite tests using DuckDB/stdlib | 3–4 h |
| R2: Remove PySpark from `bronze/ingest_imdb.py` | `bronze/ingest_imdb.py` | Delete PySpark code path; keep DuckDB canonical path | 1 h |
| R3: Fix `docs/disaster_recovery.md` | `docs/disaster_recovery.md:70` | Replace `spark-submit` with DuckDB command | 15 min |
| R4: Clean `docs/phase1_summary.md` | `docs/phase1_summary.md` | Mark PySpark sections as historical/deprecated | 15 min |
| R5: Clean stale docstrings | `silver/transform.py`, `upsert.py`, `scd2_transform.py` | Remove PySpark docstrings (already docstring-only) | 15 min |

### 4.3 CI Gate Fix

**Evidence:**  
- `.github/workflows/ci-de.yml:27-28`: `pytest data-engineering/tests/ -q --tb=short || echo "No DE tests found (tests/ absent)"`.  
- `data-engineering/tests/` does NOT exist — the fallback always fires.  
- `.github/workflows/ci.yml:30,37`: Second `|| echo` fallback.  
- Per-test verdicts: 2 FUNCTIONAL, 3 STALE, 5 BROKEN.

**Fix Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| F1: Create `data-engineering/tests/` | New directory | Move functional tests here; delete broken/stale tests | 1 h |
| F2: Remove `\|\| echo` fallback | `ci-de.yml:27-28` | Change to `pytest data-engineering/tests/ -q --tb=short` (fail on error) | 5 min |
| F3: Remove `\|\| echo` from root CI | `ci.yml:30,37` | Same treatment | 5 min |
| F4: Rewrite stale tests | 5 test files | Update imports, fix assertions, remove PySpark deps | 3–4 h |
| F5: Add DE test fixtures | `data-engineering/tests/fixtures/` | Small Parquet samples for CI testing | 1 h |

### 4.4 Performance Tuning

**Current Bottlenecks (from `pipeline_performance_metrics.md`):**

| Step | Duration | % of Total | Bottleneck |
|------|----------|------------|------------|
| Gold total | 7h 2m 41s | 95.4% | dbt run (2h 58m) + dbt test (58m) |
| dbt test: `agg_actor_cooccurrence` uniqueness | 57m 23s | 13.9% | Full table scan, 140M rows |
| dbt test: `fact_title_principal` uniqueness | 32m 16s | 7.7% | Full table scan, 100M rows |
| Silver export | 20m 17s | 4.6% | Serial COPY over 16 shards |
| Gold export | 19m 6s | 4.5% | Serial 6-table export |

**Optimization Plan:**

| # | Optimization | Expected Speedup | Effort |
|---|-------------|------------------|--------|
| O1: Incremental materialization for `fact_performance`, `dim_title`, `dim_person` | 2–3x on re-runs | 2–3 h |
| O2: Raise dbt threads 2→4 for tests | 2x on test parallelism | 15 min |
| O3: Pre-compute PK index for slow uniqueness tests | 57m → 2–5 min each | 1 h |
| O4: Parallelize Gold export (6 tables serial) | 19m → 6–8 min | 2 h |
| O5: Skip `agg_actor_cooccurrence` from dbt run (already warn severity) | -22% of dbt run time | 15 min |
| O6: Add `freshness` block to `sources.yml` for `title_director` | Eliminates freshness noise | 15 min |
| O7: Remove `freshness.py` auto-ALTER hack | Cleaner freshness path | 30 min |

### 4.5 Hybrid Delta Detection (Breakthrough Feature)

**Context:** IMDb provides complete TSV/Parquet dumps daily. No change log exists. We need to detect deltas between snapshots.

**Design (DuckDB-native):**

```sql
-- Step 1: Compute row hashes for current and previous snapshots
CREATE TABLE current_hashes AS
SELECT tconst, hash(*columns(*)) AS row_hash
FROM read_parquet('bronze/title.basics/2026-08-09/*.parquet');

CREATE TABLE previous_hashes AS
SELECT tconst, hash(*columns(*)) AS row_hash
FROM read_parquet('bronze/title.basics/2026-08-08/*.parquet');

-- Step 2: Detect changes
-- New rows (inserted)
INSERT INTO silver.title_basics_delta
SELECT * FROM current_hashes c
LEFT JOIN previous_hashes p ON c.tconst = p.tconst
WHERE p.tconst IS NULL;

-- Changed rows (updated)
INSERT INTO silver.title_basics_delta
SELECT * FROM current_hashes c
JOIN previous_hashes p ON c.tconst = p.tconst
WHERE c.row_hash != p.row_hash;

-- Deleted rows (optional, for SCD Type 2)
INSERT INTO silver.title_basics_deleted
SELECT p.tconst FROM previous_hashes p
LEFT JOIN current_hashes c ON p.tconst = c.tconst
WHERE c.tconst IS NULL;
```

**Implementation Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| H1: Create delta detection script | `scripts/detect_delta.py` | DuckDB-based hash diff with configurable strategy per table | 3–4 h |
| H2: Add delta materialization | `silver_operator.py` | Integrate delta detection before SCD2 upsert | 2 h |
| H3: Store previous hashes | Bronze partition | Persist `*_hashes.parquet` alongside data for next run | 1 h |
| H4: Add schema evolution handling | `silver_operator.py` | Detect column adds/drops; auto-ALTER Silver DDL | 2 h |

**Strategy Decision Tree:**
- **Append-only tables** (new `tconst`): Use `LEFT JOIN ... WHERE IS NULL` — fast, no hash needed.
- **SCD Type 2 tables** (changed rows): Use `hash(*columns(*))` diff — accurate, moderate cost.
- **Large tables** (100M+ rows): Partition hash computation by `tconst` prefix; parallelize across threads.

**Benchmark Estimate:** Hash computation over 100M rows with DuckDB `hash(*columns(*))` — ~2–5 min (DuckDB v1.3+ with late materialization). Full reload approach: ~20 min. Delta approach: ~5 min (90% faster on stable days).

### 4.6 Simulated Subagent Discussion: DE Module

**DE Agent:** "The credential consolidation is the highest priority — plaintext secrets in 22+ files is a production blocker. The CI gate fix is also critical since it provides zero regression signal."

**Performance Agent:** "The dbt test bottleneck is the single biggest time sink. Pre-computing PK indexes for the two slow uniqueness tests (57m + 32m) would cut total runtime by ~20%. Incremental materialization would cut re-run time by 2–3x."

**Delta Agent:** "Hybrid delta detection is the most architecturally significant feature. The DuckDB `hash(*columns(*))` approach is clean and efficient. We should implement it as a reusable script that other tables can adopt."

**Decision:** Credentials (C1–C7) → CI gate (F1–F5) → PySpark cleanup (R1–R5) → Performance (O1–O7) → Delta detection (H1–H4).

---

## 5. Cross-cutting — Infrastructure & MLOps

### 5.1 Docker & Container Runtime

**Issues Found:**
- No `.dockerignore` for `web-application/api/`, `web-application/client/` — ships `node_modules/`, `.venv/`, `dist/` into images.
- `web-application/api/Dockerfile` runs as root; `mlops/docker/Dockerfile.api` creates `elyssa` user.
- Root compose `mem_limit: 512m` for api; mlops compose has no api mem limit.
- Port conflict: frontend `3000:80` vs grafana `3000:3000`.
- MLOps CD pushes CI fixture models, not trained models.

**Fix Plan:**

| Task | File | Change | Effort |
|------|------|--------|--------|
| I1: Add .dockerignore files | 3 locations | Exclude caches, tests, node_modules, .venv | 30 min |
| I2: Non-root user in all Dockerfiles | `web-application/api/Dockerfile` | Add `useradd -r -s /bin/false elyssa` | 15 min |
| I3: Fix port conflict | `mlops/docker-compose.yml` | Change grafana to `3001:3000` | 5 min |
| I4: Add mem_limit to mlops compose | `mlops/docker-compose.yml` | Add `mem_limit` to api/model/frontend | 15 min |
| I5: Fix CD to push real models | `.github/workflows/cd.yml` | Remove fixture staging; build from trained artifacts | 1 h |
| I6: Add Docker build cache pruning | `Makefile` or script | `docker builder prune -f --filter "until=24h"` | 15 min |

### 5.2 WSL2 Resource Management

**Current:** Host has 16GB RAM. WSL2 default allocates 50% (8GB). Docker containers consume up to 9.5GB (postgres 2G + airflow 2.5G + etl-runner 2G + rustfs 256M + api 512M + redis 256M).

**Recommended `.wslconfig`:**
```ini
[wsl2]
memory=8GB
processors=4
swap=2GB

[experimental]
autoMemoryReclaim=gradual
```

**VHD Compaction:** Run `Optimize-VHD` monthly or use `wsl --manage` to resize.

### 5.3 MLOps Pipeline Enhancement

**Current State:**
- MLflow compose service exists (Postgres backend, artifact storage).
- Model deployment bakes artifacts into Docker image at build time.
- CD pushes `ghcr.io/tmduc2606/elyssa-*:${{ github.sha }}` but with CI fixture models.
- No model versioning beyond `:latest` and `:sha`.

**Proposed Minimal MLOps Pipeline:**

```
Gold Mart Update → DS Pipeline Run → MLflow Logging → Quality Gate → Model Registry → Docker Build → Deploy
```

| Component | Tool | Purpose |
|-----------|------|---------|
| Experiment tracking | MLflow (already deployed) | Log params, metrics, artifacts per run |
| Model registry | MLflow Model Registry | Version models, promote Staging→Production |
| Quality gate | `src/evaluation/gates.py` | Block promotion if RMSE/F1 gates fail |
| CI validation | GitHub Actions | Run `validate_contracts.py` + `gates.py` on PR |
| Deployment | Docker build + compose | Rebuild model image with new artifacts |

**Key Change:** Remove fixture staging from `cd.yml`. Instead, `cd.yml` should:
1. Pull trained artifacts from MLflow registry (or S3)
2. Build model image with real artifacts
3. Push to GHCR with version tag

### 5.4 Documentation Consistency

**Broken References Found:**

| File | Reference | Status |
|------|-----------|--------|
| `docs/disaster_recovery.md:15` | `orchestration/operators/backup.py` | Does not exist |
| `docs/disaster_recovery.md:70` | `spark-submit silver/etl_runner.py` | Dead (no PySpark) |
| `docs/RUNBOOK.md` | `data-engineering/scripts/export_marts.py` | Does not exist (now `gold_export_runner.py`) |
| `Makefile` `export` target | `docker exec ... scripts/export_marts.py` | Does not exist |
| `contracts/gold-to-ds.md` | `scripts/validate_all_marts.py` | Does not exist |
| `docs/phase1_summary.md` | "PySpark 4.1.2" | Historical/deprecated |
| `docs/SMOKE_TEST.md` | `data-science/marts/sample` | Must be generated first |

### 5.5 Cleanup Checklist

| Item | Location | Action | Est. Space |
|------|----------|--------|------------|
| Docker build cache | Global | `docker builder prune -f` | ~14 GB |
| PostgreSQL volumes | `elyssa_pg_data` | `docker compose down -v` after extraction | ~97 GB |
| Python caches | All modules | `find . -type d -name __pycache__ -exec rm -rf {} +` | ~100 MB |
| .venv directories | DE/DS/WA | Delete and recreate | ~2 GB |
| node_modules | `web-application/client/` | `rm -rf node_modules && npm ci` | ~500 MB |
| dbt target/logs | `data-engineering/gold/target/`, `gold/logs/` | Delete after pipeline run | ~500 MB |
| WSL2 VHD | `%LOCALAPPDATA%\Packages\...` | `Optimize-VHD` monthly | Variable |

---

## 6. Aggressive Optimisation Plan

### DE Optimisations

| # | Area | Technique | Before | After (Est.) |
|---|------|-----------|--------|-------------|
| DE-O1 | dbt test | Pre-compute PK indexes for slow uniqueness tests | 57m + 32m | 2–5 min each |
| DE-O2 | dbt run | Incremental materialization for large marts | 2h 58m | 45–60 min |
| DE-O3 | dbt test | Raise threads 2→3 **max** (4 threads on 2C/4T risks OOM at 2 GB package) | — | ~1.5x test parallelism |
| DE-O4 | Gold export | 2 parallel export workers (3 tables each, `memory_limit` 1 GB/worker) | 19m | 8–10 min |
| DE-O5 | Silver export | Keep `threads=2`; split export into 2 workers over 16 shards | 20m | ~12–14 min |
| DE-O6 | DuckDB | Enable jemalloc allocator | — | ~10% memory reduction |
| DE-O7 | Delta detection | Hash-based diff instead of full reload | 20m | 5 min |

### DS Optimisations

| # | Area | Technique | Before | After (Est.) |
|---|------|-----------|--------|-------------|
| DS-O1 | Embeddings | INT8 quantize DistilBERT | 29.2 titles/s | 90–120 titles/s |
| DS-O2 | Embeddings | Cache hit (already done) | 140 min | 0 min |
| DS-O3 | Training | float32 end-to-end | float64 | 2x memory reduction |
| DS-O4 | Optuna | Parallelize CatBoost trials | Serial | 2–3x with joblib |
| DS-O5 | SHAP | TreeExplainer (already done) | 11m 14s | ~30s |

### WA Optimisations

| # | Area | Technique | Before | After (Est.) |
|---|------|-----------|--------|-------------|
| WA-O1 | DuckDB | Lazy-load with connection pooling | Cold start ~30s | ~5s (pooled) |
| WA-O2 | Search | Cursor-based pagination with infinite scroll | Capped at 50/100 | Unlimited |
| WA-O3 | Posters | OpenPosterDB with Redis caching | None | <100ms per poster |
| WA-O4 | Docker | Multi-stage builds, .dockerignore | Bloated images | 50–70% smaller |
| WA-O5 | Frontend | Code splitting (already done with React.lazy) | — | Verified |

### 6.4 Hardware-Constrained Amendments (Approved — AMD Athlon 200GE · 2C/4T · 13.9 GB usable RAM)

**Reference baseline:** 2 physical cores / 4 logical threads; ~13.9 GB usable RAM; WSL2 cap 8 GB; container memory budget postgres 2.0g + airflow 2.5g + etl-runner 2g + rustfs 256m + api 512m + redis 256m ≈ 7.5 GB worst case. Earlier runs flirted with 93–98 % host RAM during Silver peak.

**Threading doctrine (2 cores — memory-bound stages do not scale with 4 threads):**

| Setting | Approved value | Rationale |
|---|---|---|
| DuckDB `threads` (ingest/transform/export) | **2** (one per physical core) | 4 threads on 4 logical threads adds context-switch overhead; memory is the bottleneck |
| DuckDB `memory_limit` (runners) | 1.5 GB + spill `temp_directory` (1.25 GB cap) | Keeps 2 concurrent runners ≤ 3.2 GB combined |
| dbt `threads` (profiles.yml) | 2 default; **3 max** for test phase only | 4 threads caused OOM during tests |
| Gold export | 2 workers × 3 tables, 1 GB memory_limit each | ~2.2 GB peak; halves 19 min → 8–10 min |
| Silver export | threads=2, split shard list across 2 workers | ~12–14 min (was 20 min serial) |
| Torch (`set_num_threads`) | 2 for embedding; batch 128; `max_length` 32 | Measured sweet spot on 4T; also reduces CPU-DRAM thrash |
| Airflow parallelism | Keep `MAX_ACTIVE_TASKS_PER_DAG=1` + parallelism 1 | Never run two memory-heavy stages concurrently |
| jemalloc | Set `LD_PRELOAD`/`duckdb` allocator flag in etl-runner | ~10 % memory reduction on DuckDB allocations |
| Any river stage swap | WSL autoMemoryReclaim=gradual + swap 2 GB | Bounded paging instead of host OOM |

**Cheapest-first optimisation ladder (max value per hour on this rig):**
1. Skip `agg_actor_cooccurrence` in dbt runs (**−22 % dbt run**).
2. Pre-compute PK indexes for the 2 slowest uniqueness tests (57m + 32m → ~2–5 min each).
3. dbt incremental for `dim_title`/`dim_person`/`fact_performance` (full-refresh 2h58m → 45–60 m on re-runs).
4. Hybrid delta detection (Gold append 20 m → ~5 min on stable days).
5. INT8-quantized DistilBERT via ONNX Runtime (29.2 titles/s → 90–120/s; AVX2 supported by 200GE).
6. 2-worker parallel exports (Silver 20 m → 12–14 m; Gold 19 m → 8–10 m).

**Not targeted on this rig:** any stage exceeding ~4 GB single-process heap; GPU paths; parallel dbt > 3 threads; concurrent DS training + DE runs.

---

## 7. Open Questions for User Customization

| # | Question | Options | Recommendation |
|---|----------|---------|----------------|
| Q1 | SCD strategy per Gold table? | SCD Type 2 (full history) vs SCD Type 1 (latest only) vs Hybrid | SCD Type 2 for `dim_title`, `dim_person`; SCD Type 1 for facts |
| Q2 | Authentication provider? | JWT (current) vs OAuth2 (Google/GitHub) vs Session-based | JWT with rotation (current approach, hardened) |
| Q3 | Poster image resolution & cache policy? | Low (300px) / Medium (500px) / High (original) + TTL | Medium (500px), 7-day Redis cache |
| Q4 | Deployment environment? | Local WSL2 vs Cloud VM vs Kubernetes | Local WSL2 for dev; Cloud VM for prod |
| Q5 | Bronze snapshot retention? | 7 days / 30 days / 90 days / forever | 30 days (align with S3 lifecycle) |
| Q6 | Real-time features needed? | Batch only vs WebSocket live updates vs SSE | Batch only (current scope) |
| Q7 | GPU for DistilBERT? | CPU-only (current) vs GPU acceleration | CPU-only with INT8 quantization |
| Q8 | MLOps tool choice? | MLflow (current) vs DVC vs Both | MLflow for tracking/registry + DVC for data versioning |
| Q9 | CI/CD deployment trigger? | Push to main vs Tag-based vs Manual approval | Tag-based (`v*`) with manual approval gate |
| Q10 | Documentation format? | Single BLUEPRINT.md vs Multi-file suite vs Wiki | Single BLUEPRINT.md (this document) |

### 7.1 Approved Decisions (owner sign-off 2026-08-09)

All ten open questions resolved below. Decisions are hardware-bound (AMD Athlon 200GE / 13.9 GB) and final unless the plan is explicitly revisited.

| # | Decision | Approved | Rationale |
|---|----------|----------|-----------|
| Q1 | **Hybrid SCD:** SCD2 (history) for `dim_title`, `dim_person`; SCD1 upsert for `fact_title_rating`; append-only for `fact_title_principal`, `fact_performance`, `fact_episode` | ✅ | Full history on 100M-row facts is prohibitive on 2C/4T; dims are small enough (12M/15M) for SCD2 |
| Q2 | **JWT (current) + hardened:** rotation, reuse detection, family revocation, rate-limited login/refresh | ✅ | Keeps existing stack; OAuth2 deferred to v1.1+ |
| Q3 | **Posters:** 500px medium, Redis cache 7-day TTL, lazy fetch + top-100 pre-warm | ✅ | Redis capped at 256 MB in compose |
| Q4 | **Local WSL2** (dev) + **single Cloud VM** (prod, compose); Kubernetes deferred | ✅ | Matches reference rig; terraform `mlops/infra` retained for future |
| Q5 | **Bronze retention:** 14 days local / 30 days S3 lifecycle | ✅ | Full-snapshot pipeline stores ~14 GB/day Parquet; 30-day local on 500 GB disk is risky |
| Q6 | **Batch only** — no WebSocket/SSE real-time | ✅ | Out of scope for v1.0 |
| Q7 | **CPU-only + INT8 (ONNX-RT) quantization** — no GPU | ✅ | No GPU on rig; INT8 gives 3–6x CPU throughput (AVX2 present) |
| Q8 | **MLflow only** (tracking + registry); DVC deferred | ✅ | Lightweight local-first; add DVC if cross-env reproducible pipelines appear |
| Q9 | **Tag-based deploy (`v*`) + manual approval** in CD | ✅ | Follows existing rc.1/rc.2 convention; prevents accidental deploys |
| Q10 | **BLUEPRINT.md (single doc) + task checklists** per module | ✅ | `docs/final-release/` holds BLUEPRINT.md + WA_IMPLEMENTATION_TODO.md; further module checklists to follow |

**Sequencing remains P1 WA → P2 DS → P3 DE → P4 Infra.** P1 (WA) is next and fully scoped in `docs/final-release/WA_IMPLEMENTATION_TODO.md`.

---

## 8. Deliverables List

### Code Deliverables

| # | Deliverable | Module | Files | Status |
|---|-------------|--------|-------|--------|
| CD1 | Auth fix (cookie flags, rotation, rate limiting) | WA | `auth/router.py`, `auth/utils.py`, `config.py` | TODO |
| CD2 | OpenPosterDB integration service | WA | `services/poster.py` (new), `resolvers.py` | TODO |
| CD3 | GraphQL pagination (frontend) | WA | `gold.ts`, `Search.tsx`, `Browse.tsx` | TODO |
| CD4 | Crew display fix | WA | `TitleDetail.tsx`, `CastList.tsx` | TODO |
| CD5 | Docker build optimization | WA/Infra | `Dockerfile`, `.dockerignore` x3, `docker-compose.yml` | TODO |
| CD6 | DS leakage fix | DS | `src/features/engineering.py` (remove `avg_rating_genre_year`) | TODO |
| CD7 | DS inference pipeline fix | DS | `src/inference/pipeline.py` (CLS, max_length, preprocessor) | TODO |
| CD8 | DS notebook re-run | DS | `scripts/run_pipeline.py --stage all` | TODO |
| CD9 | Credential consolidation | DE | `.env.example`, `docker-compose.yml`, DAGs, operators | TODO |
| CD10 | PySpark cleanup | DE | 14 files (remove/rewrite stale references) | TODO |
| CD11 | CI gate fix | DE/Infra | `.github/workflows/ci-de.yml`, `ci.yml` | TODO |
| CD12 | Delta detection script | DE | `scripts/detect_delta.py` (new) | TODO |
| CD13 | MLOps pipeline fix | Infra | `.github/workflows/cd.yml`, `Dockerfile.model` | TODO |

### Documentation Deliverables

| # | Deliverable | Files | Status |
|---|-------------|-------|--------|
| DD1 | Updated contracts | `contracts/api-to-frontend.md`, `gold-to-ds.md` | TODO |
| DD2 | Fixed RUNBOOK | `docs/RUNBOOK.md` (update broken paths) | TODO |
| DD3 | Fixed disaster recovery | `docs/disaster_recovery.md` (remove PySpark refs) | TODO |
| DD4 | Updated Makefile | `Makefile` (fix `export` target) | TODO |
| DD5 | Updated .gitignore | Root + module-level `.gitignore` | TODO |
| DD6 | Model cards | `data-science/docs/model_cards/` (new) | TODO |

### Test Deliverables

| # | Deliverable | Module | Status |
|---|-------------|--------|--------|
| TD1 | Auth integration tests | WA | TODO |
| TD2 | DE test suite (rewrite) | DE | TODO |
| TD3 | DS contract validation | DS | TODO |
| TD4 | Docker build smoke test | Infra | TODO |
| TD5 | QA catalog (58 checks) | Cross-module | TODO |

---

## 9. Review Gates & Approval

### PR Checklist (for every merge to main)

- [ ] All CI workflows pass (real pytest, not `|| echo`)
- [ ] No hardcoded credentials (grep validation)
- [ ] No PySpark references in live code
- [ ] Contracts updated if schemas changed
- [ ] Docker build succeeds with no warnings
- [ ] Auth tests pass (register, login, refresh, /me)
- [ ] DS quality gates pass (or documented exceptions)
- [ ] DE pipeline completes end-to-end (or documented degradation)
- [ ] Documentation reflects current codebase

### Staging Deployment Gate

- [ ] All PR checks pass
- [ ] Docker images built and pushed to GHCR
- [ ] MLflow model registry updated (Staging stage)
- [ ] Manual smoke test on localhost:5173
- [ ] Auth flow verified (register → login → refresh → /me)
- [ ] Search/browse with pagination works
- [ ] Poster images load (OpenPosterDB running)
- [ ] Predictions return non-zero values

### Production Release Gate

- [ ] All staging checks pass
- [ ] MLflow models promoted to Production stage
- [ ] Quality gates pass (RMSE ≤ 0.55, F1 > 0.60 — or documented exceptions)
- [ ] Credential rotation completed
- [ ] PostgreSQL volume backup verified
- [ ] WSL2 .wslconfig applied
- [ ] Docker build cache pruned
- [ ] Documentation reviewed and approved

---

## Appendix A: Evidence Index

| Reference | Source | Lines |
|-----------|--------|-------|
| Pipeline runtime 26,592s | `data-engineering/docs/pipeline_performance_metrics.md` | 4–6 |
| Peak RAM 1.126GB | `data-engineering/docs/pipeline_performance_metrics.md` | 80–94 |
| dbt test 57m 23s | `data-engineering/gold/dbt_test.log` | 99 |
| dbt run 10,681s | `data-engineering/gold/dbt_run.log` | 39 |
| Auth 409 cause | `web-application/api/app/auth/models.py` | 56–58 |
| Auth cookie flags | `web-application/api/app/auth/router.py` | 51–58, 70–78 |
| JWT expiry 15min | `web-application/api/app/config.py` | 37 |
| Poster hardcoded None | `web-application/api/app/graphql/resolvers.py` | 125, 325 |
| Crew dropped | `web-application/client/src/pages/TitleDetail.tsx` | 34 |
| Search cap 50 | `web-application/client/src/api/gold.ts` | 154–161 |
| Leakage 91% importance | `catboost_rating_model.cbm` analysis | — |
| Inference CLS vs mean | `src/inference/pipeline.py` vs `src/features/text.py` | — |
| PySpark in 14 files | grep results | — |
| CI `pytest \|\| echo` | `.github/workflows/ci-de.yml` | 27–28 |
| 22+ credential files | grep results | — |
| DuckDB `hash(*columns(*))` | Stack Overflow / DuckDB docs | — |
| OpenPosterDB API | `github.com/PNRxA/openposterdb/docs/api.md` | — |
| DistilBERT INT8 4.1x | Intel arXiv 2211.07715 | — |
| FastAPI JWT best practices | KowashLab 2026, Navspace 2026 | — |
| WSL2 `.wslconfig` | Microsoft docs, rostand.dev 2026 | — |

---

*Blueprint generated 2026-08-09 by Elyssa-IMDb orchestrator. Awaiting user review and approval.*
