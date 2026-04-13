"""Rate Limiter — API 호출 간격 제어

각 데이터 API의 rate limit를 준수하면서 최대 처리량을 유지한다.
스레드 세이프하며 sliding window 방식으로 동작.

사용 예:
    limiter = RateLimiter.for_provider("coingecko")
    limiter.wait()  # 필요하면 대기 후 반환
    response = requests.get(...)
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# 프로바이더별 rate limit 설정
PROVIDER_LIMITS: Dict[str, dict] = {
    "coingecko":     {"calls": 25, "period": 60, "desc": "CoinGecko Free (30/min, 안전마진 적용)"},
    "alpha_vantage": {"calls": 5,  "period": 65, "desc": "Alpha Vantage Free (5/min)"},
    "fred":          {"calls": 100, "period": 60, "desc": "FRED (120/min, 안전마진 적용)"},
    "yfinance":      {"calls": 5,  "period": 2,  "desc": "yfinance (비공식, 보수적 제한)"},
    "pykrx":         {"calls": 3,  "period": 2,  "desc": "PyKRX (보수적 제한)"},
    "claude":        {"calls": 50, "period": 60, "desc": "Claude API (RPM 제한)"},
}


class RateLimiter:
    """Sliding window rate limiter.

    주어진 시간 창(period) 내에 최대 calls 횟수만 허용.
    초과 시 자동으로 필요한 시간만큼 대기.
    """

    def __init__(self, max_calls: int, period_seconds: float, name: str = ""):
        self.max_calls = max_calls
        self.period = period_seconds
        self.name = name
        self._timestamps: deque = deque()
        self._lock = threading.Lock()

    @classmethod
    def for_provider(cls, provider: str) -> "RateLimiter":
        """프로바이더 이름으로 사전 설정된 limiter 생성."""
        config = PROVIDER_LIMITS.get(provider)
        if not config:
            logger.warning(f"[RateLimiter] 알 수 없는 프로바이더: {provider}, 기본값 사용 (10/min)")
            return cls(max_calls=10, period_seconds=60, name=provider)
        return cls(
            max_calls=config["calls"],
            period_seconds=config["period"],
            name=provider,
        )

    def wait(self) -> float:
        """호출 전에 rate limit 확인. 필요하면 대기 후 반환.

        Returns:
            실제 대기한 시간(초). 0이면 대기 없이 통과.
        """
        with self._lock:
            now = time.monotonic()
            # 만료된 타임스탬프 정리
            while self._timestamps and self._timestamps[0] <= now - self.period:
                self._timestamps.popleft()

            if len(self._timestamps) < self.max_calls:
                self._timestamps.append(now)
                return 0.0

            # 가장 오래된 호출이 만료될 때까지 대기
            wait_time = self._timestamps[0] + self.period - now + 0.05  # 50ms 여유
            if wait_time > 0:
                logger.info(f"[RateLimiter:{self.name}] rate limit 도달, {wait_time:.1f}초 대기")
                time.sleep(wait_time)

            # 다시 정리
            now = time.monotonic()
            while self._timestamps and self._timestamps[0] <= now - self.period:
                self._timestamps.popleft()
            self._timestamps.append(now)
            return wait_time

    def remaining(self) -> int:
        """현재 남은 호출 가능 횟수."""
        with self._lock:
            now = time.monotonic()
            while self._timestamps and self._timestamps[0] <= now - self.period:
                self._timestamps.popleft()
            return max(0, self.max_calls - len(self._timestamps))

    def __repr__(self) -> str:
        return f"RateLimiter({self.name}: {self.max_calls}/{self.period}s, remaining={self.remaining()})"


class RateLimiterRegistry:
    """프로바이더별 RateLimiter를 싱글턴으로 관리."""

    _instance: Optional["RateLimiterRegistry"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._limiters: Dict[str, RateLimiter] = {}

    @classmethod
    def get(cls) -> "RateLimiterRegistry":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def limiter_for(self, provider: str) -> RateLimiter:
        """프로바이더별 limiter 반환 (없으면 자동 생성)."""
        if provider not in self._limiters:
            self._limiters[provider] = RateLimiter.for_provider(provider)
        return self._limiters[provider]

    def wait(self, provider: str) -> float:
        """편의 메서드: 프로바이더 이름으로 바로 wait."""
        return self.limiter_for(provider).wait()

    def status(self) -> Dict[str, int]:
        """전체 프로바이더 잔여 호출 수."""
        return {name: lim.remaining() for name, lim in self._limiters.items()}
