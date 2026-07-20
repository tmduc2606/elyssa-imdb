from __future__ import annotations

import json
import pickle
import threading
import time
from functools import wraps
from typing import Any, Callable

from app.cache.redis import cache_get as redis_get
from app.cache.redis import cache_set as redis_set


class MultiTierCache:
    def __init__(self, default_ttl: int = 120):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    def _redis_key(self, key: str) -> str:
        return f"elyssa:api:{key}"

    def get(self, key: str) -> Any | None:
        redis_val = redis_get(self._redis_key(key))
        if redis_val is not None:
            try:
                return pickle.loads(redis_val.encode("latin1"))
            except Exception:
                pass
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires, value = entry
            if time.time() > expires:
                del self._store[key]
                return None
            return value

    def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        effective_ttl = ttl or self._default_ttl
        try:
            redis_set(self._redis_key(key), pickle.dumps(value).decode("latin1"), ttl=effective_ttl)
        except Exception:
            pass
        with self._lock:
            self._store[key] = (time.time() + effective_ttl, value)

    def clear(self, prefix: str | None = None) -> None:
        with self._lock:
            if prefix is None:
                self._store.clear()
            else:
                self._store = {k: v for k, v in self._store.items() if not k.startswith(prefix)}


_cache: MultiTierCache | None = None


def get_cache() -> MultiTierCache:
    global _cache
    if _cache is None:
        _cache = MultiTierCache()
    return _cache


def cached(ttl: int = 120):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            c = get_cache()
            key = f"{func.__name__}:{json.dumps((args, kwargs), sort_keys=True, default=str)}"
            result = c.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            c.set(key, result, ttl=ttl)
            return result
        return wrapper
    return decorator
