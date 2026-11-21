"""In-memory sliding-window limits on login failures and registrations.

Behind the reverse proxies every request comes from the same address, so limits are kept
per username (guessing one account's password) and globally (spraying many accounts),
not per IP. State resets on restart, which is acceptable for a single small server."""

import time
from collections import defaultdict, deque
from threading import Lock


class SlidingWindow:
    def __init__(self, limit: int, window_s: float) -> None:
        self.limit = limit
        self.window_s = window_s
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def _prune(self, key: str, now: float) -> deque[float]:
        events = self._events[key]
        while events and events[0] <= now - self.window_s:
            events.popleft()
        if not events:
            del self._events[key]
            return deque()
        return events

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._prune(key, clock())) >= self.limit

    def hit(self, key: str) -> None:
        with self._lock:
            now = clock()
            self._prune(key, now)
            self._events[key].append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._events.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._events.clear()


def clock() -> float:
    """Monotonic time; a function so tests can move it."""
    return time.monotonic()


# 5 wrong passwords per account per 15 minutes; 100 failures per minute across all accounts.
login_per_user = SlidingWindow(limit=5, window_s=15 * 60)
login_global = SlidingWindow(limit=100, window_s=60)
# New accounts across the whole server per hour.
registrations = SlidingWindow(limit=30, window_s=60 * 60)

GLOBAL = "*"
