"""In-memory rate limiting.

Counters live in process memory, so each serverless instance has its own. This only
slows down casual abuse and accidental loops; it is not a billing guard.
"""

from __future__ import annotations

import time
from collections import deque

MAX_TRACKED_KEYS = 5000


class SlidingWindowLimiter:
    def __init__(self, per_key: int, global_limit: int, window_s: int) -> None:
        self.per_key = per_key
        self.global_limit = global_limit
        self.window_s = window_s
        self._hits: dict[str, deque[float]] = {}
        self._global: deque[float] = deque()

    def _prune(self, q: deque[float], now: float) -> None:
        while q and now - q[0] >= self.window_s:
            q.popleft()

    def check(self, key: str, now: float | None = None) -> int | None:
        """Record a hit. Return None if allowed, else seconds until retry."""
        now = time.monotonic() if now is None else now
        self._prune(self._global, now)
        if len(self._global) >= self.global_limit:
            return max(1, int(self.window_s - (now - self._global[0])))
        q = self._hits.get(key)
        if q is None:
            if len(self._hits) >= MAX_TRACKED_KEYS:
                self._evict(now)
            q = self._hits[key] = deque()
        self._prune(q, now)
        if len(q) >= self.per_key:
            return max(1, int(self.window_s - (now - q[0])))
        q.append(now)
        self._global.append(now)
        return None

    def _evict(self, now: float) -> None:
        for k in list(self._hits):
            self._prune(self._hits[k], now)
            if not self._hits[k]:
                del self._hits[k]
        if len(self._hits) >= MAX_TRACKED_KEYS:
            self._hits.clear()
