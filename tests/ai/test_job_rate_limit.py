from figure_data.ai.job_rate_limit import InMemoryRateLimiter


def test_in_memory_rate_limiter_allows_until_limit() -> None:
    limiter = InMemoryRateLimiter()

    assert limiter.allow("fake", "model", limit_per_minute=2)
    assert limiter.allow("fake", "model", limit_per_minute=2)
    assert not limiter.allow("fake", "model", limit_per_minute=2)
