# UNIFIED_ELYSSA_STATE.md — Post-Overhaul UI/UX Audit & Next-Sprint Roadmap

**Audit:** Senior Frontend Architect / UI-UX / DevOps review, 2026-08-11
**Evidence basis:** every claim below was re-verified against source code (`file:line`), the four merged documents, and the 2026-08-11 smoke run. Visual snapshot claims are marked confirmed / refuted / partially confirmed with code evidence.
**Merged sources:** `WA_IMPLEMENTATION_TODO.md` (WA-01…27) · `WA_REMNANT_CATALOGUE.md` (P1–P5, Q1–Q5) · `QA_SIGNOFF_WEB.md` (checks 36–58) · `openposterdb-policy.md`
**Status:** P1–P4 shipped (`ea85c03`, `994dede`, `bd62714`, `a8ab503`) · P5 DE delta scheduled (BLUEPRINT §8.5 piggyback) · **3 open blockers found this audit: KEY-1, KEY-2, KEY-3**

---

## 1. Visual Snapshot Claims → Verified Verdicts

| # | Visual claim (snapshot) | Verdict | Code evidence |
|---|---|---|---|
| V-1 | "Discover" carousel + "Top 10 this week" show dark blank boxes instead of posters | ✅ **CONFIRMED — backend bug, not hydration** | `_row_to_summary` `resolvers.py:72–77` never populates `poster_url`; only `resolve_title` (:154) and `resolve_person` (:409) call PosterService. All summary lists (featured/trending/topRated/similar/search/browse/knownFor/filmography) return `posterUrl: null`. `FeaturedCarousel.tsx:63–72` then renders an empty `bg-muted` box. |
| V-2 | Watchlist shows the Interstellar poster (base URL structure is correct) | ✅ **CONFIRMED** | Watchlist stores the detail-page `title_data` JSON (incl. resolved `posterUrl`) in SQLite (`auth/models.py:31–41`); `WatchlistGrid.tsx:71` renders it. Proves OPDB service + URL shape work — only summary rows skip resolution. |
| V-3 | Cast avatars are grey placeholder circles, not headshots | ✅ **CONFIRMED (partial)** | `_resolve_cast`/`_resolve_crew` (`resolvers.py:181–228`) build `PersonSummary(id, primary_name)` with **no headshot resolution**; `headshotUrl` is only fetched in `resolve_person` (:410). `CastList.tsx:27–39` falls back to a bare `User` icon (initials render only on image *load failure*, not on null). |
| V-4 | "Similar titles" pulls irrelevant obscure 10.0-rated films; adult titles appear | ✅ **CONFIRMED — root cause located** | `_resolve_similar` `resolvers.py:231–247`: genre `ILIKE` match, `ORDER BY average_rating DESC`, **no `num_votes` threshold, no Adult-genre exclusion**. Obscure 10.0 films surface first; adult titles match genre `Adult`. |
| V-5 | Display-name save is a no-op; UI still shows email | ⚠️ **PARTIALLY REFUTED — endpoint persists fine; separate serialization bug makes it look dead** | `PATCH /auth/me` (`auth/router.py:285–302`) + `update_user_display_name` (`auth/models.py:213–222`) work; `Account.tsx:15–29` fully wired; `test_patch_me_updates_display_name` passes. **But `/me` returns snake_case `display_name`** (`router.py:239` returns raw user dict) while the frozen contract (`client/src/api/auth.docs.ts:26`) and `User` type (`types.ts:147–151`) demand camelCase `displayName` → `Header.tsx:110` always falls back to email. |
| V-6 | Rating "history" is a compact text block, no graph | ✅ **REFUTED as defect — intended redesign, shipped** | P1 delivered exactly this: single snapshot → stat card (`RatingTimelineChart.tsx:33–57`); ≥2 snapshots → SVG sparkline + ▲/▼ delta (:59–108). Aligned with catalogue §2.3. Optional polish only: point dots/monthly ticks. |
| V-7 | Footer attributes TMDB ("not endorsed or certified") | ✅ **CONFIRMED** | `Footer.tsx:59`. TMDB attribution terms satisfied. |
| V-8 | Horizontal scroll bar at bottom of browse grid | ✅ **CONFIRMED** | Carousels use `overflow-x-auto` intentionally (`TopTenRow.tsx:16`). Cosmetic: standardize `[scrollbar-width:thin]` / chrome scrollbar styling across rows. |

