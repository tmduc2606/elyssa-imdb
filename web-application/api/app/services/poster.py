from __future__ import annotations

import logging

import httpx

from app.cache.redis import cache_get, cache_set, make_cache_key
from app.config import get_settings

logger = logging.getLogger(__name__)

POSTER_TTL = 60 * 60 * 24 * 7  # 7 days
POSTER_KIND = "poster"
REQUEST_TIMEOUT = 10.0
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

        url, cacheable = self._fetch(imdb_id)
        if cacheable:
            cache_set(self._cache_key(imdb_id), url or "", ttl=POSTER_TTL)
        return url

    def _fetch(self, imdb_id: str) -> tuple[str | None, bool]:
        # OpenPosterDB documented contract: GET {base}/{api_key}/imdb/poster-default/{id}.jpg
        # The response IS the image (JPEG with rating badges), not JSON.
        endpoint = (
            f"{self.base_url.rstrip('/')}/{self.api_key}/imdb/poster-default/{imdb_id}.jpg"
        )
        headers = {"accept": "image/jpeg"}

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                    resp = client.head(endpoint, headers=headers)
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    if content_type.startswith("image/"):
                        return endpoint, True
                    logger.debug(
                        "Poster endpoint %s returned non-image content-type %s",
                        imdb_id,
                        content_type,
                    )
                    return None, True
                if resp.status_code in (404, 410):
                    logger.debug("No poster found for %s (HTTP %s)", imdb_id, resp.status_code)
                    return None, True
                if resp.status_code == 405:
                    # HEAD unsupported by the server — trust the documented URL shape
                    return endpoint, True
                logger.warning("Poster HEAD %s -> HTTP %s", imdb_id, resp.status_code)
            except httpx.HTTPError as exc:
                last_exc = exc
                logger.warning("Poster fetch attempt %s for %s failed: %s", attempt + 1, imdb_id, exc)

        logger.warning("All poster fetch attempts failed for %s: %s", imdb_id, last_exc)
        return None, False

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
