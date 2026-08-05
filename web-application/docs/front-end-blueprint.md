# Elyssa Frontend — Comprehensive Project Blueprint

**Version**: 1.0.0
**Status**: Approved — canonical for all downstream implementation agents
**Previous**: No. 1 — Agent Scaffold (AGENTS.md); No. 2 — UI/UX Conceptual Design, Architecture & Blueprint (this document)
**Completion**: Phases 0–7 Complete (MVP delivered 2026-07-10)

### Phase Completion Summary

| Phase | Name | Status | Notes |
|-------|------|--------|-------|
| 0 | Research & Scaffold | ✅ Complete | Vite + React 19 + TS 5 + Tailwind 4 + shadcn/ui |
| 1 | Design System | ✅ Complete | Theme tokens, Google Fonts, cn() utility |
| 2 | Core Layout | ✅ Complete | RootLayout, Header, Footer, Router, RequireAuth |
| 3 | Foundation Components | ✅ Complete | MediaCard, EntityLink, RatingBadge, GenreTags, FilterBar, SearchInput, WatchlistButton, PageHeader, BreadcrumbNav |
| 4 | Feature Modules | ✅ Complete | 26 components across 8 modules (Home, Search, Browse, Title Detail, Person Detail, Auth, Watchlist, Account) |
| 5 | Integration | ✅ Complete | urql client, TanStack Query hooks, AuthProvider, ErrorBoundary, scroll restore |
| 6 | Optimization | ✅ Complete | React.lazy code-splitting (23 chunks), manual chunks, bundle analyzer, hover preloading |
| 7 | Polish & QA | ✅ Complete | Accessibility 100, Best Practices 100, SEO 100, Lighthouse CLI audit, dark mode, 404 route, Playwright E2E |

### Lighthouse Results (CLI)

| Category | Score | Target |
|---|---|---|
| Performance | 84 | >90 |
| Accessibility | 100 | >95 |
| Best Practices | 100 | >90 |
| SEO | 100 | >90 |

*Performance 84 is expected — homepage is placeholder with no real data fetching. Will improve once Gold API gateway is deployed.*

---

## 1. Product

### Elevator Pitch

Elyssa is a cinematic data platform that transforms IMDb's vast metadata into an intuitive, visually rich discovery experience. It bridges the gap between raw data and meaningful exploration — letting users browse, search, and understand film and television through elegant visual narratives rather than dense tables.

### Core Value Proposition

> The most beautiful way to explore movie data.

### Scope (MVP)

| In scope | Out of scope |
|----------|--------------|
| Search titles and people | User-generated reviews / ratings |
| Browse by genre, decade, type | Social features (comments, following) |
| Title detail pages (metadata, cast, episodes, ratings, similar) | Content moderation or reporting |
| Person detail pages (bio, filmography, timeline, network) | Streaming service integrations or links |
| Watchlist (personal collections) | Paywalls, subscriptions, or monetization |
| Lightweight auth (JWT, email/password) | Admin dashboards or back-office interfaces |
| Responsive web (desktop, tablet, mobile) | Native mobile apps |
| Dark mode | Multi-language or i18n |

### Key Differentiators vs Competitors

| | IMDb | Letterboxd | Netflix | Elyssa |
|---|---|---|---|---|
| Visual design | Dense, text-heavy | Clean, social-focused | Cinema-grade | **Cinematic, editorial** |
| Data depth | Deep but buried | Limited | Minimal | **Deep, explorable** |
| Discovery | Search-driven | Social-driven | Algorithm-driven | **Hybrid — search + browse + visual** |
| Performance | Heavy, ad-laden | Moderate | Excellent | **Fast, minimal** |

---

## 2. Users

### Personas

| Persona | Age | Archetype | Primary Need | Key Metric |
|---------|-----|-----------|-------------|------------|
| Maya | 32 | Cinephile | Deep filmography exploration, serendipitous discovery | Sessions > 10 min |
| Jake | 28 | Casual viewer | Quick "what to watch" decisions | Time to decision < 30s |
| Dr. Chen | 45 | Researcher | Data analysis, trend visualization, export | Tasks completed per session |
| Priya | 38 | Industry professional | Efficiency, talent research, cross-referencing | Time saved vs IMDb |

### User Goals (Ranked)

