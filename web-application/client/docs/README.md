# Codename: Elyssa — Web Application Client

**Location**: `web-application/client/` (merged into the Elyssa Web Application module)
**Status**: MVP Complete (Phases 0–7)
**Stack**: React 19 · Vite 6 · TypeScript 5 · Tailwind CSS 4 · shadcn/ui (Base UI)
**Generated**: 2026-07-10

---

## Quick Start

```bash
# Install dependencies
npm install

# Start dev server (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Preview production build
npm run build && npx vite preview --port 3000

# Lint
npm run lint

# E2E tests (requires Playwright browsers)
npm run e2e

# Bundle analyzer
ANALYZE=true npm run build
```

---

## Project Structure

```
src/
├── api/                    API layer (urql + TanStack Query)
│   ├── gold.ts             7 GraphQL queries + 7 typed hooks
│   ├── auth.docs.ts        Auth API contract
│   ├── client.ts           Generic fetch wrappers
│   └── user.ts             User/watchlist API hooks
│
├── components/
│   ├── ui/                 22 shadcn/ui primitives (Base UI)
│   ├── composites/         13 domain-agnostic components
│   ├── features/           26 feature components (8 modules)
│   └── layout/             Header, Footer, RootLayout, RequireAuth
│
├── hooks/                  Custom hooks (auth, query, preload, scroll)
├── lib/                    Utils, types, constants, urql client
├── pages/                  10 page components (all lazy-loaded)
├── index.css               Theme tokens, dark mode, motion variants
├── router.tsx              React Router v7 with Suspense
├── App.tsx                 Providers (ErrorBoundary, ThemeProvider, QueryClient)
└── main.tsx                Vite entry point
```

---

## Tech Stack Details

| Layer | Technology | Version |
|---|---|---|
| Framework | React | 19.x |
| Build | Vite | 6.x |
| Routing | React Router | 7.x |
| GraphQL | urql | 4.x |
| Caching | TanStack Query | 5.x |
| Components | shadcn/ui (Base UI) | latest |
| Styling | Tailwind CSS | 4.x |
| Icons | lucide-react | 1.x |
| Motion | GSAP | 3.x (installed, ready) |
| Auth | next-themes + JWT httpOnly | — |
| E2E | Playwright | 1.x |

---

## Design System

### Color Palette

| Token | Light | Dark |
|---|---|---|
| `--color-canvas` | `#ffffff` | `#1a1a1a` |
| `--color-surface` | `#f9f9f8` | `#222222` |
| `--color-text` | `#111111` | `#eaeaea` |
| `--color-text-muted` | `#787774` | `#8a8a8a` |
| `--color-border` | `#eaeaea` | `#333333` |
| `--color-primary` | `#111111` | `#ffffff` |

### Typography

| Role | Font |
|---|---|
| Display | Playfair Display |
| Body | Geist Sans |
| Mono | Geist Mono |

### Dark Mode

Toggle via the Moon/Sun button in the Header. Uses `next-themes` with class-based detection (`.dark` on `<html>`).

---

## Routes

| Path | Page | Auth |
|---|---|---|
| `/` | Home | No |
| `/search?q=` | Search | No |
| `/title/:tconst` | Title Detail | No |
| `/person/:nconst` | Person Detail | No |
| `/browse` | Browse | No |
| `/browse/top-rated` | Browse | No |
| `/watchlist` | Watchlist | Yes |
| `/account` | Account | Yes |
| `/auth/login` | Login | No |
| `/auth/register` | Register | No |
| `*` | 404 Not Found | No |

---

## Quality Gates

| Metric | Target | Result |
|---|---|---|
| Build errors | 0 | 0 |
| Lint errors | 0 | 0 |
| Lighthouse Performance | >90 | 84* |
| Lighthouse Accessibility | >95 | 100 |
| Lighthouse Best Practices | >90 | 100 |
| Lighthouse SEO | >90 | 100 |
| E2E critical paths | 5 | 5 |

*Performance score of 84 is expected for placeholder homepage with no real data.

---

## Gold Layer Data Contracts

The frontend consumes 6 Gold-layer parquet marts via GraphQL:

| Mart | Type | Rows | Purpose |
|---|---|---|---|
| `dim_title` | dimension | 12.6M | Title metadata |
| `dim_person` | dimension | 15.4M | Person metadata |
| `fact_title_principal` | fact | 100.2M | Cast/crew relationships |
| `fact_performance` | fact | 100.2M | Title performance metrics |
| `fact_episode` | fact | 9.7M | Episode relationships |
| `fact_title_rating` | fact | 1.7M | Rating snapshots |

**Note**: The API gateway lives under `web-application/api/` (not yet deployed). All GraphQL queries are designed from the Gold Parquet schemas. Data fetching is wired but returns empty/placeholder data until the backend is live. During development, Vite proxies `/graphql`, `/auth`, and `/api` to the backend.

---

## Known Limitations

1. **No API gateway** — All pages show placeholder data. Real data fetching is ready but blocked on backend deployment.
2. **Load testing** — Requires running API gateway. Documented in `docs/LOAD-TESTING-NOTE.md`.
3. **GSAP animations** — Installed but not yet applied to scroll narratives (pending real content).

---

## Documentation

| File | Contents |
|---|---|
| `docs/README.md` | This file |
| `docs/blueprint.md` | Full project blueprint with completion status |
| `docs/Elyssa - Phase 1 Recap.md` | Data pipeline recap (Bronze → Silver → Gold) |
| `docs/LOAD-TESTING-NOTE.md` | Load testing plan (blocked on API) |
| `docs/Codename_ Elyssa - Proposal.docx` | Original project proposal |
| `AGENTS.md` | Agent alignment rules |