---

## 2. [Accomplished]

- **UI overhaul complete:** cohesive dark editorial design, responsive card grids, legible title metadata, unified filter chips (GENRE/TYPE/DECADE/SORT/MIN_RATING), Browse Sheet drawer < lg, `?type=` footer links honored, `/browse/top-rated` fixed (§4.3/2.8.2, `bd62714`).
- **Home page:** "Discover" showcase with `FeaturedCarousel`, "Top 10 this week" ranked strip with number overlays, `TrendingRow`, `TopRatedRow`; no signup CTA (Q5 — showcase intent).
- **Title page:** hero poster + tagline + genre pills + popularity pill (`popularitySegment`), 2×2 metadata grid, watchlist toggle wired (`useWatchlist`, optimistic), cast card grid with character alignment, crew rows with human-readable role labels, rating-history stat card + sparkline.
- **TMDB enrichment (P3) live + attributed:** headshots/prose via `EnrichmentService` (SQLite cache 30 d, circuit breaker, negative caching, `enrich_person`/`enrich_title`), key-gated (`tmdb_api_key` empty → degrade to nulls).
- **OpenPosterDB:** documented endpoint contract (`{base}/{api_key}/imdb/poster-default/{id}.jpg`), HEAD content-type check, retry-once, Redis 7-day TTL, 404 negative cache, top-100 prewarm, failures never crash (`poster.py`).
- **Auth hardening (P1/P2):** token rotation + family revocation, single-flight refresh, anonymous-toast suppression, 401→refresh-then-retry, `PATCH /auth/me`, `DELETE /auth/account`, watchlist CRUD + notes (`PATCH /auth/watchlist/{id}`); `Account.tsx` 2-col layout, `Settings` mirrors real theme provider; e2e auth spec green.
- **Resilience (P1):** thread-safe per-thread DuckDB connections + connection close on reload-cache (`resolvers.py:108–135`), bounded memory cache, `ErrorBoundary` crash logging, episodes gated to series, crew null-guards, `formatRole` labels, unique keys.
- **QA (2026-08-09 signoff + 2026-08-11):** pytest 91/91, vitest 35/35, Playwright e2e green, eslint/build clean, checks 36–58 pass. Q1–Q5 all resolved by owner (catalogue §6).
- **P5 status:** API `known_for_ids` path code + tests shipped; DE export delta piggybacks next 7 h re-run per BLUEPRINT §8.5. No action in-sprint.

## 3. [Messy / Needs Fixing]

| ID | Issue | Evidence (`file:line`) | Root cause | Fix (modular, per WA FE/API split) |
|---|---|---|---|---|
| M-1 | **Home/Discover + Top-10 + Similar + Browse all render blank poster boxes** | `resolvers.py:72–77`, `:231–247`, `:517–557`; `FeaturedCarousel.tsx:63–72`; `TopTenRow.tsx:19–26` | `_row_to_summary` never resolves `poster_url`; OPDB URLs only resolved for detail pages | **API:** batch poster resolution for summary rows (Redis `mget` on `elyssa:poster:{id}`, fetch+fill misses). **FE:** `FeaturedCarousel` gains title-text fallback + `onError`→hide (mirror `MediaCard.tsx:39–54`) |
| M-2 | **Cast avatars grey circles** | `resolvers.py:181–228` (no `headshot_url`); `CastList.tsx:27–39` | Cast/crew `PersonSummary` never enriches headshots; null branch renders bare `User` icon | **API:** resolve headshots for cast (limit 20) via `EnrichmentService` (SQLite-cached, circuit-broken). **FE:** null-headshot branch renders `getInitials(name)` inside the circle (delete the bare-icon branch) |
| M-3 | **Similar-titles quality (broken carousel content)** | `resolvers.py:231–247`; `types.py:104–106` (passes `self.genres`) | Genre ILIKE + pure rating sort, no popularity floor, no Adult exclusion, no genre-overlap scoring | See KEY-2 (hotfix) + roadmap ticket S-A2 |
| M-4 | **Display name never appears in UI (email shown)** | `router.py:228–239`, `:285–302`, `:203` vs `types.ts:147–151`, `auth.docs.ts:26` | snake_case payload vs camelCase contract — contract violation, not missing endpoint | See KEY-3 (hotfix) |
| M-5 | **`FeaturedCarousel` crops 2:3 posters into 16:9 boxes** | `FeaturedCarousel.tsx:63` | `aspect-[16/9] object-cover` on a poster source | Switch to `aspect-[2/3]` or use backdrop enrichment (`backdrop_url` already cached in `enrich_title`) with poster fallback |
| M-6 | **Browse grid horizontal scrollbar styling inconsistent** | `TopTenRow.tsx:16` vs `TrendingRow.tsx`/`Browse.tsx` grids | One-off `scrollbar-width:thin` | Extract a `.carousel-row` utility class in `index.css` (thin, hover-styled, `prefers-reduced-motion` safe) |
| M-7 | **OPDB policy doc drift** | `openposterdb-policy.md:20–22` (3 s/1 retry) vs `poster.py:14–15` (10 s/2 attempts) | Doc not updated after timeout hardening | Update policy doc to 10 s/retry-once; add `elyssa:poster:*` + `elyssa:enrich:*` to the cache-key doc |
| M-8 | **Enrichment has no request pacing for bursts** | `enrichment.py:100–130` (`_get` retries; no queue) | Cold cast page = up to 20 TMDB `/find` calls | Accept for now (circuit breaker guards 5xx/429); batch prefill script for top-20k people is the long-term pacing (catalogue §3.3) |

