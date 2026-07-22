# QA Catalog: Elyssa End-to-End Pipeline Validation

**Run Date:** {{DATE}}
**Run ID:** {{RUN_ID}}
**Data Source:** [ ] Full IMDb / [ ] Sample / [ ] Incremental

---

## Section A: Data Engineering (Bronze→Silver→Gold)

### A.1 Infrastructure Health

| # | Check | Command | Expected | Actual | Pass/Fail |
|---|-------|---------|----------|--------|-----------|
| 1 | PostgreSQL running | `docker ps --filter name=elyssa-postgres --format "{{.Status}}"` | `healthy` | | |
| 2 | Airflow running | `docker ps --filter name=elyssa-airflow --format "{{.Status}}"` | `healthy` | | |
| 3 | RustFS running | `docker ps --filter name=elyssa-rustfs --format "{{.Status}}"` | `healthy` | | |
| 4 | DuckDB available | `docker exec elyssa-airflow duckdb -c "SELECT 1"` | `1` | | |

### A.2 Pipeline Execution

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 5 | DAG triggered successfully | Run ID returned | |
| 6 | All tasks completed without failure | All tasks = `success` | |
| 7 | Pipeline runtime within bounds | < 6 hours | |

### A.3 Bronze Layer

| # | Check | Query | Expected | Pass/Fail |
|---|-------|-------|----------|-----------|
| 8 | title.basics row count | `SELECT COUNT(*) FROM bronze.title_basics` | ~12.6M | |
| 9 | name.basics row count | `SELECT COUNT(*) FROM bronze.name_basics` | ~15.4M | |
| 10 | title.principals row count | `SELECT COUNT(*) FROM bronze.title_principals` | ~100M | |
| 11 | No zero-row tables | `SELECT table_name, row_count FROM bronze.batch_metadata` | All > 0 | |
| 12 | No quarantined corrupt files | `SELECT COUNT(*) FROM silver.quarantine` | 0 | |

### A.4 Silver Layer

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 13 | 14 tables exist | `SELECT COUNT(*) FROM information_schema.tables WHERE table_schema='silver'` | 14 | |
| 14 | SCD2 active (is_current = TRUE) | `SELECT COUNT(*) FROM silver.title_basics WHERE is_current = TRUE` | > 0 | |
| 15 | No duplicate PKs | `SELECT COUNT(*) FROM (SELECT tconst, COUNT(*) FROM silver.title_basics GROUP BY tconst HAVING COUNT(*) > 1) AS dupes` | 0 | |
| 16 | Referential integrity (episode→title) | `SELECT COUNT(*) FROM silver.title_episode e LEFT JOIN silver.title_basics t ON e.parent_tconst = t.tconst WHERE t.tconst IS NULL` | 0 | |
| 17 | Latest batch ingested_at not stale | `SELECT MAX(ingested_at) FROM silver.batch_metadata` | < 24h from now | |

### A.5 Gold Layer

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 18 | 6 materialized tables exist | `SELECT table_name FROM information_schema.tables WHERE table_schema='gold' AND table_type='BASE TABLE'` | dim_title, dim_person, fact_title_principal, fact_performance, fact_episode, fact_title_rating |
| 19 | dim_title.tconst unique | dbt test `unique` | PASS | |
| 20 | dim_title.primary_title not null | dbt test `not_null` | PASS | |
| 21 | average_rating 0.0-10.0 | dbt test `accepted_range` | PASS | |
| 22 | dbt run + test: 0 ERROR | `dbt test` exit code | 0 | |
| 23 | Parquet export complete | `Get-ChildItem marts/full/*.parquet` | 6 files, > 0 MB each | |
| 24 | Export manifest present | `Test-Path marts/full/_MANIFEST.json` | True | |

---

## Section B: Data Science (Models)

### B.1 Artifact Presence