1. Find a known title or person (search)
2. Discover something new (browse, recommendations)
3. Learn about a title (metadata, cast, crew, ratings)
4. Explore connections (actor → filmography → director → other films)
5. Compare titles (side-by-side metadata)
6. Track personally (watchlist, collections)
7. Analyze data (trends, distributions, exports)

---

## 3. Experience

### Interaction Principles

1. **Direct manipulation** — filter, scroll, hover. Forms are last resort.
2. **Instant feedback** — results appear as you type (< 100ms). Skeleton loaders for heavier queries.
3. **Infinite scroll with context** — lists never end abruptly. Show position. Re-anchor on return.
4. **Forgiving navigation** — back button works predictably. Breadcrumbs always visible. Search always accessible.
5. **Consistent mental model** — card always links to detail; badge always shows metadata; poster always represents a title.
6. **Progressive complexity** — start simple, reveal depth on demand.

### Navigation Model

| Pattern | Where | Why |
|---------|-------|-----|
| Hub-and-spoke | Home → Detail → Detail | Exploration — follow connections |
| Filter-down | Browse → Genre → Decade → Sort | Discovery — narrow from broad |
| Search-first | Global search bar | Reference — find known entities |
| Breadcrumb | All detail pages | Orientation — know where you are |

### Page States (Every Page)

| State | Display |
|-------|---------|
| Loading | Skeleton layout matching final structure |
| Success | Rendered content |
| Empty | Illustration + message + suggested action |
| Error | Error message + retry button + fallback content if available |
| Offline | Banner notification + cached content if available |

---

## 4. Content

### Entity Model

```
Title
├── id (tconst)
├── primary_title, original_title
├── title_type (movie, tvSeries, tvEpisode, etc.)
├── start_year, end_year
├── runtime_minutes
├── genres[]
├── average_rating, num_votes
├── poster_url
│
├── Cast[] (from fact_title_principal where category=actor)
│   └── Person, character, ordering
├── Crew[] (from fact_title_principal where category≠actor)
│   └── Person, category, job
├── Episodes[] (from fact_episode, if series)
│   └── Title, season_number, episode_number
├── SimilarTitles[] (computed similarity)
└── Ratings[] (from fact_title_rating, time series)

Person
├── id (nconst)
├── primary_name
├── birth_year, death_year
├── primary_profession[]
├── known_for_titles[]
│
├── Filmography[] (from fact_title_principal)
│   └── Title, category, character, year
├── Collaborators[] (co-occurrence graph)
└── Career timeline (titles by year)

Browse
├── Trending (recently popular, high traffic)
├── Top Rated (all-time, by genre, by decade)
├── Featured (editorial pick)
└── Filter results (any combination of genre + decade + type + rating)
```

### Content Relationships

```
Title ──cast/crew──▶ Person
Person ──filmography──▶ Title
Title ──episode_of──▶ Title (series parent)
Title ──similar──▶ Title
Person ──collaborated_with──▶ Person
```

---

## 5. Design System

Detailed in `repo_skills/elyssa-frontend/SKILL.md`. Key tokens:

### Colors (CSS Variables)

| Token | Light | Dark |
|-------|-------|------|
| `--color-canvas` | `#FFFFFF` | `#1A1A1A` |
| `--color-surface` | `#F9F9F8` | `#222222` |
| `--color-border` | `#EAEAEA` | `#333333` |
| `--color-text` | `#111111` | `#EAEAEA` |
| `--color-text-muted` | `#787774` | `#8A8A8A` |
| `--color-primary` | `#111111` | `#FFFFFF` |

### Typography

| Token | Value |
|-------|-------|
| `--font-display` | Playfair Display, serif |
| `--font-body` | Geist Sans, sans-serif |
| `--font-mono` | Geist Mono, monospace |
| `--leading-body` | 1.6 |
| `--tracking-display` | `-0.02em` to `-0.04em` |

### Component Rules

- Cards: `border: 1px solid #EAEAEA`, radius `8px`-`12px`
- Primary CTA: `background: #111111`, `color: #FFFFFF`, radius `4px`-`6px`
- Badges: pill-shaped, muted pastel backgrounds, uppercase, `letter-spacing: 0.05em`
- All borders: `1px solid #EAEAEA`
- Spacing: `flex gap-*` not `space-x-*` / `space-y-*`
- Equal dimensions: `size-*` not `w-* h-*`

