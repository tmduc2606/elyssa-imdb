from __future__ import annotations

from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_redis():
    settings = get_settings()
    if not settings.redis_enabled:
        return None
    try:
        import redis as redis_module

        return redis_module.from_url(settings.redis_url, decode_responses=True)
    except ImportError:
        return None


async def cache_get(key: str) -> str | None:
    r = get_redis()
    if r is None:
        return None
    return r.get(key)


async def cache_set(key: str, value: str, ttl: int = 300) -> None:
    r = get_redis()
    if r is None:
        return
    r.setex(key, ttl, value)


def make_cache_key(prefix: str, *parts: str) -> str:
    return f"elyssa:{prefix}:{':'.join(parts)}"
