# OpenPosterDB Integration — Policy & Operations

**Owner:** Web Application module
**Status:** Active
**Service:** `openposterdb` (optional, compose profile `posters`)

## What it is

OpenPosterDB is a self-hosted, RPDB-compatible poster image service. It resolves
an IMDb `tconst`/`nconst` to a poster URL (sourced from TMDB). The API gateway
caches every resolved URL in Redis with a **7-day TTL** so repeated page loads
cost zero downstream calls.

## Endpoints consumed

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/v1/poster/{imdb_id}` | Fetch poster URL for a title or person |

The API gateway (`app/services/poster.py`) calls this endpoint with a **3 s
timeout** and **one retry with backoff**. Any failure resolves to `None`, so the
frontend always degrades to its text placeholder.

## Configuration

| Env var | Default | Purpose |
|---------|---------|---------|
| `ELYSSA_POSTER_ENABLED` | `true` | Enable/disable poster fetching |
| `ELYSSA_POSTER_BASE_URL` | `http://localhost:3000` | OpenPosterDB base URL |
| `ELYSSA_POSTER_API_KEY` | `t0-free-rpdb` | RPDB-compatible API key |

## Running

Self-hosted (recommended for offline / rate-limit-free operation):

```bash
docker compose -f mlops/docker-compose.yml --profile posters up -d openposterdb
```

Or via the wrapper:

```bash
make posters-up
```

To point at an external RPDB instance instead, set `ELYSSA_POSTER_BASE_URL`
and disable the local service (`ELYSSA_POSTER_ENABLED=false`).

## Cache behaviour

- **Key:** `elyssa:poster:{imdb_id}`
- **TTL:** 7 days (604 800 s)
- **Backend:** Redis (db 0), 256 MB cap in compose
- **Eviction:** Redis `allkeys-lru` (default); warm entries survive as long as
  they are re-read within the TTL.
- **Pre-warm:** On startup the API gateway asynchronously fetches posters for
  the top-100 rated titles (non-blocking background thread).

## Failure modes

| Mode | Behaviour |
|------|-----------|
| OpenPosterDB down | `PosterService.get_poster_url` returns `None` after retries; frontend shows text placeholder |
| Redis down | In-memory cache still works; poster fetch falls through to HTTP each call |
| Invalid id | 404 → cached as `None` (empty string) for the TTL; no error surfaced |
| Timeout (>3 s) | One retry, then `None` |

## Security

- API key is read from env (`ELYSSA_POSTER_API_KEY`), never hardcoded in images.
- The poster service is internal-only (no host port needed in prod); the
  `3000:3000` mapping is for local dev.