---

## 6. Architecture

### Tech Stack (Final)

| Layer | Technology | Version | Purpose |
|-------|-----------|---------|---------|
| Framework | React | 19.x | UI components |
| Build | Vite | 6.x | Dev server + bundler |
| Routing | React Router | 7.x | Client-side routing |
| Data (GraphQL) | urql | 4.x | GraphQL client |
| Data (caching) | TanStack Query | 5.x | Server state, cache, mutations |
| Components | shadcn/ui | latest | Accessible primitives |
| Styling | Tailwind CSS | 4.x | Utility CSS |
| Icons | Radix Icons | latest | Consistent icon system |
| Charts | Recharts | 2.x | Rating timelines, scatter plots |
| Dates | date-fns | 4.x | Date formatting |
| Motion | GSAP | 3.x | Scroll-driven narratives |
| Auth | JWT (httpOnly) | — | Authentication |
| Lint | ESLint + Prettier | — | Code quality |

### Application Structure

```
src/
├── api/
│   ├── gold.ts              urql client + GraphQL queries
│   ├── user.ts              TanStack Query hooks for user API
│   └── client.ts            Axios instance for REST calls (auth, watchlist)
│
├── components/
│   ├── ui/                  shadcn/ui primitives (auto-generated)
│   ├── composites/          Domain-agnostic reusable components
│   │   ├── MediaCard.tsx
│   │   ├── EntityLink.tsx
│   │   ├── FilterBar.tsx
│   │   ├── RatingBadge.tsx
│   │   ├── GenreTags.tsx
│   │   ├── SearchInput.tsx
│   │   ├── SkeletonGrid.tsx
│   │   ├── EmptyState.tsx
│   │   ├── ErrorFallback.tsx
│   │   ├── WatchlistButton.tsx
│   │   ├── PageHeader.tsx
│   │   └── BreadcrumbNav.tsx
│   ├── features/            Domain-specific feature components
│   │   ├── home/
│   │   │   ├── FeaturedCarousel.tsx
│   │   │   ├── TrendingRow.tsx
│   │   │   ├── GenreQuickLinks.tsx
│   │   │   └── TopRatedRow.tsx
│   │   ├── search/
│   │   │   ├── SearchAutocomplete.tsx
│   │   │   ├── SearchResultsGrid.tsx
│   │   │   └── FacetedFilters.tsx
│   │   ├── title/
│   │   │   ├── TitleHero.tsx
│   │   │   ├── CastList.tsx
│   │   │   ├── EpisodeTable.tsx
│   │   │   ├── SimilarTitlesRow.tsx
│   │   │   ├── RatingTimelineChart.tsx
│   │   │   └── TitleStatsPanel.tsx
│   │   ├── person/
│   │   │   ├── PersonBio.tsx
│   │   │   ├── KnownForGrid.tsx
│   │   │   ├── FilmographyList.tsx
│   │   │   ├── CareerTimeline.tsx
│   │   │   └── CollaborationNetwork.tsx
│   │   └── browse/
│   │       ├── BrowseFilters.tsx
│   │       └── TitleGrid.tsx
│   └── layout/
│       ├── RootLayout.tsx
│       ├── Header.tsx
│       ├── Footer.tsx
│       └── RequireAuth.tsx
│
├── pages/
│   ├── Home.tsx
│   ├── Search.tsx
│   ├── TitleDetail.tsx
│   ├── PersonDetail.tsx
│   ├── Browse.tsx
│   ├── Watchlist.tsx
│   ├── Account.tsx
│   ├── Login.tsx
│   └── Register.tsx
│
├── hooks/
│   ├── useSearch.ts         Search state + autocomplete
│   ├── useWatchlist.ts      Watchlist CRUD (TanStack Query mutations)
│   ├── useAuth.ts           Login, register, logout, token refresh
│   └── useScrollRestore.ts  Infinite scroll position caching
│
├── lib/
│   ├── utils.ts             cn(), format helpers
│   ├── constants.ts         Config, defaults, query TTLs
│   └── types.ts             All TypeScript interfaces
│
├── router.tsx               Route configuration
├── App.tsx                  QueryClientProvider + RouterProvider
└── main.tsx                 Vite entry point
```