## 4. [Critical Blockers]

Committed to the sprint backlog as P0 — nothing ships this sprint without them:

| Blocker | Impact | Status |
|---|---|---|
| **KEY-1 — Posters null on every summary surface** (home, top-10, similar, browse, search, filmography, known-for) | Visual evidence V-1/V-2: poster-rich app looks posterless | Confirmed in code; fix sized S (backend-only + 1 FE fallback) |
| **KEY-2 — Similar-titles recommendation garbage** (obscure 10.0 + adult titles) | Evidence V-4: carousel credibility destroyed on detail pages | Confirmed in code; fix sized S |
| **KEY-3 — Display-name serialization mismatch** (contract violation: snake_case vs camelCase `displayName`) | Evidence V-5: account settings appear non-functional to users | Confirmed in code; fix sized XS (backend response shape + 1 test) |

## 5. Policy Adherence Check (openposterdb-policy.md + TMDB terms)

**Verdict: COMPLIANT — 3 findings to note.**

| Requirement | Status | Evidence |
|---|---|---|
| OPDB documented endpoint + response-is-image | ✅ | `poster.py:47–63` (`{base}/{api_key}/imdb/poster-default/{id}.jpg`, HEAD + content-type gate) |
| Redis cache 7-day TTL per tconst, negative caching | ✅ | `poster.py:12,38–45` (key `elyssa:poster:{id}`, `""` for 404), 256 MB cap in compose |
| Pre-warm top-100 at startup | ✅ | `poster.py:84–93` (async lifespan task) |
| Downstream failure → `None`, UI degrades | ✅ | `poster.py:69–82`; `MediaCard.tsx:40–54` text fallback |
| Policy timeout/retry numbers match code | ⚠️ | doc says 3 s/1 retry; code is 10 s/retry-once (M-7) |
| TMDB attribution (logo + notice) | ✅ | `Footer.tsx:59` — "uses the TMDB API but is not endorsed or certified by TMDB" |
| TMDB results cached (no repeated hits) | ✅ | `enrichment.py` SQLite 30 d + negative caching + circuit breaker; OPDB Redis 7 d |
| Rate-limit respect / no stampede | ⚠️ | no explicit pacing loop in API path (cold cast page = ≤20 `find` calls once per nconst, then cache); recommended: Redis hot tier (7 d) for `headshot_url` of top-20k people + batch prefill with 5–10 req/s pacing (catalogue §3.3), plus optional `referrerPolicy="no-referrer"` on TMDB `<img>`s |
| Non-commercial use only | ✅ | no commercial endpoints/keys; OPDB self-hosted (`make posters-up`) |

**Caching strategy already in place:** Redis (posters, 7 d) + SQLite (enrichment, 30 d) + in-memory tier (resolvers `get_cache`). **Proposed addition:** Redis hot tier for headshots + single-flight per nconst in `EnrichmentService` (matters most the day the hot-set prefill runs).

---

## 6. [Next Sprint Roadmap]

Sprints ordered by dependency (backend truth first, UI second, QA last). Estimates: single experienced dev.

