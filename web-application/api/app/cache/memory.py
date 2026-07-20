from __future__ import annotations

import json
import threading
import time
from functools import wraps
from typing import Any, Callable


class MemoryCache:
    def __init__(self, default_ttl: int = 120):
        self._store: dict[str, tuple[float, Any]] = {}
        self._default_ttl = default_ttl
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
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
        with self._lock:
            self._store[key] = (time.time() + (ttl or self._default_ttl), value)

    def clear(self, prefix: str | None = None) -> None:
        with self._lock:
            if prefix is None:
                self._store.clear()
            else:
                self._store = {k: v for k, v in self._store.items() if not k.startswith(prefix)}


_cache: MemoryCache | None = None


def get_cache() -> MemoryCache:
    global _cache
    if _cache is None:
        _cache = MemoryCache()
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
