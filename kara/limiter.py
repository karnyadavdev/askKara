import time
from collections import deque

_PURGE_INTERVAL = 64


class SlidingWindowLimiter:
    def __init__(self, max_hits: int = 15, window_seconds: float = 300.0):
        self._max_hits = max_hits
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}
        self._since_purge = 0

    def check(self, key: str) -> tuple[bool, float]:
        now = time.monotonic()
        hits = self._hits.setdefault(key, deque())
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()
        if len(hits) >= self._max_hits:
            retry_after = hits[0] + self._window - now
            return False, max(retry_after, 1.0)
        hits.append(now)
        self._maybe_purge(cutoff)
        return True, 0.0

    def _maybe_purge(self, cutoff: float) -> None:
        self._since_purge += 1
        if self._since_purge < _PURGE_INTERVAL:
            return
        self._since_purge = 0
        for key in [k for k, dq in self._hits.items() if not dq or dq[-1] <= cutoff]:
            del self._hits[key]

    def reset(self) -> None:
        self._hits.clear()
        self._since_purge = 0
