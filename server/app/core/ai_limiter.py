"""In-process rate limiting and abuse controls for expensive AI operations.

Provides user-scoped sliding-window throttling for module generation, section modification,
and blueprint copilot chat endpoints. Prevents runaway scripts and resource exhaustion
on constrained free-tier infrastructure.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Dict, List

from fastapi import HTTPException, status
from app.core.config import settings

logger = logging.getLogger(__name__)

# NOTE: Key cooldown and user AI rate limiting state is process-local in this architecture.
# Each worker process maintains in-memory tracking without requiring extra database connections.


class AIUserRateLimiter:
    def __init__(self, max_requests: int = 30, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._user_timestamps: Dict[str, List[float]] = {}
        self._lock = threading.Lock()

    def check_and_record(self, user_id: str) -> None:
        if not user_id:
            return

        now = time.monotonic()
        cutoff = now - self.window_seconds

        with self._lock:
            timestamps = self._user_timestamps.get(user_id, [])
            # Prune timestamps older than the sliding window
            valid = [t for t in timestamps if t > cutoff]

            # Use configured RPM limit if available
            rpm_limit = getattr(settings, "GEMINI_MAX_USER_RPM", self.max_requests)

            if len(valid) >= rpm_limit:
                earliest = valid[0]
                retry_after = max(1, int(earliest + self.window_seconds - now))
                logger.warning(
                    "User %s exceeded AI operations limit (%d/%ds); throttling.",
                    user_id, rpm_limit, self.window_seconds
                )
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="AI operation rate limit exceeded. Please wait a moment before sending more requests.",
                    headers={"Retry-After": str(retry_after)},
                )

            valid.append(now)
            self._user_timestamps[user_id] = valid

    def reset(self) -> None:
        """Reset state across test fixtures."""
        with self._lock:
            self._user_timestamps.clear()


ai_limiter = AIUserRateLimiter()


def check_ai_rate_limit(user_id: str) -> None:
    """Enforce user-scoped AI operation rate limit."""
    ai_limiter.check_and_record(user_id)


def reset_ai_limiter_state() -> None:
    """Reset the in-memory AI rate limiter state."""
    ai_limiter.reset()