| # | Check | Path | Expected | Pass/Fail |
|---|-------|------|----------|-----------|
| 25 | Feature schema | `marts/processed/feature_columns.json` | Exists, valid JSON | |
| 26 | GMU model | `marts/processed/gmu_genre_best.pt` | Exists, loadable | |
| 27 | CatBoost model | `marts/processed/catboost_rating_model.cbm` | Exists, loadable | |
| 28 | Preprocessor | `marts/processed/preprocessor.joblib` | Exists, loadable | |
| 29 | MLB binarizer | `marts/processed/genre_list_mlb.joblib` | Exists, loadable | |
| 30 | Model inventory | `marts/processed/model_inventory.json` | Exists, valid JSON | |

### B.2 Quality Gates

| # | Check | Expected | Actual | Pass/Fail |
|---|-------|----------|--------|-----------|
| 31 | Rating RMSE | ≤ 0.55 | | |
| 32 | Genre Macro F1 | > 0.60 | | |
| 33 | Temporal generalisation (train-test Δ) | < 0.10 | | |
| 34 | All 18 required artifacts present | 18 files | | |
| 35 | MLflow metric naming compliant | No `@` or `+` in names | | |

---

## Section C: Web Application (API + Frontend)

### C.1 API Health

| # | Check | Command | Expected | Pass/Fail |
|---|-------|---------|----------|-----------|
| 36 | Health endpoint | `curl -s http://localhost:8000/health \| jq .status` | `"ok"` | |
| 37 | GraphQL playground | `curl -s http://localhost:8000/graphql` | 405 or HTML | |
| 38 | OpenAPI docs | `curl -s http://localhost:8000/docs` | 200 | |
| 39 | Auth register | `curl -s -X POST http://localhost:8000/auth/register` | 200 or 409 | |

### C.2 Data Endpoints

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 40 | GET /api/v1/titles returns data | Non-empty results | |
| 41 | GET /api/v1/titles/{id} returns detail | 200 with title data | |
| 42 | GET /api/v1/search?q=Inception returns results | Non-empty | |
| 43 | GET /api/v1/persons/{id} returns person | 200 | |

### C.3 Prediction Endpoints

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 44 | POST /api/v1/predict/genre returns genres | Non-empty genres array | |
| 45 | POST /api/v1/predict/rating returns rating | Float between 1.0-10.0 | |
| 46 | GET /api/v1/models lists registered models | 2+ models | |
| 47 | Graceful degradation when model absent | `{"error": ...}` | |

### C.4 Frontend

| # | Check | Expected | Pass/Fail |
|---|-------|----------|-----------|
| 48 | Homepage renders at http://localhost:5173 | 200, no console errors | |
| 49 | Browse page loads titles | Data visible | |
| 50 | Title detail page renders | All sections load | |
| 51 | Person detail page renders | Filmography visible | |
| 52 | Search returns suggestions | Dropdown appears | |
| 53 | Register/Login flow works | JWT received | |
| 54 | Dark mode toggle works | Theme switches | |

---

## Section D: Cross-Module Integration

| # | Check | Criteria | Pass/Fail |
|---|-------|----------|-----------|
| 55 | DE→DS: Gold Parquet readable by DS notebooks | `python -c "import duckdb; con=duckdb.connect(); con.execute(\"SELECT COUNT(*) FROM 'marts/full/dim_title.parquet'\").fetchone()"` | |
| 56 | DE→Web: Gold marts queryable by API | curl graphql homepage query | |
| 57 | DS→Web: Models loadable by ModelService | `python web-application/api/tests/test_contract.py` | |
| 58 | Web→Frontend: API response matches contract | `pytest web-application/api/tests/test_contract.py -v` | |

---

## Summary

| Section | Total Checks | Pass | Fail | Skipped | Pass % |
|---------|-------------|------|------|---------|--------|
| A. Data Engineering | 24 | | | | |
| B. Data Science | 11 | | | | |
| C. Web Application | 19 | | | | |
| D. Cross-Module | 4 | | | | |
| **Total** | **58** | | | | |
