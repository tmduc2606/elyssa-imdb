# Elyssa — Web Application Remnant Issue Catalogue & Enhancement Blueprint

**Module:** Web Application (API gateway + React SPA)
**Author:** WA remnant-catalogue orchestration (evidence-driven)
**Baseline:** `docs/final-release/WA_IMPLEMENTATION_TODO.md` (WA-01…WA-27) · `docs/final-release/BLUEPRINT.md` v1.1.0
**Evidence sources (mandatory, text-only):**
- `web-application/logs/Elyssa Layout - Interpretation & Feedback.md` ("Elyssa layout log")
- `web-application/logs/IMDb Layout - References.md` ("IMDb ref")
- `web-application/logs/Netflix Layout - References.md` ("Netflix ref")
- `web-application/logs/error_log.txt` ("error log")
- Code: `web-application/api/app/**` · `web-application/client/src/**` · Gold marts per `data-science/contracts/gold-to-ds.md` and `data-engineering/gold/models/marts/*.sql`

**Status:** Ready for project-owner review & execution. Every entry below is traced to a log line or an exact `file:line` in code.

---

## 1. Executive Summary

The Web Application skeleton is functional — auth, Gold-mart GraphQL/REST, pagination,
posters, watchlist, and a dark, editorial UI all exist. It falls short of the
IMDb/Netflix-inspired target in three ways:

1. **Correctness holes that look like data problems.** `Cast`/`Crew` rows show
   `Logo U - Unknown` because the backend *fabricates* the string `"Unknown"` when a
   `fact_title_principal.nconst` has no matching `dim_person` row
   (`resolvers.py:155/180/300`). Roles are rendered as raw snake_case DB values
   (`casting_director`), `"No episodes"` is shown on non-series titles, and the rating
   "history" widget draws one full-height green bar for a single daily snapshot.
2. **Frontend runtime defects confirmed in `error_log.txt`.** Duplicate React keys
   (`-undefined-null`, `-null-null`) and a null-deref crash
   (`EpisodeTable.tsx:46 → "Cannot read properties of null (reading 'id')"`) take the
   whole title page down to "Something went wrong loading this page." Anonymous visitors
   get spurious "Session expired" toasts because the auth restore path toasts on any
   refresh 401 (`useAuth.tsx:76`; error log lines 2–3 show the 401s).
3. **Under-utilised data.** The Gold marts *already contain* person names, character
   names, categories, and jobs (verified against `gold-to-ds.md` and the exported
   Parquet files on disk). No external API is needed for the core cast/crew fix. The
   genuinely missing pieces are **person headshots**, **plot/tagline text**, and
   **poster-URL reliability** — these come from a small, cached enrichment layer.

**Key decisions (recommended):**

| Decision | Choice | Rationale |
|---|---|---|
| Cast/crew names | **Fix in API + UI, no API needed** | `dim_person` join already exists; data is in Gold. `primary_name or "Unknown"` fallback is the bug, plus missing-name UX. |
| Person headshots | **TMDB `/find` (free tier), batch-precomputed + cached** | OMDb has no photos; OpenPosterDB serves posters/logos/backdrops **but no headshots**; Wikidata is keyless but slower and sparser. TMDB `/find?external_source=imdb_id` supports **people** (verified against TMDB docs). Non-commercial use is permitted with attribution. |
| Poster URLs | **Fix `PosterService` to OpenPosterDB's documented endpoint** | Current call `{base}/v1/poster/{id}` + `x-api-key` header is **not the documented OpenPosterDB contract** (`/{api_key}/imdb/poster-default/{id}.jpg`); must verify and adapt. Keep Redis 7-day TTL + negative caching. |
| Plot/tagline/trivia | **Optional TMDB overview/tagline, cached, flagged off by default** | Trivia is not in TMDB; Wikidata SPARQL is viable but low yield; keep as stretch. |
| `known_for_titles` correctness | **Tiny DE change: also export tconst IDs from Silver** | Gold drops IDs (names only), forcing a fuzzy `ILIKE` lookup per title (`resolvers.py:253–279`) — brittle; IDs already exist in `silver.name_known_for_title`. |

---

## 2. Bugfix & UX Remediation Plan (Priority 1 — Critical Fixes)

Legend for effort: 🟢 quick win (< 2 h) · 🟡 medium (< 1 day) · 🔴 involved (1–3 days).

### 2.1 Cast/Crew display — "Unknown" names, raw roles, duplicate keys

**Observed (evidence):**
- `Elyssa layout log` §4, §6: `Cast` shows `Logo U - Unknown … James Bond` while other titles correctly show `KR Keanu Reeves`; "the 'Unknown' fallbacks need better styling".
- `error_log.txt` lines 4–58: repeated `Encountered two children with the same key` for `-undefined-screenplay`, `-undefined-null`, `-null-null`, `-undefined-developed by`, `-undefined-created by`, `-undefined-producer`.

**Root causes (code):**
1. `api/app/graphql/resolvers.py:155` (`_resolve_cast`), `:180` (`_resolve_crew`), `:300` (`_resolve_collaborators`): `primary_name=r[1] or "Unknown"` — the LEFT JOIN on `dim_person` misses (nconst not present in the name snapshot) and the resolver substitutes a fake string. `EntityLink.tsx:25–28` then renders initials `U` from that string.
2. `client/src/components/features/title/CastList.tsx:56–60`: role line is `member.character ?? member.job ?? member.category` rendered verbatim — `director`, `casting_director`, `production_designer` appear raw. Same in `FilmographyList.tsx:55`.
3. `CastList.tsx:47`: `key={`${member.person.id}-${member.character}-${member.job}`}` — for crew rows `character` is `undefined` (crew GraphQL type has no `character`; `api/gold.ts:37–41`), and duplicated credits with equal `(person, character, job)` collide → the exact keys in the error log.

