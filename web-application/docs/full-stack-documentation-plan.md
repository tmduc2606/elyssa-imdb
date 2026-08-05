# Elyssa Full‑Stack Web Application — Master Specification & Review Checklist

****Document Version:**** 2.0.0  
****Status:**** Canonical for Phase 4 agents (SWE‑Frontend, SWE‑Backend, DE, DS)  
****Derived From:****

-   Codename Elyssa Proposal (VI. D & VII. B)
-   Frontend Blueprint (Elyssa Frontend – Comprehensive Project Blueprint)
-   Gold Mart Schema (DE) & Model Registry (DS)
-   AGENTS.md (root agent skills)

## 1\. Purpose & Scope

This document is the ****single source of truth**** for the ****full‑stack**** Elyssa Web Application. It has two equal halves:

1.  ****Frontend Review Checklist**** – a thorough audit of the already‑built React application against the blueprint, proposal criteria (WEB.1–WEB.16), and cross‑module contracts.
2.  ****Backend Implementation Specification**** – a concrete, actionable blueprint for the API gateway, authentication service, model‑serving layer, and caching infrastructure that the frontend depends on.

Together they ensure that the final product is a production‑grade, cinematic data platform that seamlessly integrates the Gold data layer (DE) and AI/ML models (DS).

Every agent involved in Phase 4 must use this document to plan, implement, or verify their deliverables. Deviations require a written rationale and an approved revision to this document.

## 2\. Reference Resources

Before any work, agents must study the example implementations in the **`**references/**`** folder. These projects illustrate battle‑tested patterns for cinematic data platforms, search experiences, and resilient full‑stack architectures.

****Folder:**** `elyssa-imdb/web-application/references/`  
****Contents (provided by project lead):****

| Resource | Description                                                                                                   |
| -------- | ------------------------------------------------------------------------------------------------------------- |
| tier‑1   | Full‑stack cinematic web applications with high community stars (e.g., movie-discovery, streaming platforms). |
| tier‑2   | Netflix / streaming‑platform clones – focus on hero carousels, infinite scroll, personalised rows.            |
| tier‑3   | IMDb / TMDB‑style applications – entity detail pages, search autocomplete, watchlists.                        |

****Usage:****

-   Study ****component architecture****, ****state management****, ****error handling****.
-   Extract the ****design language**** that best fits Duke’s “cinematic, editorial” aesthetic.
-   Do ****not**** copy code verbatim; adapt patterns to Elyssa’s Gold API and design system.

## 3\. Prerequisites

The following artifacts must be ****frozen**** before the full‑stack review can be completed (cf. Handshake Protocols).  
__Note: Data Science is nearly complete; only re‑run & validation remain. Phase 4 may start in parallel.__

| Artifact                                      | Responsible Team       | Status                         |
| --------------------------------------------- | ---------------------- | ------------------------------ |
| Gold API GraphQL schema (final)               | Data Engineering       | Must be published / reviewable |
| Model Registry input/output signatures        | Data Science           | Must be published              |
| Authentication API contract (REST, JWT)       | Data Engineering / SWE | Must be published              |
| Design system tokens (colors, fonts, spacing) | SWE (Frontend)         | Finalised (Phase 1)            |
| Feature Store SQL definitions (optional)      | Data Engineering       | Optional but recommended       |

## 4\. Technical Stack & Architecture

### 4.1 Technology Choices (July 2026)

| Layer              | Technology                  | Version | Purpose                              |
| ------------------ | --------------------------- | ------- | ------------------------------------ |
| Frontend Framework | React                       | 19.x    | UI components                        |
| Build              | Vite                        | 6‑8.x   | Dev server + bundler                 |
| Routing            | React Router                | 7.x     | Client‑side routing                  |
| GraphQL Client     | urql                        | 5.x     | Data fetching                        |
| Server State       | TanStack Query              | 5.x     | Cache, mutations                     |
| Components         | shadcn/ui                   | latest  | Accessible primitives                |
| Styling            | Tailwind CSS                | 4.x     | Utility CSS                          |
| Icons              | Radix Icons                 | latest  | Consistent icon system               |
| Charts             | Recharts                    | 3.x     | Rating timelines, scatter plots      |
| Dates              | date‑fns                    | 4.x     | Date formatting                      |
| Motion             | GSAP                        | 3.x     | Scroll‑driven narratives             |
| Auth               | JWT (httpOnly cookie)       | –       | Stateless authentication             |
| Lint               | ESLint + Prettier           | –       | Code quality                         |
| Backend API        | FastAPI (Python)            | latest  | GraphQL & REST endpoint              |
| Caching            | Redis                       | 7.x     | Session‑aware caching                |
| Model Serving      | Ray Serve / FastAPI sidecar | –       | Genre, rating, recommender inference |
| Hosting            | Docker, Kubernetes          | –       | Containerized deployment             |
| CI/CD              | GitHub Actions              | –       | Automated testing & deployment       |

