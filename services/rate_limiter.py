"""In-memory rate limiter for public analysis endpoints.

Enforces two-tier limits (per-client IP and global per-instance) with sliding/fixed
windows to prevent denial of service and LLM quota depletion while remaining
thread-safe.
"""
from __future__ import annotations

import math
import threading
import time
from typing import NamedTuple


class RateLimitDecision(NamedTuple):
    allowed: bool
    retry_after_seconds: int


class RateLimiter:
    def __init__(
        self,
        window_seconds: int = 60,
        per_client_limit: int = 10,
        global_limit: int = 30,
        max_tracked_clients: int = 1000,
    ):
        self.window_seconds = window_seconds
        self.per_client_limit = per_client_limit
        self.global_limit = global_limit
        self.max_tracked_clients = max_tracked_clients

        self._lock = threading.Lock()
        self._clients: dict[str, list[float]] = {}
        self._global_timestamps: list[float] = []

    def check(self, client_key: str, now: float | None = None) -> RateLimitDecision:
        if now is None:
            now = time.time()

        cutoff = now - self.window_seconds

        with self._lock:
            # 1. Clean up global timestamps
            self._global_timestamps = [t for t in self._global_timestamps if t > cutoff]
            if len(self._global_timestamps) >= self.global_limit:
                oldest = self._global_timestamps[0]
                retry_after = max(1, math.ceil(oldest + self.window_seconds - now))
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

            # 2. Clean up client timestamps
            client_ts = self._clients.get(client_key, [])
            client_ts = [t for t in client_ts if t > cutoff]
            self._clients[client_key] = client_ts

            if len(client_ts) >= self.per_client_limit:
                oldest = client_ts[0]
                retry_after = max(1, math.ceil(oldest + self.window_seconds - now))
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)

            # 3. Capacity management if too many clients are tracked
            if len(self._clients) > self.max_tracked_clients:
                expired_keys = [k for k, ts in self._clients.items() if not ts or ts[-1] <= cutoff]
                for k in expired_keys:
                    self._clients.pop(k, None)

            # 4. Record consumption
            self._clients.setdefault(client_key, []).append(now)
            self._global_timestamps.append(now)
            return RateLimitDecision(allowed=True, retry_after_seconds=0)

    def reset_for_tests(self) -> None:
        with self._lock:
            self._clients.clear()
            self._global_timestamps.clear()


# Default singleton instance for fraud analysis endpoint
fraud_rate_limiter = RateLimiter(
    window_seconds=60,
    per_client_limit=10,
    global_limit=30,
    max_tracked_clients=1000,
)
