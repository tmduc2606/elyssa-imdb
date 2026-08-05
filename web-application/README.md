<div align="center">

# Codename: Elyssa — Web Application

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Production-green.svg)](docs/SMOKE_TEST.md)
[![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green.svg)](api)
[![GraphQL](https://img.shields.io/badge/GraphQL-Strawberry-e10098.svg)](api)
[![React](https://img.shields.io/badge/React-19-61DAFB.svg)](client)
[![TypeScript](https://img.shields.io/badge/TypeScript-5-3178C6.svg)](client)

</div>

## Overview

Full-stack web layer for Elyssa: GraphQL + REST API over the 6 Gold Parquet marts (DuckDB views),
JWT authentication, watchlists, and ML-powered predictions, served to an authenticated React 19 SPA.

**Stack:** FastAPI · Strawberry GraphQL · React 19 · Vite 6 · TypeScript 5 · Tailwind CSS 4

```
Browser (React SPA :5173)
  ├── /graphql ──▶ urql ──▶ FastAPI ──▶ DuckDB (6 Gold Parquet marts)
  ├── /auth ─────▶ FastAPI ──▶ SQLite (users, watchlist)
  ├── /api/v1 ───▶ FastAPI ──▶ ModelInference (GMU + CatBoost)
  └── Static ────▶ Vite dev server
```

## Prerequisites

- Python 3.12+ (`web-application/api/.venv/`), Node.js 20+ with npm
- 6 Gold Parquet marts at `data-science/marts/gold/*.parquet` (DE pipeline output)
- DS inference artifacts at `data-science/marts/processed/` (DS pipeline output; optional — inference degrades gracefully)
- (Optional) Redis on `localhost:6379` — falls back to in-memory cache

## Quick Start

```bash
# Backend
cd web-application/api
.venv\Scripts\activate          # Windows — or: source .venv/bin/activate
uvicorn app.main:app --reload --port 8000
# GraphQL playground http://localhost:8000/graphql · REST docs /docs · health /health

# Frontend
cd web-application/client
npm install
npm run dev                     # → http://localhost:5173 (Vite proxies /graphql, /auth, /api)

# Docker (web stack only)
docker compose up -d            # root docker-compose.yml: api + redis
```

## API Endpoints

**GraphQL (primary):** `homepage`, `title(tconst)`, `titleRatings`, `person(nconst)`, `search(query, first, after)`, `browse(genres, decade, ...)`

**REST (`/api/v1`):** `GET /titles`, `GET /titles/{id}`, `GET /titles/{id}/principals`, `GET /persons/{id}`, `GET /persons/{id}/credits`, `GET /search?q=`, `POST /predict/genre`, `POST /predict/rating`, `GET /models`

**Auth (`/auth`):** `register`, `login` (JWT access + httpOnly refresh cookie), `refresh`, `logout`, `me`, `watchlist` (GET/POST/DELETE)

## Data Storage

| Store | Technology | Contents |
|-------|-----------|----------|
| User data | SQLite (`api/data/elyssa.db`) | users (bcrypt password hash), watchlist |
| Analytics | DuckDB (in-memory views) | 6 Gold Parquet marts loaded at startup |
| Cache | Redis → in-memory fallback | `ELYSSA_REDIS_ENABLED` (default true) |

JWT access tokens expire in 15 min; refresh tokens in httpOnly cookies expire in 7 days.

## ML Models

| Model | Type | Task | Input |
|-------|------|------|-------|
| GMU | PyTorch | Genre classification | 26 tabular + 768 text = 794 features |
| CatBoost | Gradient boosting | Rating regression | Same feature vector |

Artifacts load from `data-science/marts/processed/`; inference degrades gracefully when a model is absent.

## Testing

| Suite | Command | Count |
|-------|---------|-------|
| Backend (pytest) | `cd api && .venv\Scripts\python -m pytest tests/` | 45 tests |
| Frontend (vitest) | `cd client && npm run test` | 27 tests |
| E2E (Playwright) | `cd client && npm run e2e` | 5 critical paths |
| Contract conformance | `cd api && pytest tests/test_contract.py -v` | frontend contract compliance |

## Contracts

Frozen cross-module contracts (version-controlled):
- `contracts/gold-to-api.md` — Gold marts → API schema
- `contracts/api-to-frontend.md` — API → Frontend contract

## Project Structure

```
web-application/
├── api/                  # FastAPI app: api/router.py (REST), auth/, graphql/, models/inference.py, config.py
├── client/               # React 19 SPA: src/api/gold.ts, components/, hooks/, pages/ (10), test/
├── contracts/            # gold-to-api.md, api-to-frontend.md
└── docs/                 # full-stack-documentation-plan.md, front-end-blueprint.md
```