### 4.2 High‑Level Architecture

text

Browser  
   │  
   ├── Static Assets (Vite build) ──▶ CDN  
   │  
   ├── GraphQL Queries ──▶ urql ──▶ API Gateway (FastAPI)  
   │                                   │  
   │                    ┌──────────────┼──────────────┐  
   │                    │              │              │  
   │               Gold Query       Model          Auth  
   │               Engine          Inference      Service  
   │               (DuckDB)        (Ray Serve)    (JWT)  
   │                    │              │              │  
   │              Gold Parquet     Model Registry  User DB  
   │              (DE marts)       (DS checkpoints) (SQLite/Postgres)  
   │  
   ├── REST Calls (auth, watchlist) ──▶ API Gateway (FastAPI)  
   │  
   └── (Optional) Feature Store ──▶ Redis cache

### 4.3 Data Flow

text

URL Params → Page Component → TanStack Query (urql) → GraphQL → Gold Query Engine  
                │  
                ├──▶ (optional) Model Inference Service (genre/rating predictions)  
                └──▶ (optional) Redis cache (Feature Store / session)

## 5\. Frontend Review Checklist (Existing Code Audit)

The frontend application has already been built following the blueprint (Phases 0‑7). This checklist validates that the implementation meets all proposal criteria and works correctly with the (upcoming) backend contracts.

### 5.1 Code Quality & Process (WEB.1–WEB.3, WEB.9–WEB.12)

- ****WEB.1**** – Code style: ESLint, Prettier, `.editorconfig` all configured and passing.
- ****WEB.2**** – Automated tests:
   -   Unit tests for composites & hooks (>80% coverage).
   -   Integration tests with MSW (mocking Gold API).
   -   E2E tests (Playwright) covering 5 critical paths.
- ****WEB.3**** – Bug tracking: GitHub Issues with `frontend` label, severity, repro steps.
- ****WEB.9**** – Git branching (trunk‑based); PRs mandatory.
- ****WEB.10**** – Code review: ≥1 peer per PR; security, performance, accessibility checklist used.
- ****WEB.11**** – Agile practices followed (sprints, stand‑ups, backlog).
- ****WEB.12**** – Component ownership documented (`CODEOWNERS`).

### 5.2 Security & Stability (WEB.4, WEB.13, WEB.14)

- ****WEB.4**** – OWASP Top 10: input validation, CSP headers, no secrets in client code.
- ****WEB.13**** – Observability:
   -   P95 latency, error rate, throughput monitored via Grafana/Datadog.
   -   Alerts for SLA violations (p95 > 500ms, error rate > 1%).
- ****WEB.14**** – Graceful degradation:
   -   API timeout → skeleton 3s → ErrorFallback with retry + cached suggestions.
   -   Model unavailable → heuristic recommendations / fallback.
   -   Offline → banner + TanStack Query cache.

### 5.3 API Contracts & Deployment (WEB.5–WEB.8)

- ****WEB.5**** – Frozen contracts: GraphQL schema and REST endpoints are locked; any change goes through formal review.
- ****WEB.6**** – Small‑batch deployments: canary releases, feature flags.
- ****WEB.7**** – Feature flags for all new features (env‑based or service).
- ****WEB.8**** – CI/CD: commit → lint, test, build; merge to main → auto‑deploy to staging.

### 5.4 Mobile & Performance (WEB.15, WEB.16)

- ****WEB.15**** – Responsive on 375/768/1280/1920px; touch targets ≥44px; no horizontal scroll.
- ****WEB.16**** – Load testing: 100 concurrent users → p95 < 500ms. Resilience testing: API failures, latency; fallback UI works.

### 5.5 Design System & Accessibility (Blueprint §5 & 7)

- CSS variables for colors, fonts, spacing defined in `src/index.css`.
- Typography: Playfair Display, Geist Sans, Geist Mono.
- `cn()` utility used for class merging.
- Components follow design rules (cards: 1px solid border, radius 8‑12px; badges: pill, uppercase, etc.).
- Accessibility:
   -   axe‑core scan on every page → 0 violations.
   -   Full keyboard navigation.
   -   `prefers‑reduced‑motion` respected.
   -   Contrast ≥ 4.5:1 for body text.

