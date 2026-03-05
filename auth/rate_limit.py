"""
In-memory rate limiters — brute-force and abuse defense for LAN deployment.

LoginRateLimiter: Tracks failed login attempts per (IP, email) combo.
APIRateLimiter: Tracks mutation requests per IP across all API endpoints.

No persistence needed — server restarts clear the slate (acceptable for
a small LAN deployment).
"""

import time
from threading import Lock

MAX_ATTEMPTS = 5
WINDOW_SECONDS = 900  # 15 minutes


class LoginRateLimiter:
    def __init__(self):
        self._attempts: dict[tuple[str, str], list[float]] = {}
        self._lock = Lock()

    def _prune(self, key: tuple[str, str], now: float) -> list[float]:
        """Remove timestamps older than the window."""
        cutoff = now - WINDOW_SECONDS
        entries = self._attempts.get(key, [])
        pruned = [t for t in entries if t > cutoff]
        if pruned:
            self._attempts[key] = pruned
        elif key in self._attempts:
            del self._attempts[key]
        return pruned

    def check(self, ip: str, email: str) -> int:
        """Check if login is allowed.

        Returns 0 if allowed, or seconds remaining until unlock.
        """
        key = (ip, email.lower())
        now = time.monotonic()
        with self._lock:
            recent = self._prune(key, now)
            if len(recent) >= MAX_ATTEMPTS:
                oldest = recent[0]
                return int(WINDOW_SECONDS - (now - oldest)) + 1
        return 0

    def record_failure(self, ip: str, email: str) -> None:
        """Record a failed login attempt."""
        key = (ip, email.lower())
        now = time.monotonic()
        with self._lock:
            self._prune(key, now)
            self._attempts.setdefault(key, []).append(now)

    def reset(self, ip: str, email: str) -> None:
        """Clear attempts on successful login."""
        key = (ip, email.lower())
        with self._lock:
            self._attempts.pop(key, None)


# Module-level singleton — shared across Waitress threads
limiter = LoginRateLimiter()


# ---------------------------------------------------------------------------
# General API rate limiter — per-IP throttle on mutation endpoints
# ---------------------------------------------------------------------------

API_MAX_REQUESTS = 60
API_WINDOW_SECONDS = 60  # 60 requests per minute per IP


class APIRateLimiter:
    """Per-IP rate limiter for API mutation endpoints (POST/PUT/DELETE/PATCH)."""

    def __init__(self, max_requests: int = API_MAX_REQUESTS,
                 window: int = API_WINDOW_SECONDS):
        self._max = max_requests
        self._window = window
        self._requests: dict[str, list[float]] = {}
        self._lock = Lock()

    def _prune(self, ip: str, now: float) -> list[float]:
        cutoff = now - self._window
        entries = self._requests.get(ip, [])
        pruned = [t for t in entries if t > cutoff]
        if pruned:
            self._requests[ip] = pruned
        elif ip in self._requests:
            del self._requests[ip]
        return pruned

    def check_and_record(self, ip: str) -> int:
        """Record a request and check the limit.

        Returns 0 if allowed, or seconds remaining until the window resets.
        """
        now = time.monotonic()
        with self._lock:
            recent = self._prune(ip, now)
            if len(recent) >= self._max:
                oldest = recent[0]
                return int(self._window - (now - oldest)) + 1
            self._requests.setdefault(ip, []).append(now)
        return 0


api_limiter = APIRateLimiter()
