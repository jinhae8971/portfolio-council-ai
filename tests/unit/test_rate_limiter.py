"""Rate Limiter 테스트"""
import time
from src.utils.rate_limiter import RateLimiter, RateLimiterRegistry, PROVIDER_LIMITS


def test_limiter_allows_within_limit():
    limiter = RateLimiter(max_calls=5, period_seconds=1, name="test")
    for _ in range(5):
        wait = limiter.wait()
        assert wait == 0.0


def test_limiter_remaining_decreases():
    limiter = RateLimiter(max_calls=3, period_seconds=10, name="test")
    assert limiter.remaining() == 3
    limiter.wait()
    assert limiter.remaining() == 2
    limiter.wait()
    assert limiter.remaining() == 1


def test_for_provider_known():
    limiter = RateLimiter.for_provider("coingecko")
    assert limiter.max_calls == PROVIDER_LIMITS["coingecko"]["calls"]


def test_for_provider_unknown():
    limiter = RateLimiter.for_provider("unknown_api")
    assert limiter.max_calls == 10  # 기본값


def test_registry_singleton():
    r1 = RateLimiterRegistry.get()
    r2 = RateLimiterRegistry.get()
    assert r1 is r2


def test_registry_returns_same_limiter():
    reg = RateLimiterRegistry()
    l1 = reg.limiter_for("coingecko")
    l2 = reg.limiter_for("coingecko")
    assert l1 is l2
