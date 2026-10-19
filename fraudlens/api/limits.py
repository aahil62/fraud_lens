"""Per-client limits for public-facing routes."""
from collections import deque
import os
import threading
import time

LOOPBACK = {"127.0.0.1", "::1"}


def client_ip(request) -> str:
    """The caller's address, trusting forwarded headers only via the bundled console proxy (a loopback peer).

    FRAUDLENS_CLIENT_IP_HEADER names a header the hosting edge sets itself (the
    container uses cf-connecting-ip: Render sits behind Cloudflare, which overwrites
    it with the visitor's address). Otherwise the right-most X-Forwarded-For entry,
    the one the last proxy appended, is used; earlier entries are client-supplied.
    """
    peer = request.client.host if request.client else "unknown"
    if peer not in LOOPBACK:
        return peer
    header = os.environ.get("FRAUDLENS_CLIENT_IP_HEADER", "").strip()
    trusted = request.headers.get(header, "").strip() if header else ""
    if trusted:
        return trusted.split(",")[0].strip()
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded.strip():
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
