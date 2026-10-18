"""Token-bucket rate limiter for news/LLM providers."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class RateLimiter:
    """Simple async token bucket."""

    rate_per_minute: float
    _tokens: float = field(init=False)
    _updated: float = field(init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.rate_per_minute)
        self._updated = time.monotonic()

    async def acquire(self, tokens: float = 1.0) -> float:
        """Wait until tokens available. Returns wait time in seconds."""
        waited = 0.0
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self._updated
                self._updated = now
                self._tokens = min(
                    self.rate_per_minute,
                    self._tokens + elapsed * (self.rate_per_minute / 60.0),
                )
                if self._tokens >= tokens:
                    self._tokens -= tokens
                    return waited
                need = tokens - self._tokens
                sleep_s = need / (self.rate_per_minute / 60.0)
                await asyncio.sleep(sleep_s)
                waited += sleep_s