| Ticket | Scope | Files | Effort | Depends on | Acceptance |
|---|---|---|---|---|---|
| **S-A1 (P0)** Poster resolution for summary rows | Batch-resolve `poster_url` for trending/top-rated/featured/similar/search/browse/knownFor/filmography via Redis `mget` + miss-fill | `api/app/graphql/resolvers.py:72–77,231–247,517–557`; `api/app/cache/redis.py` (add `mget`) | 🟡 | — | GraphQL `{ homepage { trending { posterUrl } } }` returns non-null for ≥ 90 % of OPDB-known tconsts; pytest `test_summary_rows_have_posters` |
| **S-A2 (P0)** Similar-titles quality | Add `num_votes >= 1000`, exclude `Adult` genre, prefer genre-overlap score then rating; return posters (after S-A1) | `resolvers.py:231–247` | 🟢 | S-A1 | pytest: top-12 for `tt1375666` contain no Adult, no 10.0 with < 1000 votes; e2e E2E-003 green |
| **S-B1 (P0)** `/auth/me` contract fix | Return camelCase `displayName` alongside `display_name` on GET/PATCH/register/login user payloads (keep snake_case for BC); update pytest | `api/app/auth/router.py:203,228–239,285–302`; `api/tests/test_auth.py` | 🟢 | — | `test_patch_me_updates_display_name` asserts `displayName`; e2e E2E-001 green |
| **S-C1 (P1)** Cast headshots | Resolve `headshot_url` in `_resolve_cast`/`_resolve_crew` via EnrichmentService (already cached); single-flight guard | `resolvers.py:181–228`; `services/enrichment.py` (single-flight) | 🟡 | — | cast rows return non-null `headshotUrl` for enriched nconsts; no-TMDB-stampede test (`test_cast_headshot_cached`) |
| **S-C2 (P1)** Avatar + carousel fallbacks | `CastList.tsx:27–39` → initials fallback; `FeaturedCarousel.tsx:62–72` → text watermark + `onError` hide; aspect fix to 2:3 with backdrop fallback (M-5) | `CastList.tsx`, `FeaturedCarousel.tsx` | 🟢 | S-C1 (data) but can land standalone | vitest: fallback renders initials; visual contrast ok |
| **S-D1 (P2)** E2E suite | Land `account.spec.ts` (E2E-001), `watchlist.spec.ts` (E2E-002), `similar-titles.spec.ts` (E2E-003) in `client/e2e/` | `client/e2e/*.spec.ts` | 🟡 | S-A2, S-B1 | `npm run e2e` green on CI |
| **S-D2 (P2)** Docs/ops | Update `openposterdb-policy.md` timeout drift + cache keys + TMDB pacing note (M-7); optional Redis headshot hot tier + `referrerPolicy` (M-8) | `docs/final-release/openposterdb-policy.md` | 🟢 | — | doc diff review; policy table above matches code |
| **S-E1 (P3)** Polish (no-blocker backlog) | Carousel scrollbar utility (M-6), sparkline point dots/ticks (V-6 polish), prefill batch script for top-20k people (catalogue §3.3) | `index.css`, `RatingTimelineChart.tsx`, new `scripts/enrich_batch.py` | 🟡–🔴 | S-C1 | LHCI ≥ 80; vitest additions |
| **S-F1 (P5 DE)** `known_for_ids` piggyback | already scheduled on next 7 h pipeline re-run (BLUEPRINT §8.5, catalogue §3.2) | DE module | 🔴 (re-run) | — | `dim_person.known_for_ids` populated; API prefers `tconst = ?` |

**Definition of Done per ticket:** pytest green for touched modules · vitest for FE components · Playwright spec green · eslint/build clean · QA catalog checks 36–58 re-run at sprint end.

---

## 7. Debugging & Hotfix Plan (immediate execution order)

### 7.1 KEY-1 — Posters on summary rows (single root cause, one backend change)

1. Add `cache_mget(keys)` to `api/app/cache/redis.py` (fall back to a per-key loop when Redis is down so the memory tier stays safe).
2. In every `_row_to_summary` caller (trending, top_rated, homepage, search, browse, similar, known-for, filmography): collect `ids = [r[0] for r in rows]`, `urls = cache_mget(["poster:" + i for i in ids])`, fill Redis misses through `get_poster_service().get_poster_url(id)` (existing 7-day TTL + negative-cache semantics), then attach to each `TitleSummary`.
3. `FeaturedCarousel.tsx` fallback (independent, safe first commit): when `posterUrl` is null render the dark box with the title watermark (copy the `MediaCard` pattern) + `onError` → hide.

