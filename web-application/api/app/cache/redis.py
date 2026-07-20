from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def get_redis():
    settings = get_settings()
    if not settings.redis_enabled:
        return None
    try:
        import redis as redis_module
        client = redis_module.from_url(settings.redis_url, decode_responses=True)
        client.ping()
        logger.info("Connected to Redis at %s", settings.redis_url)
        return client
    except Exception as e:
        logger.warning("Redis unavailable (disabled): %s", e)
        return None


def cache_get(key: str) -> str | None:
    r = get_redis()
    if r is None:
        return None
    try:
        return r.get(key)
    except Exception as e:
        logger.warning("Redis get failed: %s", e)
        return None


def cache_set(key: str, value: str, ttl: int = 300) -> None:
    r = get_redis()
    if r is None:
        return
    try:
        r.setex(key, ttl, value)
    except Exception as e:
        logger.warning("Redis set failed: %s", e)


def make_cache_key(prefix: str, *parts: str) -> str:
    return f"elyssa:{prefix}:{':'.join(parts)}"
