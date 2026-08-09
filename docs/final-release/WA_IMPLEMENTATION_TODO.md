# Elyssa — WA Final Release Implementation Checklist (WA-only)

**Owner:** Web Application module  
**Baseline:** `docs/final-release/BLUEPRINT.md` v1.1.0 (Approved)  
**Priority order:** P1 WA runs first — everything below is WA-only; DS/DE/Infra phases are out of scope here.  
**QA rule:** no task is "done" until its QA evidence column is green and recorded in the PR. The QA catalog `docs/qa_catalog_template.md` checks **36–54 (Web)** must pass at the end.

---

## 0. Definition of Done (for the whole phase)

- [ ] All tasks WA-01 … WA-24 closed, each with QA evidence.
- [ ] `cd web-application/api && python -m pytest tests/ -q` → **0 failures** (no `|| echo` anywhere).
- [ ] `cd web-application/client && npm run lint && npm run build` → clean.
- [ ] `npx playwright test` (client e2e including new auth/pagination specs) → green.
- [ ] `docker compose -f mlops/docker-compose.yml config -q` → no error; `docker compose up -d --build` on clean host starts api/model/frontend without pulling `elyssa-*` images.
- [ ] Manual smoke: register → login → refresh → `/auth/me`; search loads pages; title detail shows Cast **and** Crew; posters load; browse has infinite scroll.
- [ ] Lighthouse (LHCI) desktop performance ≥ 80 and no console errors on deploy preview.

---

## 1. Auth — restore registration/login/refresh loop (BLUEPRINT §2.1, tasks A1–A4)

| ID | Task | Files | Strict QA (evidence required) | ✅ |
|-----|------|-------|-------------------------------|----|
| WA-01 | Unify cookie flags: `secure` derives from `request.url.scheme` on register as on login (HTTP dev → `Secure` must be absent) | `api/app/auth/router.py` (register block) | pytest: `tests/test_auth.py::test_register_sets_insecure_cookie_on_http`; curl: `curl -i -X POST :8000/auth/register -d '{"email":"qa1@elyssa.local","password":"Qa1234567!"}'` → **200 + `refresh_token=...; HttpOnly; SameSite=lax` without `Secure`** | ☐ |
| WA-02 | Refresh token rotation: every `/auth/refresh` mints a NEW refresh token and stores its SHA-256 in SQLite (`refresh_tokens` table) | `api/app/auth/router.py`, `auth/models.py` (new table + migration), `auth/utils.py` | pytest: `test_refresh_rotates_token`, `test_refresh_reuse_detected_401` (old token reused → **401**), `test_refresh_family_revoked` | ☐ |
| WA-03 | Logout revokes whole family (delete all rows for `family_id`) | `auth/router.py` | pytest: `test_logout_revokes_family` (refresh → 401 after logout) | ☐ |
| WA-04 | Rate limit `/auth/login`, `/auth/register`, `/auth/refresh` (slowapi 5/min per IP) | `api/app/main.py` (middleware), `auth/router.py` | pytest: 6th rapid login → **429**; throttle values in config | ☐ |
| WA-05 | JWT secret must come from env only in prod (fail-fast if default used outside `ENVIRONMENT=dev`) | `api/app/config.py` | unit: `test_config_rejects_default_secret_in_prod`; grep CI for secret leaks | ☐ |
| WA-06 | CORS: exact origins list, never `*` with credentials; allow PATCH/PUT if added by new endpoints | `api/app/main.py` | pytest: preflight `OPTIONS /auth/login` from `http://localhost:5173` → `200` with `access-control-allow-origin` echoing origin only | ☐ |
| WA-07 | Update contract doc: JWT expiry **15 min**, refresh 7 days rotated; document cookie flags | `contracts/api-to-frontend.md` | doc diff review; `grep -rn "24 hours" contracts/` → 0 hits | ☐ |
| WA-08 | Frontend: handle 401 from `/auth/me` by refresh-then-retry; surface "session expired" toast; store access token in memory only (no localStorage) | `client/src/hooks/useAuth.tsx` | Playwright `tests/e2e/auth.spec.ts`: register → logout → login flow passes; no access-token in localStorage after login | ☐ |