### Data Flow (per page)

```
URL Params (path + query)
    │
    ▼
Page Component
    │
    ├──▶ useQuery (TanStack Query)
    │       │
    │       ▼
    │   urql client (GraphQL)
    │       │
    │       ▼
    │   Gold API Gateway
    │
    └──▶ useMutation (TanStack Query, auth pages)
            │
            ▼
        User REST API (JWT authenticated)
```

### GraphQL Query Design

```graphql
# Title Detail — composite query
query TitleDetail($tconst: ID!) {
  title(tconst: $tconst) {
    id
    primaryTitle
    originalTitle
    titleType
    startYear
    endYear
    runtimeMinutes
    genres
    averageRating
    numVotes
    posterUrl
    cast(limit: 20) {
      person { id primaryName posterUrl }
      character
      ordering
    }
    crew {
      person { id primaryName }
      category
      job
    }
    similar(limit: 12) { id primaryTitle averageRating posterUrl }
    episodes(limit: 100) {
      seasonNumber
      episodeNumber
      title { id primaryTitle }
    }
  }
}
```

### Route Table

| Path | Page | Auth | Data Dependencies |
|------|------|------|-------------------|
| `/` | Home | No | Trending, TopRated, Featured queries |
| `/search?q=&genre=&...` | Search | No | Search query, filter counts |
| `/title/:tconst` | TitleDetail | No | Title detail composite query |
| `/person/:nconst` | PersonDetail | No | Person detail + filmography |
| `/browse` | Browse | No | Genre/decade counts, filtered titles |
| `/browse/genre/:slug` | Browse | No | Filtered titles |
| `/browse/decade/:year` | Browse | No | Filtered titles |
| `/browse/top-rated` | Browse | No | Top-rated titles |
| `/watchlist` | Watchlist | Yes | User watchlist (GET) |
| `/account` | Account | Yes | User profile |
| `/auth/login` | Login | No | — |
| `/auth/register` | Register | No | — |

---

## 7. Reliability

### Graceful Degradation Strategy

| Failure | Degraded Behavior |
|---------|-------------------|
| Gold API timeout | Show skeleton for 3s, then ErrorFallback with "Retry" + cached suggestions below |
| Gold API 500 | ErrorFallback with "Service unavailable, please try later" + link back to home |
| User API unavailable | Watchlist shows "Sign in to save" prompt (not error) |
| Network offline | Banner "You are offline" + last-cached data from TanStack Query |
| Image load failure | Avatar/Poster fallback (gradient placeholder with title initials) |
| GraphQL partial error | Renders successful fields, shows inline error for failed fields |

### Caching Strategy

| Content | TTL | Stale Time | Cache Behavior |
|---------|-----|------------|----------------|
| Title detail | 5 min | 1 min | Stale-while-revalidate |
| Person detail | 10 min | 2 min | Stale-while-revalidate |
| Search results | 2 min | 30s | Cache-first, immediate refetch |
| Browse queries | 5 min | 1 min | Cache-first, background refresh |
| Trending/top-rated | 10 min | 2 min | Fresh on mount |
| Watchlist | 30s | 0 | Fresh on mount (mutation invalidates) |
| Static assets | 1 year | — | CDN cache with content hash |

### Error Boundaries