**Recommended fixes:**
- **API:** make `PersonSummary.primary_name` genuinely nullable; stop synthesising `"Unknown"`. Emit `None` and let the client decide; keep `nconst` always present.
  ```python
  # resolvers.py — before
  person=PersonSummary(id=r[0] or "", primary_name=r[1] or "Unknown")
  # after — carry the raw join result; UI renders the fallback (see below)
  person=PersonSummary(id=r[0], primary_name=r[1])
  ```
  `graphql/types.py:30–34` → `primary_name: str | None`. Update `client/src/lib/types.ts:76` accordingly.
- **UI (`CastList.tsx`, `EntityLink.tsx`):**
  - If `primaryName == null` (or empty): render a **silhouette avatar** (generic circle, no initials, no text) and either suppress the row or show muted placeholder — *decision needed from owner, §6 Q1*. Default recommendation: **hide the row from "Cast" when the actor is unknown, keep it in "Crew" with a "Details coming soon" tooltip**, because cast rows without a name are pure noise, whereas crew credit counts matter.
  - Guard `getInitials` (`lib/utils.ts:33–41`) against null/empty input regardless.
- **Role labels:** add a single `ROLE_LABELS` map in `client/src/lib/constants.ts` (per IMDb categories) and a `formatRole()` util; use it in `CastList.tsx:59` and `FilmographyList.tsx:55`. Fallback: `title-case` of the raw string (replace `_` with space).
  ```ts
  export const ROLE_LABELS: Record<string, string> = {
    director: "Director", writer: "Writer", producer: "Producer",
    composer: "Composer", cinematographer: "Cinematographer", editor: "Editor",
    production_designer: "Production Designer", casting_director: "Casting Director",
    costume_designer: "Costume Designer", self: "Self", archive_footage: "Archive Footage",
    // …remaining IMDb categories as encountered
  };
  ```
- **Unique keys:** key rows with `ordering` when present (GraphQL already returns it for cast) and fall back to an index for crew: `key={`${member.person.id}-${member.ordering ?? i}`}` — kills the duplicate-key warnings without touching the backend. Cleaner: add `ordering` to the `CrewMember` type + `TITLE_DETAIL_QUERY.crew` (1-line change each in `types.py:46–50` and `gold.ts:37–41`).
- **Backend hardening (optional, cheap):** prune orphan principals at query time
  ```sql
  -- use INNER JOIN instead of LEFT JOIN when name is mandatory for display:
  --   LEFT JOIN → INNER JOIN in _resolve_cast/_resolve_crew
  ```
  This silently drops credits whose person cannot be resolved — combine with the UI decision in §6 Q1.

**QA:** vitest for `formatRole` + `getInitials(null)`; playwright: title page with no console warnings (grep console error types), `data-person-id` rows all unique; GraphQL test asserting `primary_name: null` when join misses.

### 2.2 Episodes — "No episode" on movies + null-title crash

**Observed (evidence):**
- User report: "`No episode` frequently appears for titles that are not series."
- `error_log.txt:60–76`: `TypeError: Cannot read properties of null (reading 'id')` at `EpisodeTable.tsx:46:40`, bubbling to the route `ErrorBoundary` → **"Something went wrong loading this page"** (see §2.7).

**Root causes (code):**
1. `TitleDetail.tsx:59` renders `<EpisodeTable episodes={episodes} />` for every title type; `EpisodeTable.tsx:23` returns `<EmptyState title="No episodes" />` when the array is empty. The API never asserts series-ness — `_resolve_episodes` (`resolvers.py:206–226`) just returns `[]` because `fact_episode` has no rows for non-series keys.
2. `_resolve_episodes` does `LEFT JOIN dim_title` and emits `title=None` on join miss (`resolvers.py:224`); the GraphQL type declares `title: TitleSummary | None` (`types.py:66–69`), **but the client type lies** (`types.ts:102–106`: `title: TitleSummary` non-null), and `EpisodeTable.tsx:46` dereferences `ep.title.id`.

**Recommended fixes:**
- `TitleDetail.tsx`: render the section **only when `episodes.length > 0`** (and/or when `title.titleType` is `tvSeries | tvMiniSeries | tvMovie | tvSpecial`). Expose `titleType` in the query (already present in `TITLE_DETAIL_QUERY`) and gate on it; drop the `EmptyState` entirely for empty episodes so movies never show the section.
- `EpisodeTable.tsx:43–54`: defensively handle `ep.title == null` — render a non-clickable row `Episode N · S<season> E<ep>` (no link) instead of crashing; **and** fix the client type to `title: TitleSummary | null` (`types.ts:105`) so future regressions are type errors.
- Backend (optional, cheap): guard `_resolve_episodes` with the title's `title_type` from `dim_title` and return `[]` unless episodic; this also saves a wasted query for the 95 % of titles that are movies.

**QA:** playwright on a movie (e.g. `tt1375666`): no "Episodes" heading, no console error; on a series: episodes render; unit test for `EpisodeTable` with a `null` title prop.

### 2.3 Rating "history" widget

**Observed (evidence):** `Elyssa layout log` §4/§6 — "a large opaque rectangle", "needs X/Y axes or numerical labels"; user report: "excessively long vertical green bar with a single numeric rating".

**Root cause (code):** `RatingTimelineChart.tsx:16–31` — one column per snapshot, bar height `numVotes/maxVotes * 100px`; with **one daily snapshot** (`fact_title_rating` is grain `(tconst, snapshot_date)`, one row per pipeline run) the bar is a full-height 100 px block; axis/date labels are absent and the rating is hidden behind `group-hover`.