### 5.6 Feature Modules (Blueprint Phase 4)

-   ****Home**** – FeaturedCarousel, TrendingRow, GenreQuickLinks, TopRatedRow.
-   ****Search**** – SearchAutocomplete (debounced), SearchResultsGrid, FacetedFilters.
-   ****Browse**** – BrowseFilters, TitleGrid.
-   ****Title Detail**** – TitleHero, CastList, EpisodeTable, SimilarTitlesRow, RatingTimelineChart, TitleStatsPanel.
-   ****Person Detail**** – PersonBio, KnownForGrid, FilmographyList, CareerTimeline, CollaborationNetwork.
-   ****Auth**** – LoginForm, RegisterForm, RequireAuth wrapper.
-   ****Watchlist**** – WatchlistGrid, WatchlistButton (reusable).
-   ****Account**** – Profile form, settings.

### 5.7 Performance Budgets (Blueprint §8)

-   TTI < 2s (3G).
-   LCP < 2.5s.
-   Total bundle (gzipped) < 150KB.
-   Code‑splitting via `React.lazy` and manual chunks.
-   Image lazy loading (`loading="lazy"`) for below‑fold posters.
-   Hover pre‑loading for detail pages.

## 6\. Backend Implementation Specification

This section defines the ****server‑side**** components that the frontend depends on. It is to be implemented (or reviewed if already started) by the SWE‑Backend agent, with support from DE & DS.

### 6.1 Gold Query Engine (GraphQL)

The core data API must expose a GraphQL endpoint that directly queries the Gold Parquet files via DuckDB.  
****Key requirements:****

-   ****Framework:**** FastAPI + Strawberry (or Ariadne) for GraphQL.
-   ****Schema:**** Mirror the entity model from the frontend blueprint (Title, Person, Browse, Search).  
    Example types - graphql:
    
    type Title {  
      id: ID!  
      primaryTitle: String!  
      originalTitle: String  
      titleType: String  
      startYear: Int  
      endYear: Int  
      runtimeMinutes: Int  
      genres: \[String!\]!  
      averageRating: Float  
      numVotes: Int  
      posterUrl: String  
      cast(limit: Int = 20): \[CastMember!\]!  
      crew: \[CrewMember!\]!  
      similar(limit: Int = 12): \[Title!\]!  
      episodes(limit: Int = 100): \[Episode!\]!  
    }  
    type CastMember { person: Person!; character: String; ordering: Int }  
    type CrewMember { person: Person!; category: String; job: String }  
    type Episode { seasonNumber: Int; episodeNumber: Int; title: Title! }  
    type Person { id: ID!; primaryName: String!; birthYear: Int; deathYear: Int; primaryProfession: \[String!\]!; knownForTitles: \[Title!\]!; filmography(limit: Int = 50): \[FilmographyEntry!\]!; collaborators(limit: Int = 20): \[Person!\]! }  
    type FilmographyEntry { title: Title!; category: String; character: String; year: Int }
    
-   ****Implementation:**** For each field, a resolver function executes a parameterised DuckDB query against the Gold views (dim\_title, dim\_person, fact\_performance, etc.). Caching should be applied at the query level (Redis) for expensive aggregations (e.g., similar titles, trending).
-   ****Performance:**** All queries must return within 200ms p95 for cached queries, 500ms for uncached.

### 6.2 Authentication & User REST API

A simple JWT‑based auth system with httpOnly cookies (for security).  
****Endpoints:****

| Method | Path               | Description                      |
| ------ | ------------------ | -------------------------------- |
| POST   | /api/auth/register | Create account (email, password) |
| POST   | /api/auth/login    | Returns JWT in httpOnly cookie   |
| POST   | /api/auth/logout   | Clears cookie                    |
| GET    | /api/auth/me       | Returns current user profile     |

****User watchlist:****

| Method | Path                   | Description                     |
| ------ | ---------------------- | ------------------------------- |
| GET    | /api/watchlist         | List titles in user’s watchlist |
| POST   | /api/watchlist         | Add title to watchlist          |
| DELETE | /api/watchlist/:tconst | Remove title from watchlist     |

****Implementation:**** FastAPI + SQLite/PostgreSQL for user data. JWT secret stored in environment variable. All endpoints require authentication (via middleware).

### 6.3 Model Inference Service

The DS team’s best models (genre GMU, rating CatBoost, hybrid recommender) must be callable via REST.  
****Endpoints:****