- One root-level `ErrorBoundary` wrapping `RouterProvider`
- One per feature section (e.g., CastList has its own boundary so a cast API failure doesn't crash the entire title page)
- Watchlist operations catch errors and show inline toast (not full-page error)

---

## 8. Quality

### Performance Budgets

| Metric | Target | Measurement |
|--------|--------|-------------|
| Time to Interactive | < 2s on 3G | Lighthouse |
| First Contentful Paint | < 1.5s | Lighthouse |
| Largest Contentful Paint | < 2.5s | Lighthouse |
| Total Bundle (gzipped) | < 150KB | Bundle analyzer |
| Search API response | < 200ms p95 | API monitoring |
| Detail page API (first paint) | < 500ms | API monitoring |
| Lighthouse Performance score | > 90 | CI gate |
| Lighthouse Accessibility score | > 95 | CI gate |

### Testing Strategy

| Layer | Tool | Scope | Coverage Target |
|-------|------|-------|-----------------|
| Unit (components) | Vitest + Testing Library | Composites, hooks, utils | > 80% |
| Integration (pages) | Vitest + MSW | Page renders, API mocking, loading/error/empty states | > 70% |
| E2E (critical paths) | Playwright | Search → Detail, Browse → Filter, Auth → Watchlist | 5 critical paths |
| Accessibility | axe-core (via Playwright) | Every page | 0 violations |
| Visual regression | Playwright screenshot | Every page | Match baseline |

### Critical Paths to Test (E2E)

1. Home → Click title → Title detail page renders correctly
2. Search → Type query → Autocomplete appears → Submit → Results grid → Click → Detail
3. Browse → Filter by genre + decade → Results update → Clear filters
4. Login → Enter credentials → Redirect to home → Header shows logged-in state
5. Logged in → Title detail → Add to watchlist → Visit watchlist → Title appears

### Accessibility Checks

- Every page: axe-core scan (0 critical/serious violations)
- Every interactive element: keyboard navigable + visible focus ring
- Every form: labels, error messages, aria-invalid
- Every image: meaningful alt text (or `alt=""` for decorative)
- Every motion: respect `prefers-reduced-motion` (GSAP matchMedia for scroll animations, CSS `transition: none` for hover animations)
- Color contrast: 4.5:1 for body text, 3:1 for large text (18px+ bold / 24px+ regular)

---

## 9. Future Roadmap

### Post-MVP (v1.1 — v2.0)

| Feature | Priority | Complexity | Notes |
|---------|----------|------------|-------|
| Dark mode | High | Medium | Add `--color-*` dark tokens, `prefers-color-scheme` detection + toggle |
| Advanced search filters | High | Medium | Cast/crew search, year range slider, rating range, language |
| Comparison mode | Medium | High | Side-by-side title comparison (up to 3 titles) |
| Data export | Medium | Low | CSV/JSON export of search results or watchlist |
| User ratings | Low | Medium | 1-10 scale (stored in user API, not Gold) |
| Social features | Low | High | Follow users, public watchlists |
| PWA | Low | Medium | Offline support, install prompt |
| i18n | Low | High | Multi-language support |

### v2.x+

- Advanced analytics dashboards (trends, distributions, network graphs)
- API rate limiting UI (show remaining quota)
- Embeddable widgets (for external sites)
- Mobile apps (React Native / Expo)

---

## 10. Implementation Schedule

### Phase 0 — Research (Week 1) ✅ Complete

| Task | Output |
|------|--------|
| Verify Gold API GraphQL schema | Documented query/mutation list |
| Define TypeScript types for all entities | `src/lib/types.ts` |
| Finalize auth flow with backend team | Auth API contract documented |
| Set up Vite + React + Tailwind project | Working dev server |
| Configure ESLint + Prettier | Lint passes on `npm run lint` |
| Initialize shadcn/ui with Elyssa preset | `components/ui/` with base components |

### Phase 1 — Design System (Week 1, parallel with Phase 0) ✅ Complete

| Task | Output |
|------|--------|
| Define CSS variables (colors, fonts, spacing) | `src/index.css` with `@theme` block |
| Set up typography (Google Fonts for Playfair Display, Geist) | Fonts load in `<head>` |
| Add base utility classes | Truncate, sr-only, focus-ring |
| Create `cn()` utility | `src/lib/utils.ts` |
| Install and configure all shadcn/ui components needed | `components/ui/` complete |

### Phase 2 — Core Layout (Week 2) ✅ Complete

| Task | Dependencies |
|------|-------------|
| `RootLayout` with Header + Footer | shadcn/ui Layout primitives |
| `Header` with search bar + navigation | shadcn/ui NavigationMenu, Input |
| `Footer` with links + credits | — |
| React Router setup with all routes | Router config |
| `SkeletonGrid`, `ErrorFallback`, `EmptyState` | — |
| `RequireAuth` wrapper for protected routes | Router |

### Phase 3 — Foundation Components (Week 2-3) ✅ Complete

| Component | Dependencies | Reused By |
|-----------|-------------|-----------|
| `MediaCard` | Poster image, Badge, RatingBadge | Home, Search, Browse, Watchlist |
| `EntityLink` | Avatar + name | Everywhere |
| `RatingBadge` | Star icon | MediaCard, TitleHero |
| `GenreTags` | Badge, Genre list | MediaCard, TitleHero |
| `FilterBar` | Chips, Button | Search, Browse |
| `SearchInput` | Input, Autocomplete | Header (persistent) |
| `WatchlistButton` | Button, icon state | TitleDetail, MediaCard |
| `PageHeader` | Breadcrumb + Title | All pages |
| `BreadcrumbNav` | Separator, links | All detail pages |

### Phase 4 — Feature Modules (Week 3-5) ✅ Complete

| Module | Components | Pages | API Queries |
|--------|-----------|-------|-------------|
| **Home** | FeaturedCarousel, TrendingRow, GenreQuickLinks, TopRatedRow | Home.tsx | trending, topRated, featured |
| **Search** | SearchAutocomplete, SearchResultsGrid, FacetedFilters | Search.tsx | search, filterCounts |
| **Browse** | BrowseFilters, TitleGrid | Browse.tsx | browse (filtered), genreDecadeCounts |
| **Title Detail** | TitleHero, CastList, EpisodeTable, SimilarTitlesRow, RatingTimelineChart, TitleStatsPanel | TitleDetail.tsx | title(id), similar(id), episodes(id), ratings(id) |
| **Person Detail** | PersonBio, KnownForGrid, FilmographyList, CareerTimeline, CollaborationNetwork | PersonDetail.tsx | person(id), filmography(id), collaborations(id) |
| **Auth** | LoginForm, RegisterForm | Login.tsx, Register.tsx | auth via REST (TanStack Query mutation) |
| **Watchlist** | WatchlistGrid, CollectionList | Watchlist.tsx | watchlist via REST (TanStack Query) |
| **Account** | Profile form, Settings | Account.tsx | user profile |

### Phase 5 — Integration (Week 5-6) ✅ Complete

| Task | Details |
|------|---------|
| GraphQL client setup (`urql`) | Client config, exchanges (dedup, cache), auth context |
| TanStack Query setup | QueryClient defaults, stale times, retry policy |
| urql + TanStack Query integration | urql fetcher wrapped in TanStack Query hooks |
| Auth flow | Login → JWT cookie → AuthProvider → protected routes |
| Error boundary integration | Per-section boundaries, root boundary |
| Scroll position restoration | `useScrollRestore` for browse/search infinite scroll |
| GraphQL codegen | TypeScript types from schema |

### Phase 6 — Optimization (Week 6) ✅ Complete

| Task | Target |
|------|--------|
| Code-splitting by page (`React.lazy`) | < 150KB initial bundle |
| Image lazy loading (`loading="lazy"`) | All posters below fold |
| Preload hover detection | Detail pages load on hover intent |
| TanStack Query tuning | Stale times, prefetching |
| Bundle analyzer review | Identify largest dependencies |
| Lighthouse audit | Score > 90 all categories |

### Phase 7 — Polish & QA (Week 6-7) ✅ Complete

| Task | Verification |
|------|-------------|
| Accessibility audit (axe-core, keyboard nav) | 0 violations, full keyboard flow |
| Responsive testing (375px, 768px, 1280px, 1920px) | No layout breakage |
| Dark mode prep (CSS variable foundation) | Ready for toggle (tokens defined, not live) |
| Reduced motion verification | All animations degrade |
| E2E critical paths in Playwright | 5 paths, passing |
| Error state review | Every page, every state (loading, empty, error, offline) |
| Load testing (100 concurrent simulated users) | p95 < 500ms API, no crashes |
| Final Lighthouse audit | Performance > 90, Accessibility > 95, Best Practices > 90, SEO > 90 |

### Total Timeline: 7 weeks

---

## Blueprint Authority

This blueprint is the **canonical source of truth** for all frontend implementation agents (SWE agents, as described in Phase 5 of the project proposal).

Any deviation from this blueprint requires:
1. A written rationale explaining why the deviation is necessary
2. An approved revision to this document
3. A note in the commit message referencing the revision

## Document Ownership

- **Author**: Elyssa Frontend Agent (SWE Agent)
- **Maintainer**: Project Lead / Architecture Owner
- **Review cadence**: Every sprint retrospective
