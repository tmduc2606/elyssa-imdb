from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.cache.redis import cache_get, cache_set, make_cache_key
from app.config import get_settings

logger = logging.getLogger(__name__)

POSTER_TTL = 60 * 60 * 24 * 7  # 7 days
REQUEST_TIMEOUT = 2.0
MAX_RETRIES = 1
CIRCUIT_TRIP = 5
CIRCUIT_OPEN_SECONDS = 300


class PosterService:
    """Fetch poster image URLs from OpenPosterDB (RPDB-compatible).

    Results are cached in Redis with a 7-day TTL. A simple circuit breaker
    prevents hammering OPDB when it returns 5xx errors.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.poster_base_url
        self.api_key = settings.poster_api_key
        self.enabled = settings.poster_enabled and bool(self.base_url)
        self._failures = 0
        self._circuit_open_until = 0.0

    def _cache_key(self, imdb_id: str) -> str:
        return make_cache_key("poster", imdb_id)

    def _is_circuit_open(self) -> bool:
        if self._failures >= CIRCUIT_TRIP:
            if time.monotonic() < self._circuit_open_until:
                return True
            self._circuit_open_until = 0
        return False

    def _record_failure(self) -> None:
        self._failures += 1
        if self._failures >= CIRCUIT_TRIP:
            self._circuit_open_until = time.monotonic() + CIRCUIT_OPEN_SECONDS
            logger.warning("Poster circuit OPEN - OPDB unhealthy (%d failures)", self._failures)

    def _record_success(self) -> None:
        self._failures = 0

    def get_poster_url(self, imdb_id: str) -> str | None:
        if not self.enabled or not imdb_id:
            return None

        if self._is_circuit_open():
            return None

        cached = cache_get(self._cache_key(imdb_id))
        if cached is not None:
            self._record_success()
            return cached or None

        url, cacheable = self._fetch(imdb_id)
        if cacheable:
            cache_set(self._cache_key(imdb_id), url or "", ttl=POSTER_TTL)
        return url

    def _fetch(self, imdb_id: str) -> tuple[str | None, bool]:
        endpoint = (
            f"{self.base_url.rstrip('/')}/{self.api_key}/imdb/poster-default/{imdb_id}.jpg"
        )
        headers = {"accept": "image/jpeg"}
        for attempt in range(MAX_RETRIES):
            try:
                with httpx.Client(timeout=REQUEST_TIMEOUT) as client:
                    resp = client.head(endpoint, headers=headers)
                    if resp.status_code == 200 and "image/" in resp.headers.get("content-type", ""):
                        self._record_success()
                        return endpoint, True
                    if resp.status_code == 404:
                        self._record_success()
                        return None, True
                    if resp.status_code >= 500:
                        self._record_failure()
                        logger.warning("Poster HEAD %s -> HTTP %d", imdb_id, resp.status_code)
            except Exception as e:
                self._record_failure()
                logger.debug("Poster HEAD %s failed: %s", imdb_id, e)
        return None, False

    def prewarm(self, imdb_ids: list[str], limit: int = 100) -> int:
        if not self.enabled:
            return 0
        count = 0
        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(self.get_poster_url, id_) for id_ in imdb_ids[:limit]]
            for f in futures:
                if f.result():
                    count += 1
        return count