Gate: WA-01..08 → `pytest tests/test_auth*.py` green + e2e spec green.

---

## 2. OpenPosterDB — poster service + cache (BLUEPRINT §2.2, tasks P1–P5)

| # | Task | File | Strict QA | ✅ |
|-----|------|-------|-----------|----|
| WA-09 | New `PosterService`: GET `{ELYSSA_POSTER_BASE_URL}/v1/{kind}/{imdb_id}` (kind=poster), timeout 3s, retry-once with backoff | `api/app/services/poster.py` (new) | unit: mocked httpx returns URL; failure → `None` (no crash); `test_poster_timeout_returns_none` | ☐ |
| WA-10 | Redis transport cache 7-day TTL per tconst; key `poster:{imdb_id}`; eviction aware (redis 256 MB) | `poster.py`, `api/app/cache/` | integration (redis-flavor local): hit/miss counters; `redis-cli TTL poster:tt0111161` ≥ 604800−ε; miss when key absent | ☐ |
| WA-11 | Wire resolver: `posterUrl` returns URL from service, `None` only when downstream unavailable | `api/app/graphql/resolvers.py` (`resolve_title`, `resolve_person`) | GraphQL query `{ title(id:"tt0111161"){ posterUrl } }` → non-null URL; with poster service stopped → `null` | ☐ |
| WA-12 | Pre-warm top-100 rated titles in background at API startup (non-blocking task) | `api/app/main.py` lifespan | warmup logs: `prewarm poster: 98/100`; no startup delay > 2s | ☐ |
| WA-13 | Frontend: render `<img loading="lazy">` with text fallback when `posterUrl` null; add `onerror` → hide | `client/src/components/MediaCard.tsx`, `TitleHero.tsx` | Playwright: title-detail page has ≥1 `img[src*=poster]`; network: no 404/403 images (LHCI errors-in-console clean) | ☐ |
| WA-14 | Policies: docs + compose script for OpenPosterDB (self-host optional) | `docs/`, `Makefile` target `posters-up` | doc review; `docker compose -f mlops/docker-compose.yml ps poster*` shows healthy when enabled | ☐ |

---

## Phase C: Pagination + Crew UX (BLUEPRINT §2.3)

| # | Task | File | Strict QA | |
|-----|------|-------|----------------|----|
| WA-15 | Search: rewrite with TanStack `useInfiniteQuery`, cursor from `data.search.cursor/hasMore`, page size 20; stop when `hasMore=false` | `client/src/api/gold.ts`, `client/src/pages/Search.tsx` | Playwright `e2e/search-pagination.spec.ts`: type "the"; assert 3 successive `loadmore` fetches produce unique 20-items sets and no overlap; last page `hasMore=false` | ☐ |
| WA-16 | Browse: same infinite scroll for genre/decade/top-rated routes | `Browse.tsx`, `gold.ts` | static check for monotonic cursors in network log: ≥2 distinct `after` values across load-more requests; no repeated cursor values (no duplicate page) | ☐ |
| WA-17 | Crew section: `TitleDetail.tsx` extracts `title.crew`, filters `director`/`writer` categories; renders "Directors"/"Writers" lists | `TitleDetail.tsx`, new `CrewList.tsx` | Playwright `title-detail.spec.ts`: assert DOM contains known director name (e.g., `Christopher Nolan` for `tt1375666`); assert no actor in crew section | ☐ |
| WA-18 | REST `/api/v1/titles/{tconst}` returns directors/writers consistent with GraphQL crew | `api/app/api/v1/router.py` (already has director/writer arrays) | pytest: field parity test `test_crew_consistent_graphql_rest` | ☐ |

---

## Phase D: Docker build & release hardening (BLUEPRINT §2.4, tasks D1–D6)

