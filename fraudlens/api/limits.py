"""Per-client limits for public-facing routes."""
from collections import deque
import threading
import time

LOOPBACK = {"127.0.0.1", "::1"}


def client_ip(request) -> str:
    """The caller's address. Behind the bundled console proxy (a loopback peer)
    the right-most X-Forwarded-For entry is the one the last proxy appended;
    earlier entries are client-supplied and ignored."""
    peer = request.client.host if request.client else "unknown"
    forwarded = request.headers.get("x-forwarded-for", "")
    if peer in LOOPBACK and forwarded.strip():
        return forwarded.split(",")[-1].strip()
    return peer


class LoginLimiter:
    """Sliding window: at most `limit` login attempts per client every `window_seconds`."""

    def __init__(self, limit=20, window_seconds=300, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window_seconds, clock
        self.attempts: dict[str, deque] = {}
        self.lock = threading.Lock()

    def allow(self, client) -> bool:
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
