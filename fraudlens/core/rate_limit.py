"""A per-client sliding-window rate limit, shared by sign-in and the public attack console."""

import threading
import time
from collections import deque


class SlidingWindowLimiter:
    """At most `limit` attempts per client in any `window_seconds`."""

    def __init__(self, limit, window_seconds=300, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self.attempts: dict[str, deque] = {}
        self.lock = threading.Lock()

    def allow(self, client) -> bool:
        """Record an attempt and return True, or return False if the client is over the limit."""
        with self.lock:
            cutoff = self.clock() - self.window
            for key, attempts in list(self.attempts.items()):
                while attempts and attempts[0] <= cutoff:
                    attempts.popleft()
                if not attempts:
                    del self.attempts[key]
            attempts = self.attempts.setdefault(client, deque())
            if len(attempts) >= self.limit:
                return False
            attempts.append(self.clock())
            return True