| # | Task | File | Strict QA | Gate |
|----|------|-------|-----------|------|
| WA-19 | `api` Dockerfile: multi-stage; final runtime has prod-only python deps (no torch/catboost unless model baked); non-root user | `web-application/api/Dockerfile` | `docker build web-application/api` succeeds under 2 GB memory (`--build-arg` limit or `docker stats`); `docker run --rm --user 10001:10001` works; `docker exec ... id -u` ≠ 0 | ☐ |
| WA-20 | `.dockerignore` x2 (api, client): exclude `.venv/`, `node_modules/`, `dist/`, `test-results/`, `.pytest_cache/`, `__pycache__`, `*.pyc` | `web-application/api/.dockerignore`, `web-application/client/.dockerignore` | `docker build` log shows "COPY excluded" hints; image size delta measured: build context `du -sh .` vs `docker context` listed files; < 50 MB context | ☐ |
| WA-21 | Compose: remove `image:`-pull pattern for local builds; add `build:` everywhere; ensure `docker compose -f mlops/docker-compose.yml up -d` builds missing images (`--build` documented in wrapper `make web-up`) | `mlops/docker-compose.yml`, `Makefile` | `docker compose -f mlops/docker-compose.yml up -d --build` succeeds w/o `pull` errors; `docker image ls elyssa-* | wc -l` grows; port map non-conflicting (frontend 3000 ↔ Grafana 3001) | ☐ |
| WA-22 | Resource budgets in compose: api `mem_limit 512m`, model 2g, frontend 256m, redis 256m; `restart: on-failure` | `mlops/docker-compose.yml` | `docker stats --no-stream` after up: values within limits; healthchecks pass | ☐ |
| WA-23 | Healthchecks on all root services + `depends_on: service_healthy` chain api→redis; frontend depends api | compose file | `docker compose -f ... ps` → api/redis healthy within 60s; healthcheck exit codes | ☐ |
| WA-24 | CI `ci-web.yml`: no `|| echo` swallow; real pytest gate; LHCI upload; trivy on final images | `.github/workflows/ci-web.yml` | Workflow run on branch → pytest job FAILS when a test fails (probe with a failing test) | ☐ |

---

## Phase E: Performance (BLUEPRINT §6 WA‑O1/O2, light)

| # | Task | QA |
|----|------|-----|
| WA-25 | DuckDB: keep lazy loads but create a single shared cached connection (dedupe `_get_con` vs `get_duckdb`); parallel `parquet_scan` for marts >2 GB | cold-start timer: first GraphQL query < 5 s (was ~30 s claim); `pytest tests/test_duckdb_single_instance` |
| WA-26 | Pre-warm model artifacts at startup (already via lifespan) — keep; add warm `/models` readiness payload for compose healthcheck | `curl :8000/api/v1/models` at T+10s (after startup) returns loaded=true |
| WA-27 | LHCI CI gate (already): keep ≥80 desktop; archive reports | `.github/workflows/ci-web.yml` LHCI artifact `artifacts/` |

---

## Phase F: QA catalog sign-off (web subset §C checks 36–54)

Run `docs/qa_catalog_template.md` checks 36–43 (Web Application) + 55–58 (cross-module) and attach results to release PR.

| Check | Result | Evidence |
|-------|--------|----------|
| W-36 auth register/login/refresh | ✅ / ❌ | curl + playwright records |
| W-37 `/auth/me` 200 after refresh | ✅ / ❌ | curl |
| W-38 search returns paged | ✅ | playwright network trace |
| W-39 title detail + crew | ✅ | screenshot + DOM assert |
| W-40 posters render | ✅ | LHCI console clean, no 404s |
| W-41 browse decade/genre/page | ✅ | playwright |
| W-42 watchlist CRUD | ✅ | playwright |
| W-43 404 handling | ✅ | GET /nonexistent → 404 page |

---

## Commit policy for this phase

Each task lands in one commit (conventional style `fix(wa): …`); PRs must be updated with QA evidence before merge; no `&& echo` / `|| true` swallowing in CI YAML (grep check in CI).

**Next:** after this checklist is complete → DS phase (P2).