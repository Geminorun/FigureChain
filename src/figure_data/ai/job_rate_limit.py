from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Protocol


class AIJobRateLimiter(Protocol):
    def allow(self, provider: str, model_name: str, *, limit_per_minute: int) -> bool:
        """Return whether a provider/model call is allowed now."""


class RedisCounter(Protocol):
    def incr(self, key: str) -> int:
        """Increment a Redis counter and return its value."""

    def expire(self, key: str, seconds: int) -> object:
        """Set an expiration on a Redis key."""


class InMemoryRateLimiter:
    def __init__(self) -> None:
        self._counts: dict[tuple[str, str, str], int] = defaultdict(int)

    def allow(self, provider: str, model_name: str, *, limit_per_minute: int) -> bool:
        minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
        key = (provider, model_name, minute)
        self._counts[key] += 1
        return self._counts[key] <= limit_per_minute


class RedisRateLimiter:
    def __init__(self, redis_client: RedisCounter) -> None:
        self._redis = redis_client

    def allow(self, provider: str, model_name: str, *, limit_per_minute: int) -> bool:
        minute = datetime.now(UTC).strftime("%Y%m%d%H%M")
        key = f"figurechain:ai:rate:{provider}:{model_name}:{minute}"
        value = self._redis.incr(key)
        if value == 1:
            self._redis.expire(key, 120)
        return value <= limit_per_minute
