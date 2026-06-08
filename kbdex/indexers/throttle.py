import asyncio
import time


class RateLimiter:
    """Ensures a minimum interval between requests to a single target."""

    def __init__(self, min_interval_ms: int) -> None:
        self._min_interval = min_interval_ms / 1000.0
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = asyncio.get_event_loop().time()
            wait = self._min_interval - (now - self._last_request)
            if wait > 0:
                await asyncio.sleep(wait)
            self._last_request = asyncio.get_event_loop().time()


class CircuitBreaker:
    """Opens after N consecutive failures; auto-resets after a cooldown period."""

    def __init__(self, threshold: int, cooldown_seconds: int) -> None:
        self._threshold = threshold
        self._cooldown = cooldown_seconds
        self._failures = 0
        self._opened_at: float | None = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.monotonic() - self._opened_at > self._cooldown:
            self._failures = 0
            self._opened_at = None
            return False
        return True

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._threshold:
            self._opened_at = time.monotonic()
