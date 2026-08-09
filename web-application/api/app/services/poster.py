from __future__ import annotations

import logging

import httpx

from app.cache.redis import cache_get, cache_set, make_cache_key
from app.config import get_settings

logger = logging.getLogger(__name__)

POSTER_TTL = 60 * 60 * 24 * 7  # 7 days
POSTER_KIND = "poster"
REQUEST_TIMEOUT = 3.0
MAX_RETRIES = 2


class PosterService:
    """Fetch poster image URLs from OpenPosterDB (RPDB-compatible).

    Results are cached in Redis with a 7-day TTL. Any downstream failure
    resolves to ``None`` so callers always degrade gracefully.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.poster_base_url
        self.api_key = settings.poster_api_key
        self.enabled = settings.poster_enabled and bool(self.base_url)

    def _cache_key(self, imdb_id: str) -> str:
        return make_cache_key("poster", imdb_id)

    def get_poster_url(self, imdb_id: str) -> str | None:
        if not self.enabled or not imdb_id:
            return None

        cached = cache_get(self._cache_key(imdb_id))
        if cached is not None:
            return cached or None

        url = self._fetch(imdb_id)
        cache_set(self._cache_key(imdb_id), url or "", ttl=POSTER_TTL)
        return url

    def _fetch(self, imdb_id: str) -> str | None:
        endpoint = f"{self.base_url.rstrip('/')}/v1/{POSTER_KIND}/{imdb_id}"
        headers = {"accept": "application/json"}
        if self.api_key:
            headers["x-api-key"] = self.api_key

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                    resp = client.get(endpoint, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    poster_url = self._extract_url(data)
                    if poster_url:
                        return poster_url
                    logger.debug("Poster response for %s had no URL: %s", imdb_id, data)
                    return None
                if resp.status_code in (404, 410):
                    logger.debug("No poster found for %s (HTTP %s)", imdb_id, resp.status_code)
                    return None
                logger.warning("Poster fetch %s -> HTTP %s", imdb_id, resp.status_code)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("Poster fetch attempt %s for %s failed: %s", attempt + 1, imdb_id, exc)

        logger.warning("All poster fetch attempts failed for %s: %s", imdb_id, last_exc)
        return None

    @staticmethod
    def _extract_url(data) -> str | None:
        if isinstance(data, str) and data.startswith("http"):
            return data
        if isinstance(data, dict):
            for key in ("url", "poster_url", "poster", "link", "source"):
                val = data.get(key)
                if isinstance(val, str) and val.startswith("http"):
                    return val
            nested = data.get("data")
            if isinstance(nested, dict):
                return PosterService._extract_url(nested)
        return None

    def prewarm(self, imdb_ids: list[str], limit: int = 100) -> int:
        """Warm the poster cache for the given ids. Returns count of cache hits/misses fetched."""
        if not self.enabled:
            return 0
        fetched = 0
        for imdb_id in imdb_ids[:limit]:
            self.get_poster_url(imdb_id)
            fetched += 1
        logger.info("prewarm poster: %s/%s", fetched, min(len(imdb_ids), limit))
        return fetched
