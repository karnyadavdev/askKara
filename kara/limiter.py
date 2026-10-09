import time
from collections import deque


class SlidingWindowLimiter:
    def __init__(self, max_hits: int = 15, window_seconds: float = 300.0):
        self._max_hits = max_hits
        self._window = window_seconds
        self._hits: dict[str, deque[float]] = {}

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
        return True, 0.0

    def reset(self) -> None:
        self._hits.clear()
