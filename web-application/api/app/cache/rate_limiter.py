from __future__ import annotations

import threading
import time
from collections import defaultdict
from functools import lru_cache

from app.config import get_settings


@lru_cache
def get_rate_limiter():
    settings = get_settings()
    return SlidingWindowRateLimiter(
        max_requests=settings.rate_limit_per_minute,
        window_seconds=60,
    )


class SlidingWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60, max_clients: int = 10_000):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.max_clients = max_clients
        self._clients: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def _prune(self, now: float) -> None:
        cutoff = now - self.window_seconds
        stale = [cid for cid, ts in self._clients.items() if not ts or ts[-1] < cutoff]
        if len(self._clients) - len(stale) > self.max_clients:
            # Ordered by last activity; drop the least-recently-active overflow
            active = sorted(
                ((cid, ts[-1]) for cid, ts in self._clients.items() if ts and ts[-1] >= cutoff),
                key=lambda kv: kv[1],
            )
            overflow = active[: len(active) - self.max_clients]
            stale = list(set(stale) | {cid for cid, _ in overflow})
        for cid in stale:
            del self._clients[cid]

    def check(self, client_id: str) -> bool:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            if len(self._clients) >= self.max_clients and client_id not in self._clients:
                self._prune(now)
            timestamps = self._clients[client_id]
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            if len(timestamps) >= self.max_requests:
                return False
            timestamps.append(now)
        return True

    def remaining(self, client_id: str) -> int:
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            timestamps = self._clients.get(client_id, [])
            while timestamps and timestamps[0] < cutoff:
                timestamps.pop(0)
            return max(0, self.max_requests - len(timestamps))