**Recommended fix (redesign):**
- Treat votes bars as **secondary**; lead with the rating. Compact horizontal design:
  - Header row: `Rating history` + last rating `8.4/10 · 412k votes` + Δ vs previous snapshot (`▲ 0.1`).
  - Body: horizontal sparkline of `averageRating` per snapshot (SVG polyline, ~16 px tall, no library needed), with a subtle per-point dot and `snapshotDate` labels (month-year ticks when > 6 points).
  - Secondary: right-aligned mini bar of `numVotes` (tooltip on hover).
  - **Hide the whole section when `snapshots.length <= 1`** and show a single stat card instead (the data will become a real history as daily pipeline runs accumulate). Empty state text: keep `No rating data` only when the title genuinely has none.
- No new dependency: hand-rolled SVG/Tailwind, matching `RatingBadge` tokens (`--color-accent-green-*`).

**QA:** vitest for the sparkline path generation; playwright: movie with 1 snapshot shows stat card, no green slab.

### 2.4 Account page — layout, display name, dark mode, delete account

**Observed (evidence):** `Elyssa layout log` §5/§6 ("Dark mode — Coming soon", "user dropdown … standard and functional"); user report: imbalanced layout, email shown instead of editable name, redundant dark-mode toggle, disabled delete button.

**Root causes (code):**
1. Display-name save is a **no-op**: `Account.tsx:19` passes `onSubmit={() => {}}`; `ProfileForm.tsx:38–40` has the input + button but no caller. No `PATCH/PATCH /auth/me` endpoint exists anywhere in the API (`auth/router.py` — verify by grep).
2. Dark-mode toggle in `Settings.tsx:5–25` is a **disconnected local `useState(false)`**, `disabled`, labelled "Coming soon" — while the **Header toggle is fully wired** to `next-themes` (`Header.tsx:36,100–104`, `App.tsx:23`). So the account page control is dead weight.
3. Delete account button `disabled` (`Settings.tsx:32`) — no endpoint, no cascade.

**Recommended fixes (🟡):**
- **API (new, contract-added):**
  - `PATCH /auth/me` `{display_name}` → updates `users.display_name`, returns updated user. Input validation: length 1–64, trimmed; rate-limited like other auth routes.
  - `DELETE /auth/account` → cascade: delete `watchlist` rows, revoke refresh family, delete user row; returns 204. Require a confirmation token/body (`{confirm: "DELETE"}`) to prevent CSRF-style accidents; auth via Bearer + same-origin cookie check.
- **Frontend:**
  - `Account.tsx`: pass a real `handleSave` (call `PATCH /auth/me`, update `user` via `useAuth`, toast success — the app already uses `sonner`); add `isLoading`.
  - Layout: `Account.tsx:12–27` uses a single `max-w-4xl` column with two stacked sections of uneven height; rebalance with a 2-col `lg:grid-cols-2` (Profile | Preferences) + full-width destructive zone, consistent spacing tokens.
  - `Settings.tsx`: replace the disabled toggle with `useTheme()` from `next-themes` (reads the *same* provider as the header, `Settings.tsx:6` state removed). Rationale: header toggle is global; the Preferences entry merely mirrors it — keep it **in sync**, do not add a third theme source. Remove "Coming soon" text.
  - Wire delete to `DELETE /auth/account` behind a `Dialog` (component exists in `components/ui/dialog.tsx`) with typed confirmation and a destructive button; on success → logout + redirect `/`.

**QA:** pytest for PATCH/DELETE (auth + cascade + validation); playwright account spec: rename persists across reload; toggle state mirrors header; delete removes account and watchlist 401s afterwards.

### 2.5 Watchlist & notes persistence

**Observed (evidence):** `Elyssa layout log` §5 (watchlist works, empty state is good); user report: "`Save list` / Markdown content is not saveable".

**Root causes (code):**
1. `TitleHero.tsx:73` renders `<WatchlistButton />` with **no `isSaved`/`onToggle` props** → `WatchlistButton.tsx:16–29` defaults to `isSaved=false` and an `undefined` click handler → the bookmark is inert from the title page (watchlist add only exists server-side: `POST /auth/watchlist`, `auth/router.py:210–218`).
2. **No notes/markdown anywhere**: `watchlist` SQLite table has only `title_data` JSON (`auth/models.py:31–41`); `WatchlistItem.notes` is typed (`types.ts:140`) but the only component that renders it (`components/features/watchlist/CollectionList.tsx`) is **imported by no page** (dead component).

**Recommended fixes:**
- `TitleHero.tsx`/`WatchlistButton.tsx`: wire with the existing `useWatchlist` hook (`hooks/useWatchlist.ts:24–56`, TanStack Query, already has `useAddToWatchlist`/`useRemoveFromWatchlist`); optimistic toggle with rollback; show count of saves (IMDb ref: "Add to Watchlist — includes count").
- **Notes endpoint (new):** add `notes TEXT` column to `watchlist` (SQLite migration — schema lives in `auth/models.py:22–53`); `PATCH /auth/watchlist/{entry_id}` with `{notes}` (markdown allowed, sanitised on render); `GET` returns it in the existing payload.
- **"Save list" scope:** the user-facing concept "save list" = per-entry notes + a **Collections** phase (group watchlist entries into named lists). Recommend: ship per-entry notes now (small), Collections later using the same API shape; **delete** the dead `CollectionList.tsx` or integrate it into `pages/Watchlist.tsx` (`WatchlistGrid.tsx:24–36` lists items today).
- Contract update: `web-application/contracts/api-to-frontend.md` — endpoints are under `/auth/watchlist` **not** `/api/v1/watchlist` as documented; fix the contract or add v1 aliases (prefer **fixing the contract**; the doc is frozen but manifestly wrong — flagged in exploration).

**QA:** playwright: add/remove/notes round-trip via API; optimistic UI test in vitest.

### 2.6 Auth/session — spurious "Session expired" + refresh races

**Observed (evidence):** `error_log.txt:2–3` — two `POST /auth/refresh → 401` during anonymous browsing; user report: "Session expired toast appears randomly … even when a valid token exists".

