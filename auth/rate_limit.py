"""
In-memory login rate limiter — brute-force defense for LAN deployment.

Tracks failed login attempts per (IP, email) combo. After MAX_ATTEMPTS
failures within WINDOW_SECONDS, blocks that combo for the remainder of
the window. Resets on successful login. No persistence needed — server
restarts clear the slate (acceptable for a small LAN deployment).
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
