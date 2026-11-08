from __future__ import annotations

import asyncio
import time
from collections import defaultdict


class TokenBucket:
    """Async token bucket keyed by host."""

    def __init__(self, rate: float = 4.0, burst: int = 8) -> None:
        self.rate = rate
        self.burst = burst
        self._state: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(burst), time.monotonic())
        )
        self._lock = asyncio.Lock()

    async def acquire(self, key: str) -> None:
        while True:
            async with self._lock:
                tokens, last = self._state[key]
                now = time.monotonic()
                tokens = min(self.burst, tokens + (now - last) * self.rate)
                self._state[key] = (tokens, now)
                if tokens >= 1.0:
                    self._state[key] = (tokens - 1.0, now)
                    return
                wait = (1.0 - tokens) / self.rate
            await asyncio.sleep(min(wait, 2.0))