### 7.2 KEY-2 — Similar titles (one SQL rewrite + test)

```sql
SELECT tconst, primary_title, title_type, average_rating, start_year, num_votes, genre_list
FROM dim_title
WHERE tconst <> ?
  AND genre_list NOT LIKE '%Adult%'
  AND (genre_list ILIKE ? OR genre_list ILIKE ? OR genre_list ILIKE ?)
  AND average_rating IS NOT NULL
  AND num_votes >= 1000
ORDER BY average_rating DESC, num_votes DESC
LIMIT ?;
```

Rationale: the genre-match is the OR-clause; the 1000-vote floor kills the obscure 10.0 titles (same floor already used by `resolve_top_rated`, `resolvers.py:545` — consistency); `NOT LIKE '%Adult%'` blocks the Raw-page contamination. Optional next step: rank by genre-hit count before rating.

### 7.3 KEY-3 — Display-name contract (backend response shape only)

- Keep `get_user_by_id`/`update_user_display_name` returning snake_case dicts; wrap at the router boundary so every auth response also carries `displayName`: single helper `_public_user(user)` in `auth/router.py` used by `register`, `login`, `refresh`, `/me` GET, `/me` PATCH.
- Frontend: **no consumer change** — `User.displayName` (`types.ts:150`), `ProfileForm`, `Header.tsx:110` already read camelCase.
- Regression: extend `test_patch_me_updates_display_name` + add `test_me_returns_camelcase_display_name`.
- Manual gate: re-run the smoke — register → account → rename → refresh → header shows new name (the exact user report V-5).

### 7.4 S-C1 — Cast headshots (fill-in layer)

- In `_resolve_cast`/`_resolve_crew`: after the DuckDB join, annotate `PersonSummary` with `headshot_url = get_enrichment_service().get_person_headshot(nconst)` — SQLite-cached, circuit-broken; skip entirely when enrichment disabled (config gate).
- Add a single-flight keyed per nconst in `EnrichmentService._get` to prevent 20-way stampede on a cold cast page.
- FE: `CastList.tsx` no-headshot branch → `getInitials(primaryName ?? "?")` inside the circle instead of the bare `User` icon; keep `EntityLink` crew rows as-is.

---

## 8. End-to-End Tests (Playwright pseudo-code, `client/e2e/`)

> Matches repo conventions (`client/e2e/*.spec.ts`, Vite dev server + real API, fixture gold marts). Run: `cd web-application/client && npm run e2e`.

### E2E-001 — Account update (display name persists)

```typescript
// client/e2e/account.spec.ts
import { test, expect } from "@playwright/test";

test("E2E-001: display name persists across reload and shows in header", async ({ page }) => {
  const email = `audit-${Date.now()}@elyssa.local`;

  // Arrange: fresh account with a known display name
  await page.goto("/register");
  await page.getByLabel(/email/i).fill(email);
  await page.getByLabel(/password/i).fill("Qa1234567!");
  await page.getByLabel(/display name|name/i).fill("Audit User");
  await page.getByRole("button", { name: /register/i }).click();
  await expect(page).toHaveURL(/\/(browse|title)?/);           // logged-in landing

  // Act: rename on the Account page
  await page.goto("/account");
  await page.getByLabel(/display name/i).fill("Audit Renamed");
  await page.getByRole("button", { name: /save/i }).click();
  await expect(page.getByText("Profile updated")).toBeVisible(); // sonner toast
  await page.reload();                                          // persistence gate

  // Assert: form re-read from /me, header shows the new name, NOT email
  await expect(page.getByLabel(/display name/i)).toHaveValue("Audit Renamed");
  await expect(page.getByRole("banner")).toContainText("Audit Renamed");
  await expect(page.getByRole("banner")).not.toContainText(email);
});
```

### E2E-002 — Watchlist mechanism (add + notes interactable + notes persist)

