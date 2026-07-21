# API-to-Frontend Contract

## Overview

Defines the interface between the FastAPI backend and the React SPA frontend. The frontend consumes only these endpoints — never queries Gold marts or MLflow directly.

**Producer:** Web Application API
**Consumer:** React SPA (client)

---

## Authentication

| Endpoint | Method | Auth Required | Description |
|----------|--------|---------------|-------------|
| `/auth/register` | POST | No | Create account |
| `/auth/login` | POST | No | Get JWT token |
| `/auth/refresh` | POST | Yes | Refresh JWT |
| `/auth/me` | GET | Yes | Current user info |

JWT tokens expire after 24 hours. Refresh tokens valid for 7 days.

---

## REST Endpoints

### Titles

| Endpoint | Method | Query Params | Description |
|----------|--------|-------------|-------------|
| `/api/v1/titles` | GET | `page`, `per_page`, `sort`, `title_type`, `start_year_min`, `start_year_max` | Paginated title list |
| `/api/v1/titles/{title_id}` | GET | — | Single title detail |
| `/api/v1/search` | GET | `q`, `type` | Full-text search |

### Persons

| Endpoint | Method | Query Params | Description |
|----------|--------|-------------|-------------|
| `/api/v1/persons/{person_id}` | GET | — | Person detail |
| `/api/v1/persons/{person_id}/credits` | GET | — | Filmography |

### Watchlist

| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/api/v1/watchlist` | GET | Yes | User's watchlist |
| `/api/v1/watchlist` | POST | Yes | Add to watchlist |
| `/api/v1/watchlist/{title_id}` | DELETE | Yes | Remove from watchlist |

### Predictions

| Endpoint | Method | Body | Description |
|----------|--------|------|-------------|
| `/api/v1/predict/genre` | POST | `{runtime_minutes, start_year, title_type, is_adult}` | Genre prediction |
| `/api/v1/predict/rating` | POST | `{runtime_minutes, start_year, title_type, is_adult}` | Rating prediction |
| `/api/v1/models` | GET | — | List registered models |

---

## GraphQL Endpoint

`POST /graphql` — Strawberry GraphQL with the following queries:

| Query | Description |
|-------|-------------|
| `homepage` | Trending, top-rated, new releases |
| `titleDetail(id: ID!)` | Full title with rating, principals, episodes |
| `personDetail(id: ID!)` | Person with filmography |
| `searchTitles(q: String!, limit: Int)` | Title search |
| `searchPersons(q: String!, limit: Int)` | Person search |

---

## Response Format

### REST Success
```json
{
  "data": [ ... ],
  "meta": { "latency_ms": 50, "cached": false }
}
```

### REST Error
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Title not found",
    "details": {}
  }
}
```

### GraphQL
Standard Strawberry format with `data` and optional `errors` arrays.

---

## Pagination

Cursor-based for GraphQL, page-based for REST:
- REST: `?page=1&per_page=20` (max 100)
- GraphQL: `cursor: String` field on connection types

---

## Rate Limiting

- 200 requests per minute per IP
- Headers: `X-RateLimit-Limit`, `X-RateLimit-Remaining`
- 429 response with `Retry-After: 60`

---

## Frontend Routes

| Route | Component | Data Source |
|-------|-----------|-------------|
| `/` | Home | `homepage` GraphQL |
| `/browse` | Browse | `GET /api/v1/titles` |
| `/title/:id` | TitleDetail | `titleDetail` GraphQL |
| `/person/:id` | PersonDetail | `personDetail` GraphQL |
| `/search?q=` | Search | `searchTitles` + `searchPersons` |
| `/watchlist` | Watchlist | `GET /api/v1/watchlist` |
| `/login` | Login | `POST /auth/login` |
| `/register` | Register | `POST /auth/register` |
| `/account` | Account | `GET /auth/me` |