**Root causes (code):**
1. **Toast fires for anonymous visitors:** `useAuth.tsx:63–77` runs `/auth/refresh` on **every app mount** (login or not); the single `catch` block at `:73–77` clears state **and toasts** `"Session expired. Please log in again."` for *any* failure — including the perfectly normal "no session cookie" 401.
2. **Concurrent-refresh race (valid-session failure):** rotation is revoke-then-issue (`auth/router.py:148–149`); two parallel `/auth/refresh` calls (two tabs, or refresh racing the first page load) make the second hit `row["revoked"]==1` → **the whole family is revoked** (`auth/router.py:133–137`) → every later refresh 401s even with a valid cookie.
3. `authFetch` (`useAuth.tsx:27–44`) and all API helpers throw on 401; there is **no refresh-then-retry on 401 anywhere** despite `auth.docs.ts:44` claiming it.

**Recommended fixes:**
- **Suppress the anonymous toast:** track "had a session before this request" — only toast when `getAccessToken()` was non-null at mount and `/me` subsequently failed, or on refresh 401 after a *successful earlier* session. Silent fallback otherwise (already correctly logged out).
- **Single-flight refresh:** module-level `let refreshPromise` — concurrent callers await the same in-flight POST; on success re-broadcast the token. This eliminates the double-refresh race client-side.
- **Server-side grace (defense in depth):** treat a reused *unexpired* token as race rather than theft when the replacement was issued < 5 s ago (configurable `refresh_reuse_grace_seconds`); revoke family only for genuinely stale reuse. Document in `api-to-frontend.md` (WA-07 already touches this contract).
- **401→refresh-then-retry:** implement once in `authFetch`/urql `mapExchange` (`lib/urql.ts:30–39`): on 401 (excluding `/auth/refresh` itself) → single-flight refresh → retry original request once. Remove the current silent token-clear on `UNAUTHENTICATED`.

**QA:** playwright: anonymous landing page shows **no** toast (assert `toast` count 0); two-tab test: refresh twice concurrently → second tab still valid; pytest: `test_refresh_concurrent_single_family`, `test_refresh_grace_window`.

### 2.7 "Something went wrong loading this page" after prolonged uptime

**Observed (evidence):** user report (prolonged uptime → pages stop loading); `error_log.txt:72–76` confirms the render-crash path (`ErrorBoundary` recreate).

**Root causes (code):**
1. **Confirmed:** any render throw in a lazy route → `router.tsx:24–32` `ErrorBoundary` → `ErrorFallback` message (EpisodeTable null crash is the logged instance).
2. **Suspected memory/threading degradation (matches "prolonged uptime"):**
   - DuckDB **connection–thread affinity**: `_get_con` (`resolvers.py:72–96`) is a process-wide `@lru_cache` singleton, but the lifespan prewarm creates it **inside a daemon thread** (`main.py:53–77` → `_prewarm_con` → `_get_con`), while request threads (FastAPI threadpool) later use it → intermittent "Connection used in different thread" type errors, especially after `Cache-Control`-busting restarts or `reload-cache`.
   - `MemoryCache._store` (`cache/memory.py:16`) has **no size cap / eviction** — pickled GraphQL/person/title entries grow forever (Redis failures are swallowed, `cache/redis.py:27–45`, silently degrading to the unbounded memory tier). 512 MB API container + unbounded cache = OOM after days.
   - `/api/v1/admin/reload-cache` (`api/router.py:390–399`) calls `_get_con.cache_clear()` **without closing the old connection** — one leaked DuckDB handle per call.
   - Rate limiter `_clients` (`cache/rate_limiter.py:24,44–45`) never prunes inactive IPs (slow leak).

**Recommended fixes (🟡–🔴):**
- **Frontend:** null-guard every `title`/`person` deref in list renderers (§2.2 covers the known one); **log `componentDidCatch`** (`ErrorBoundary.tsx:25–27` currently only calls an optional `onError` prop) to console/telemetry so the next occurrence is visible; keep the friendly fallback.
- **Backend resilience:**
  - Create the DuckDB connection **in the request path on first use** (lazy, `threading.local` wrapper around a per-thread connection, or acquire at app startup in the main thread **before** spawning the prewarm thread). Do **not** share one connection across threads.
  - Cap the memory cache (`functools.lru_cache(maxsize=…)` or small eviction policy); consider disabling the memory tier when Redis is available.
  - `reload-cache`: track and `close()` the previous connection before `cache_clear()`.
  - Prune rate-limiter IP entries older than the window (or key by IP + hour bucket).

**QA:** soak test — 10k mixed queries + 2 × `reload-cache` under `docker stats` memory cap; pytest: `test_duckdb_multiple_threads`; playwright: no console errors after 200 title navigations.

### 2.8 Minor/global items

| # | Issue | Evidence | Fix | Effort |
|---|---|---|---|---|
| 2.8.1 | Branding "Hlyssa" on Search/Browse | `Elyssa layout log` §6 (screenshots) — **code contains only "Elyssa"** (`Header.tsx:48–53`) | Suspect stale build or serif-font swash; verify favicon/site title (`index.html`), add a proper favicon/icon (log flags "lacks a distinct graphical icon or favicon") | 🟢 |
| 2.8.2 | Two filter layouts ("Genre+Type" vs "Genre+Decade+Sort") | `Elyssa layout log` §6; `FacetedFilters.tsx` (Search) vs `BrowseFilters.tsx` (Browse) re-derive identical `genreChips` | Extract one shared `FilterBar`/genre-chip source in `lib/constants.ts`; and respect `titleType`/`minRating` in Browse (`Browse.tsx` ignores URL `?type=` links from `Footer.tsx:7–8`) | 🟡 |
| 2.8.3 | Poster protocol verification | code vs OPDB docs (§3.3) | curl check + PosterService adaptation | 🟡 |
| 2.8.4 | `Cache-Control: public, max-age=30` on *all* GETs incl. `/graphql` (`main.py:146–152`) | code | Per-endpoint tuning; never cache `POST /graphql` bodies server-side past TTL consistency | 🟢 |
| 2.8.5 | `known_for_titles` fuzzy matching | `resolvers.py:253–279`, N+1 ILIKE per name | DE change (known_for IDs, §3.1) then `WHERE tconst = ?` | 🔴 (DE rerun) |