```typescript
// client/e2e/watchlist.spec.ts
test("E2E-002: title → watchlist toggle → notes round-trip", async ({ page }) => {
  await test.step("login (shared helper loginAs(page, email))", async () => {
    // existing auth.spec.ts helper — register/login with seeded user
  });

  await page.goto("/title/tt1375666");                        // Interstellar
  await page.getByRole("button", { name: /watchlist/i }).click();
  await expect(page.getByRole("button", { name: /watchlist/i })).toHaveAttribute("aria-pressed", "true");

  await page.goto("/watchlist");
  const card = page.locator('a[href="/title/tt1375666"]');
  await expect(card).toBeVisible();

  const noteBtn = page.getByRole("button", { name: /add notes/i });
  await expect(noteBtn).toBeEnabled();                        // interactable (non-disabled)
  await noteBtn.click();
  await page.getByLabel(/notes for/i).fill("**Favourite**");
  await page.getByLabel(/notes for/i).blur();                 // autosave on blur (PATCH)
  await page.reload();                                        // persistence gate
  await expect(page.getByRole("button", { name: /edit notes/i })).toBeVisible();
  await page.getByRole("button", { name: /edit notes/i }).click();
  await expect(page.getByLabel(/notes for/i)).toHaveValue("**Favourite**");
});
```

### E2E-003 — Similar titles integrity (no adult / no obscure-10.0 in first 10)

```typescript
// client/e2e/similar-titles.spec.ts
test("E2E-003: similar carousel excludes adult + vote-poor 10.0 titles", async ({ page }) => {
  await page.goto("/title/tt1375666");                        // popular, mainstream

  // Data-level gate: intercept the GraphQL response (authoritative source)
  const similarData = page.waitForResponse((r) =>
    r.url().includes("/graphql") && r.request().postDataJSON()?.query?.includes("similar"),
  );
  await page.goto("/title/tt1375666");
  const resp = (await similarData).json();
  const entries = resp.data?.title?.similar ?? [];

  expect(entries.length).toBeGreaterThanOrEqual(10);          // full carousel
  for (const t of entries.slice(0, 10)) {
    expect(t.genres ?? []).not.toContain("Adult");            // no adult titles
    if (t.numVotes != null) expect(t.numVotes).toBeGreaterThanOrEqual(1000); // popularity floor
    // no "perfect 10.0 obscurities": 10.0 is allowed only if well-known
    if (t.averageRating >= 9.9 && (t.numVotes ?? 0) < 10_000) {
      throw new Error(`Implausible top recommendation: ${t.primaryTitle}`);
    }
  }

  // UI-level gate: carousel cards render poster images, not blank boxes
  const slides = page.locator('[aria-label*="More like this"], [aria-label*="Similar"] a');
  await expect(slides.first()).toBeVisible();
  await expect(slides.locator("img")).toHaveCount(await slides.count()); // every card has an <img>
});
```

### Regression additions (with existing specs)

| Spec | New expectation | Blocker it guards |
|---|---|---|
| `homepage.spec.ts` / `critical-paths.spec.ts` | "Discover" + "Top 10" cards each contain `img[src*=poster]` (or the title-watermark fallback, never an empty box) | KEY-1 |
| `title-detail.spec.ts` | cast avatars render either `img` or initials text (`[data-avatar-fallback]`), never a bare empty circle | S-C1/C2 |
| `auth.spec.ts` | after `PATCH /auth/me`, `/me` returns `displayName` (camelCase) — contract-level assert | KEY-3 |
| `browse.spec.ts` | browse grid scrolls with thin scrollbar utility class present | M-6 |

---

## 9. Execution Order & Verification Commands

1. `cd web-application/api && python -m pytest tests/ -q` (91 passing baseline; new: `test_summary_rows_have_posters`, `test_similar_excludes_adult`, `test_me_returns_camelcase_display_name`, `test_cast_headshot_cached`).
2. `cd web-application/client && npm run lint && npm run build` → clean; `npm run e2e` → new specs green.
3. Manual smoke: home posters visible → detail similar carousel sane (Interstellar: no Adult / no obscure 10.0, 0-vote rows) → account rename persists after reload → cast shows initials/headshots.
4. QA catalog checks 36–58 re-run; commits per ticket, one per commit, conventional style (`fix(api): …`, `test(e2e): …`).
5. Optional soak (if S-C1 lands): 10k mixed queries + 2× `reload-cache` under `docker stats` — memory flat, no DuckDB thread errors.

*End of UNIFIED_ELYSSA_STATE — ready for immediate sprint execution.*