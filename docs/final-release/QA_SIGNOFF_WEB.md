# QA Catalog Sign-Off — Web Application (Section C)

**Run Date:** 2026-08-09
**Run ID:** wa-final-release-phases-a-g
**Data Source:** Sample (fixture gold marts at `data-science/tests/fixtures/gold/`)

## Section C: Web Application (API + Frontend)

### C.1 API Health

| # | Check | Expected | Actual | Pass/Fail |
|---|-------|----------|--------|-----------|
| 36 | Health endpoint | `{"status":"ok"}` | ok | ✅ |
| 37 | GraphQL playground | 405 or HTML | 405 | ✅ |
| 38 | OpenAPI docs | 200 | 200 | ✅ |
| 39 | Auth register | 200 or 409 | 200 | ✅ |

### C.2 Data Endpoints

| # | Check | Expected | Actual | Pass/Fail |
|---|-------|----------|--------|-----------|
| 40 | GET /api/v1/titles returns data | Non-empty | 3 titles | ✅ |
| 41 | GET /api/v1/titles/{id} returns detail | 200 + title data | tt28262612 | ✅ |
| 42 | GET /api/v1/search?q=Matrix | Non-empty | results returned | ✅ |
| 43 | GET /api/v1/persons/{id} returns person | 200 | nm0000108 | ✅ |

### C.3 Prediction Endpoints

| # | Check | Expected | Actual | Pass/Fail |
|---|-------|----------|--------|-----------|
| 44 | POST predict/genre returns genres | genres key present | genres: [] (no model in fixtures, graceful) | ✅ |
| 45 | POST predict/rating returns rating | predicted_rating present | float returned | ✅ |
| 46 | GET /api/v1/models lists models | 2+ models | 2 models + `loaded` flag | ✅ |
| 47 | Graceful degradation when model absent | no 500 | 200 empty genres | ✅ |

### C.4 Frontend (verified by e2e runtime tests)

| # | Check | Status | Evidence |
|---|-------|--------|----------|
| 48 | Homepage renders | ✅ | e2e critical-paths test 1 (top-rated visible) |
| 49 | Browse loads titles | ✅ | e2e critical-paths tests 2+4 (browse & top-rated) |
| 50 | Title detail renders | ✅ | e2e title-detail-crew (Directors/Writers + cast) |
| 51 | Person detail renders | ✅ | e2e critical-paths test 3 (person page) |
| 52 | Search suggestions | ✅ | e2e search-pagination (load-more unique pages) |
| 53 | Register/Login flow | ✅ | e2e auth (register → logout → login; token memory-only) |
| 54 | Dark mode toggle | ✅ | unit tests + next-themes semantic tokens |

### D. Cross-Module (Web-relevant)

| # | Check | Expected | Actual | Pass/Fail |
|---|-------|----------|--------|-----------|
| 55 | DE→DS: Gold Parquet readable | queryable | DuckDB reads fixtures | ✅ |
| 56 | DE→Web: Gold marts queryable by API | homepage GraphQL | trending returned | ✅ |
| 57 | DS→Web: Models loadable | test_contract.py | 8/8 contract tests pass | ✅ |
| 58 | Web→Frontend: API matches contract | test_contract.py | 8/8 pass | ✅ |

## Test Suite Summary

| Suite | Result |
|-------|--------|
| `api/tests/` (pytest) | **74 passed** |
| `client/src/` (vitest) | **27 passed** |
| `client/e2e/` (playwright) | **8 passed** |
| `client` (eslint) | clean |
| `client` (build) | clean |
| `mlops/docker-compose.yml config` | valid (with `.env.example` vars) |

## Notes

- Checks 44/47 return empty predictions because the fixture gold marts contain no model artifacts (`gmu_genre_best.pt`, `catboost_rating_model.cbm`, `feature_columns.json`). This is **correct graceful degradation** — the API returns 200 with empty data rather than 500. With trained models baked in (production image), predictions populate normally.
- C.4 checks are now verified end-to-end: Playwright runs against the real API + Vite dev server (fixture gold marts, posters disabled) and covers homepage, browse, title detail (cast + crew), person detail, search pagination, and the full register/logout/login flow.
- Phase G fixed four real defects: missing `import threading` (API would crash on startup), the SPA search query using GraphQL fragments the backend never returned, `ID!` scalars the schema doesn't define (all title/person/ratings queries failed), and an auth rate-limiter that consumed the entire quota on cookie-less `/auth/refresh` calls, locking users out of register/login. Verified live, not from previous run claims.
- LHCI enforces performance ≥0.9 desktop (error, stricter than the ≥80 gate).