---

## 3. Data Enrichment Strategy (Priority 2 — Information Completeness)

### 3.1 Current-state assessment — what's in Gold vs what's missing

Verified against `data-engineering/gold/models/marts/*.sql`, `gold-to-ds.md`, and on-disk Parquet (`data-science/marts/gold/`).

| Display need | In Gold today? | Where | Missing? |
|---|---|---|---|
| Person full names | ✅ | `dim_person.primary_name` (15.5 M rows) | — (join miss → "Unknown" bug, §2.1) |
| Character names | ✅ | `fact_title_principal.character_name`, `fact_performance.character_name` | — |
| Role categories/jobs | ✅ | both principal facts (`category`, `job`) | only human-readable labels (§2.1) |
| Person headshots | ❌ | — | **yes — external** |
| Poster images | ⚠️ | via `PosterService`/OpenPosterDB | protocol verification (§3.3) |
| Plot/tagline | ❌ | — | **yes — external/optional** |
| Known-for (exact IDs) | ⚠️ | Gold has **names only**; IDs in `silver.name_known_for_title` | small DE change |
| Trivia/goofs | ❌ | not in IMDb datasets at all | external only (stretch) |

**Consequence:** the headline complaint (cast/crew "Unknown", raw roles) is solvable **without any external API or DE re-run** — it is a display/resolver bug on top of correct Gold data. The enrichment layer is only needed for images + prose.

### 3.2 Option A — Extend DE pipeline (self-contained, no external dependency)

**Scope (minimal, high-value):**

1. **`known_for_titles` IDs** — `dim_person.sql`: add `known_for_ids` (STRING_AGG of tconsts from `silver.name_known_for_title`, keep existing `known_for_titles` names for humans).
   ```sql
   -- gold/models/marts/dim_person.sql (additive, contract: extend with new column)
   , STRING_AGG(DISTINCT k.tconst, ',') FILTER (WHERE k.known_for_order IS NOT NULL)
       AS known_for_ids
   FROM silver.name_basics p
   LEFT JOIN silver.name_known_for_title k ON k.nconst = p.nconst
   -- GROUP BY …
   ```
2. **Orphan-credit inventory** (diagnostics for the "Unknown" UX decision): a one-off DuckDB/SQL check over `fact_title_principal ⋈ dim_person` — count principals with no name (informs hide-vs-placeholder choice, §6 Q1).
3. **Optional:** carry `title.akas` display titles (e.g., `aka_title` per region) — low priority; skip unless requested.

**Cost:** DE pipeline re-run is **7+ h** and exports ~6 GB of marts (per `data-engineering/docs/export_guide.md` scale). Only item (1) actually *requires* a re-run; everything else in this blueprint is WA-only. Schedule item (1) as a standalone later phase or piggyback on the next scheduled nightly/weekly run.

### 3.3 Option B — External APIs (layered hybrid)

Researched candidates (February 2026 status):