| Method | Path                | Description                                          |
| ------ | ------------------- | ---------------------------------------------------- |
| POST   | /api/predict/genre  | Accepts title metadata → returns genre probabilities |
| POST   | /api/predict/rating | Accepts title metadata → returns predicted rating    |
| POST   | /api/recommend/     | Accepts user watchlist → returns recommended titles  |

****Input/Output:**** Must match the frozen contracts from the Model Registry.  
****Deployment:**** Models are loaded once at startup (PyTorch → ONNX for GMU, CatBoost binary). The service runs as a separate container (or Ray Serve) behind the API gateway.  
****Fallback:**** If the model service is unavailable, the API returns an empty response and the frontend shows heuristic recommendations.

### 6.4 Caching & Performance

-   ****Redis**** for session‑aware caching of GraphQL queries (TTL 5–10 min for title/person details, 2 min for search).
-   ****Static assets**** (posters, images) served via CDN with long‑lived cache headers.
-   ****Rate limiting:**** API gateway enforces rate limits (100 requests/min per IP).

### 6.5 Deployment & CI/CD

-   ****Dockerfile**** for each service (API, Model, Redis).
-   ****Kubernetes**** deployment with auto‑scaling (HPA) for the API service.
-   ****CI/CD (GitHub Actions):**** Lint → Test → Build Docker images → Push to registry → Deploy to staging → Promote to production.

## 7\. Cross‑Module Collaboration Points

### 7.1 Data Engineering

| Integration                          | Required By        | Status                               |
| ------------------------------------ | ------------------ | ------------------------------------ |
| Gold API GraphQL endpoint (deployed) | Frontend & Backend | Must be online for integration tests |
| Auth service (JWT)                   | Frontend & Backend | Must be ready for integration        |
| Feature Store (optional)             | Recommendation UI  | Can be added post‑MVP                |

****Agent Task:**** DE provides a sandbox endpoint (`http://localhost:8000/graphql`) with real (or sampled) Gold data. Backend queries are verified against this endpoint.

### 7.2 Data Science

| Integration             | Required By          | Status                     |
| ----------------------- | -------------------- | -------------------------- |
| Model endpoints (REST)  | Backend API          | Must expose OpenAPI spec   |
| Pre‑computed embeddings | Similar‑titles query | Available as Parquet files |

****Agent Task:**** DS team packages models in Docker containers and provides input/output examples. Backend wraps these calls and exposes them through the API gateway.

## 8\. Implementation Phases (Full‑Stack)

| Phase                     | Duration | Frontend   | Backend                                                                             |
| ------------------------- | -------- | ---------- | ----------------------------------------------------------------------------------- |
| 0 – Research              | Week 1   | ✅ Complete | GraphQL schema finalised, auth contract finalised, model endpoints defined          |
| 1 – Design System         | Week 1   | ✅ Complete | API codebase scaffold, Docker setup                                                 |
| 2 – Core Layout           | Week 2   | ✅ Complete | Gold Query Engine MVP (GraphQL resolvers), auth endpoints                           |
| 3 – Foundation Components | Week 2‑3 | ✅ Complete | User watchlist REST API, Redis cache                                                |
| 4 – Feature Modules       | Week 3‑5 | ✅ Complete | Full GraphQL queries for each page, model serving integration, load testing         |
| 5 – Integration           | Week 5‑6 | ✅ Complete | End‑to‑end integration tests, error boundaries, scroll restoration                  |
| 6 – Optimization          | Week 6   | ✅ Complete | Query performance tuning, CDN setup, bundle analysis                                |
| 7 – Polish & QA           | Week 6‑7 | ✅ Complete | Accessibility audit, responsive testing, E2E tests, Lighthouse, penetration testing |

## 9\. Agent Instructions

1. ****General:**** Thorough understanding of the Elyssa project in terms of codebase structure, architecturem, and strict-quality criterias, comprising of DE - DS and Web Application (current). 
2.  ****Frontend Agent:**** Use Section 5 to audit the existing codebase. File issues for any unchecked item. Do ****not**** make changes that break the frozen GraphQL contract.
3.  ****Backend Agent:**** Implement the specifications in Section 6. All endpoints must be documented with OpenAPI/GraphQL SDL. Coordinate with DE for the Gold engine and DS for model serving.
4.  ****Cross‑team:**** For any contract change, create an issue tagged `cross‑team` and notify the relevant module lead.
5.  ****Reporting:**** At each sprint review, present the checklist status (frontend) and backend progress against the specification.

This document is owned by the Project Lead. It must be reviewed at every sprint retrospective and updated as the architecture evolves.