| Source | Cost/key | Rate limits | People headshots? | Titles prose? | Verdict |
|---|---|---|---|---|---|
| **TMDB** | Free, non-commercial; API key required; attribution (logo + "…uses TMDB…" notice) mandatory | ~40 req/s ceiling (legacy 40/10 s disabled 2019); `429` to respect | ✅ `/find?external_source=imdb_id` supports **people**; profile images | ✅ overview, tagline | **Primary enrichment source** |
| **Wikidata SPARQL (WDQS)** | Free, no key; **CC0 data** | ~5 concurrent, 60 s/query timeout, backoff on 429 | ⚠️ `P18` image (Commons URLs, often memorable but not a headshot service) | ⚠️ sparse prose | **Secondary/offline batch** (TMDB-id bridge P4947/P4983 ↔ IMDb P345) |
| **OMDb** | Free 1,000 req/**day** | hard daily cap | ❌ no photos | ✅ plot ("too fast" quality, stale) | Not worth a key; skip |
| **OpenPosterDB** | Self-hosted (compose profile `posters`); free demo key `t0-free-rpdb` | none (local) | ❌ **no headshot endpoint** (poster/logo/backdrop/episode only) | ❌ | Keep for posters only |
| **IMDb official API** | Commercial/trial | restricted | — | — | **Out of scope** (per project constraint) |

**Recommended hybrid architecture (production-grade, rate-safe):**

```
┌─ Gold Parquet (primary, always-on)
│   names/characters/roles/dates/ratings/episodes     ← free, instant, no network
│
├─ EnrichmentService (new, api/app/services/enrichment.py)
│   ├─ SQLite cache table: enrich_title(tconst, tmdb_id, overview, tagline, backdrop_url,
│   │                                   wikidata_qid, updated_at)
│   │                     enrich_person(nconst, tmdb_id, headshot_url, updated_at)
│   ├─ single-flight per key (no stampede on popular titles)
│   ├─ TTL 30 d in SQLite + Redis hot tier (7 d), negative caching
│   └─ circuit breaker: after N consecutive 429/5xx → fall back to cache-only for 10 min
│
├─ TMDB adapter  (require ELYSSA_TMDB_API_KEY; disabled → enrichment returns nulls)
│   ├─ /find/{imdb_id}?external_source=imdb_id      (both tt… and nm… work)
│   ├─ /person/{id}/images · /movie/{id} (overview, tagline, backdrop_path)
│   └─ image URLs built from https://image.tmdb.org/t/p/w500{path}
│
├─ Wikidata adapter (optional, offline only)
│   └─ batch job maps tt/nm → QID via P345, pulls P18/P4947/P4983;
│       TMDB adapter consumes those IDs when |imdb| lookup misses
│
└─ GraphQL surface additions (nullable, degrade to null):
    TitleDetail { overview, tagline } · PersonSummary { headshotUrl }
```

**On-the-fly vs precompute balance:** the IMDb dataset is 12.4 M titles / 15.5 M people — never touch all of them online. Two corridors:

1. **Hot set (online, cached):** the **Top-5 000** titles and **Top-20 000** people by `num_votes` (queryable in DuckDB today) are pre-filled by a **batch job** (Airflow op or `scripts/enrich_batch.py` run after the DS phase; ~5k+20k TMDB calls over ~1–2 h with 5–10 req/s pacing — well inside free limits, and `find` results cached for 30 d < TMDB's 6-month cache cap).
2. **Cold set (online, on-demand):** any requested title/person not pre-filled triggers a single `find` (Redis single-flight + SQLite persistence). Realistic UI traffic can't approach the ceilings; circuit breaker + negative cache keep it safe.

**Latency/cost estimate:** hot-set precompute ≈ 1–2 h one-off + ~1.2 GB cache growth (SQLite). Online lookups add 80–400 ms on first visit for uncached cold IDs, then 0 ms (cache). Zero per-request cost; TMDB attribution line in footer/About (IMDb data already attributed in `Footer.tsx:57`).

**Fallback behaviour:** headshot null → silhouette avatar (matches §2.1 decision); overview null → hide section (no empty blocks).

### 3.4 (Optional) Extra metadata — trivia

Not in IMDb TSVs, not clean in TMDB. **Stretch goal:** Wikidata `P18`/`P345` batch for top titles to add a "Did you know" accordion (IMDb ref §F). Low expected yield; recommend deferring until the roadmap's polish phase.

---

## 4. UI/UX Overhaul & Polish (Priority 3 — Look & Feel)

Driven by `IMDb Layout - References.md` (detail-page IA) and `Netflix Layout - References.md` (home-page conversion/showcase IA), mapped onto the current dark editorial design system (per `client/docs/README.md` + `index.css` tokens).

### 4.1 Title detail page (IMDb ref §2)

| Current | Target (IMDb ref) | Change |
|---|---|---|
| Poster left + metadata grid right (`TitleHero.tsx`) | Poster left; **title/type/year/runtime header block**; star rating box top-right; genre **pills**; prominent **"Add to Watchlist"** button (IMDb §2A) | Rework `TitleHero` composition; wire `WatchlistButton` (§2.5); add popularity rank from `dim_title.popularity_segment` (already in mart, not exposed) |
| `CastList` vertical rows (§2.1) | **Horizontal card grid with circular headshots + character names**, chevron to full cast (IMDb §2C) | New `CastGrid` (reuse `EntityLink` avatar, `usePreloadOnHover`); crew stays as Directors/Writers lines under the hero (IMDb "Core Credits") |
| Breadcrumbs (already present) | keep — IMDb-style secondary nav | — |
| Rating history slab (§2.3) | compact gauges with labels | per §2.3 |
| `SimilarTitlesRow` exists | "More Like This" carousel (IMDb §2H) | style/order pass |
| EpisodeTable for series (IMDb has dedicated episode lists) | per-season episode lists (already correct shape) | only fix §2.2 |

### 4.2 Person page (IMDb "Celebs" §4)

Headshot hero (via §3 enrichment) → Known For (exact IDs after §3.2 item 1) → filmography with role labels (§2.1) → collaborators. `PersonBio.tsx:24–26` already handles missing headshot with an initial.

### 4.3 Home page (Netflix ref §2–3)

Hero `FeaturedCarousel` (exists) + **"Top 10 this week" ranked list with large number overlays** (Netflix ref §3 trend cards; data = home `trending` already cached 120 s, `resolvers.py:430–482`) + `TrendingRow`/`TopRatedRow`. No Netflix-style email CTA (not a signup product — note in §6 Q4).

### 4.4 Motion & micro-interaction plan

- `gsap` + `@gsap/react` already in `package.json`; config flag `feature_gsap_animations` (`config.py:60`) is **defined but unused** — either consume it (hero fade-ups, carousel snap) or delete the flag.
- Loading: keep `SkeletonGrid`/`Skeleton` states; add route-level suspense already present (`router.tsx:27`).
- Hover: `usePreloadOnHover.ts` exists — extend to title cast images.
- **Accessibility:** focus-visible rings on all new interactive elements; `aria-label`s on icon-only buttons (`WatchlistButton` today has no label — add one); `prefers-reduced-motion` gate for GSAP.
- **Responsive:** hamburger/drawer for the filter sidebar on < lg (log §5 flags this).

### P4 shipped status (2026-08-11)

| §4 item | Delivered |
|---|---|
| 4.1 Title page | `CastList` → cast **card grid** (circular headshots + character, expand "View all N cast members"); crew stays Directors/Writers/Crew lines under the hero; `popularity_segment` now exposed via GraphQL and shown as a popularity pill in `TitleHero` (rank chip: Highly popular/Popular/Niche) |
| 4.2 Person page | already at target composition (headshot hero → Known For → filmography → collaborators) — verified, no gaps |
| 4.3 Home | new `TopTenRow` — "Top 10 this week" ranked strip with large number overlays (first 10 of cached `trending`); no signup CTA (Q5) |
| 4.4 Motion/a11y | `prefers-reduced-motion` gate already active in `TitleHero`; icon-only buttons have `aria-label`s (WatchlistButton, theme toggle, menu, filters); dead backend `feature_gsap_animations` flag **deleted** (frontend `FEATURE_FLAGS.gsapAnimations` remains the live switch); Browse filter sidebar → **Sheet drawer on < lg** |
| 2.8.2 Filter unification | single chip source in `lib/constants.ts` (`GENRE_CHIPS`, `TYPE_CHIPS`, `DECADE_CHIPS`, `SORT_CHIPS`, `MIN_RATING_CHIPS`) consumed by `BrowseFilters` + `FacetedFilters`; Browse now **respects `?type=` footer links** and adds Type/Min-rating filters; `/browse/top-rated` fixed (was treated as a genre → returned zero results; now minRating 8) |

**Q1 delivered in P4 hardening:** unknown actors/actresses hidden entirely; unknown crew rendered as "Details coming soon" **non-link** placeholder (`EntityLink`); verified live on `tt38627828` ("Mala Eleccion": 10/10 unknown cast hidden, 7/7 unknown crew placeholder) and unit-tested (`CastList.test.tsx` 5 cases).

---

## 5. Implementation Roadmap

Phases ordered by dependency (frontend fixes < backend endpoints < enrichment < polish). Storm/estimate: single experienced dev.

| Phase | Scope | Depends on | Effort | Requires DE re-run? | Status |
|---|---|---|---|---|---|
| **P1 — Critical fixes** | §2.1 cast/crew/keys/roles · §2.2 episodes · §2.3 rating widget · §2.6 auth toasts/races · §2.7 null guards + resilience, `ErrorBoundary` logging · 2.8.1 favicon | — | 3–4 days | ❌ | ✅ shipped (`ea85c03`) |
| **P2 — Accounts & watchlist** | §2.4 PATCH `/auth/me`, DELETE account, Settings wiring, Account layout · §2.5 watchlist wiring + notes endpoint + contract fix | P1 | 2–3 days | ❌ | ✅ shipped (`ea85c03`) |
| **P3 — Poster verify + enrichment** | §3.3 PosterService adaptation · EnrichmentService SQLite + TMDB adapter + batch script + GraphQL fields + UI (headshots, overview, tagline) + attribution | P1 (resolver surface) | 4–5 days | ❌ (hot-set batch is an API-side job) | ✅ shipped (`ea85c03`) + live-verified (TMDB heat, OPDB posters); poster timeout/negative-cache hardening ✓ (`0d7…` follow-up) |
| **P4 — UI/UX overhaul** | §4.1 title page, §4.2 person page, §4.3 home, §4.4 motion/a11y, 2.8.2 filter unification | P1 | 3–4 days | ❌ | ✅ shipped (`bd62714`) — see §4 status notes below |
| **P5 — DE deltas** | §3.2 known_for_ids (+ optional akas) → Gold contract bump `gold-to-api.md`/`gold-to-ds.md` → API switch to `tconst = ?` lookups | — | 1 day code + **7 h re-run** + QA | ✅ | ⚠️ API path ✅ code + tests (`test_graphql.py`); DE delta pending next scheduled re-run — see `BLUEPRINT.md` §8.5 |

**Quick wins first day:** 2.1 role labels + keys, 2.2 null guard + episodes gating, 2.3 rating stat card, 2.6 toast suppression, 2.8.1 favicon — all 🟢, no backend work beyond GraphQL nullability.

**Definition of done per phase:** pytest green for touched routers/resolvers; vitest + playwright specs per section; Lighthouse ≥ 80 with zero console errors (WA-27 gate), QA catalog W-36…W-43 and checks 36–54 (Web subset) re-run.

---

## 6. Open Questions for the Project Owner

1. **Missing cast/crew handling** (drives §2.1): hide unknown-person rows entirely, show them with a silhouette + "Details coming soon", or keep them with a neutral placeholder ("Uncredited" is *wrong* — these are unresolved IDs, not uncredited roles)? *Recommendation: hide unknown *actors/actresses* (noise), keep unknown crew with placeholder.* **✅ RESOLVED (owner 2026-08-11) — hide unknown actors/actresses; unknown crew kept with "Details coming soon" placeholder (no dead links). Shipped in P4; unit-tested (`CastList.test.tsx`) + live-verified on `tt38627828` (10/10 unknown cast hidden, 7/7 unknown crew placeholder)**
2. **Enrichment source:** are you willing to sign up for a **free TMDB API key** (adds the attribution logo + footer notice)? *Recommendation: yes — it is the only well-rounded free source for headshots + overviews. If not, fall back to Wikidata-only (headshots sparse, prose minimal).* **✅ RESOLVED — key in hand, enrichment live (P3), TMDB attribution in footer**
3. **Data freshness budget:** the DE pipeline re-run costs 7+ h. Is the `known_for_ids` fix worth a dedicated re-run, or should it piggyback on the next scheduled run (recommended)? Also: accept that poster/headshot caches refresh on 30-day TTL rather than per release? **✅ RESOLVED — piggyback on next scheduled re-run (`BLUEPRINT.md` §8.5); posters live via self-hosted OpenPosterDB, cache just hardened against timeout poisoning**
4. **Scope of "save list":** ship per-entry watchlist **notes** (recommended, small) now, and Collections (multi-list grouping) in a later phase — or defer notes too? Note the dead `CollectionList.tsx` either way. **✅ RESOLVED — notes shipped (P2); dead `CollectionList.tsx` deleted**
5. **Home page conversion elements:** Netflix ref is conversion-driven (email CTA). Elyssa is a browsing tool — confirm **no** signup CTA on home (recommended), keeping it a showcase page. **✅ RESOLVED (owner 2026-08-11) — no signup CTA; home remains a showcase page (verified: no signup/newsletter/email CTA anywhere in `Home.tsx`/home components; email only exists in the auth `RegisterForm`)**

---

## 7. Deliverables

### 7.1 This catalogue (replaces/augments the TODO)
`docs/final-release/WA_REMNANT_CATALOGUE.md` (this file) — the owner reviews §6 answers, then the numbered items become tickets referencing `file:line` evidence above. `WA_IMPLEMENTATION_TODO.md` gains a follow-up column pointing to this catalogue for items WA-13/17 (crew render polish) and new P2/P3 rows.

### 7.2 Concrete patch/PR suggestions (summary)

| Patch | Files | Notes |
|---|---|---|
| Nullable `primary_name` + stop "Unknown" fabrication | `api/app/graphql/resolvers.py:155/180/300`, `types.py:30–34`; `client/src/lib/types.ts:75–79` | Gate on §6 Q1 outcome |
| Role labels + unique keys | `client/src/lib/constants.ts`, `lib/utils.ts`, `CastList.tsx:47,56–60`, `FilmographyList.tsx:55` | 🟢 |
| Episodes gate + null-title guard | `TitleDetail.tsx:59`, `EpisodeTable.tsx:43–54`, `client/src/lib/types.ts:102–106` | 🟢 |
| Rating widget redesign | `RatingTimelineChart.tsx` (rewrite) | 🟡 |
| Profile PATCH + account DELETE + notes PATCH | `api/app/auth/router.py`, `auth/models.py` (+SQLite migration), `useAuth.tsx`, `Account.tsx`, `ProfileForm.tsx`, `Settings.tsx`, `TitleHero.tsx`, `WatchlistButton.tsx` | 🟡 |
| Auth: anonymous-toast suppression, single-flight refresh, 401-retry | `client/src/hooks/useAuth.tsx`, `lib/urql.ts`; optional grace window in `auth/router.py:133–149` | 🟡 |
| Resilience: thread-safe DuckDB conn, bounded memory cache, reload-cache close, limiter prune, `componentDidCatch` logging | `resolvers.py:72–96`, `cache/memory.py`, `api/router.py:390–399`, `cache/rate_limiter.py`, `ErrorBoundary.tsx` | 🔴 |
| PosterService → documented OPDB endpoint | `api/app/services/poster.py:46–87` (path + key placement + direct image URL, drop JSON parsing) | 🟡 + curl verification |
| EnrichmentService (+ TMDB adapter, SQLite cache, batch script, GraphQL `overview/tagline/headshotUrl`) | new `api/app/services/enrichment.py`, `graphql/types.py`, `resolvers.py`, `client/src/lib/types.ts`, `gold.ts`, `PersonBio.tsx`, `TitleHero.tsx` | 🔴 |
| Filter unification + Browse URL params | `FacetedFilters.tsx`, `BrowseFilters.tsx`, `Browse.tsx`, `Footer.tsx` | 🟡 |

### 7.3 Gold mart SQL delta (P5)
Covered in §3.2 (additive `known_for_ids` on `dim_person`) + contract bumps (`gold-to-ds.md`, `gold-to-api.md`) + API switch of `_resolve_known_for` to `tconst = ?` (`resolvers.py:311–366`).

**Status (2026-08-10):** the API switch shipped — `_resolve_known_for` auto-detects `known_for_ids` and prefers exact `tconst` lookups, with the ILIKE fallback intact; both paths are unit-tested (`test_graphql.py::test_known_for_*`, in-memory DuckDB). The only remaining piece is the DE delta (`known_for_ids` column in `int_person_details.sql` → `dim_person`), scheduled to piggyback on the next 7 h pipeline re-run. Full investigation: `BLUEPRINT.md` §8.5.

### 7.4 Configuration changes
- `api/app/config.py` (+`.env.example`, `mlops/docker-compose.yml`): `ELYSSA_TMDB_API_KEY` (optional), `ELYSSA_ENRICHMENT_ENABLED` (default false → true with key), `ELYSSA_REFRESH_REUSE_GRACE_SECONDS` (default 5), `ELYSSA_POSTER_BASE_URL` unchanged (verify OPDB key handling), optional `ELYSSA_POSTER_KIND` per call (`poster` | `backdrop` | `logo`).
- `.dockerignore`/compose: no new services required for the enrichment cache (SQLite volume `api/data/`), unless a Redis-backed hot tier is preferred.

---

## Appendix A — Evidence trace (log → root cause → fix)

| Log line / doc quote | Root cause (`file:line`) | Fix section |
|---|---|---|
| error_log:2–3 `auth/refresh 401` | `useAuth.tsx:63–77` anonymous refresh + unconditional toast | §2.6 |
| error_log:4–58 dup keys `-undefined-*`/`-null-null` | `CastList.tsx:47` keys from undefined character/job; `gold.ts:37–41` crew lacks character | §2.1 |
| error_log:60–76 `Cannot read properties of null (reading 'id')` @ `EpisodeTable.tsx:46` | `resolvers.py:224` nullable title vs `types.ts:105` non-null lie | §2.2, §2.7 |
| Layout log §4/§6 "Unknown" cast, raw fallbacks | `resolvers.py:155/180/300` `or "Unknown"`; `CastList.tsx:59` raw category | §2.1 |
| Layout log §6 "Dark mode — Coming soon" | `Settings.tsx:5–25` disconnected local state | §2.4 |
| Layout log §4 "large opaque rectangle" rating bar | `RatingTimelineChart.tsx:22–28` votes-only bar, no labels | §2.3 |
| Layout log §6 "Hlyssa" branding | no code match — stale build; favicon missing | §2.8.1 |
| User: "No episode" on non-series | `TitleDetail.tsx:59` unconditional + `EpisodeTable.tsx:23` EmptyState | §2.2 |
| User: "Something went wrong…" after uptime | render crashes + DuckDB thread affinity (`main.py:53–77` vs `resolvers.py:72–96`) + unbounded `memory.py:16` cache | §2.7 |
| User: save list/notes not persistable | `TitleHero.tsx:73` prop-less button; no notes column in `auth/models.py:31–41`; dead `CollectionList.tsx` | §2.5 |

---

*End of catalogue — P1–P4 shipped, §6 Q1–Q5 resolved; only P5 (DE `known_for_ids`) remains, piggybacked per `BLUEPRINT.md` §8.5.*