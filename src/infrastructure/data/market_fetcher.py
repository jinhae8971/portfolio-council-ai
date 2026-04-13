"""시장 데이터 수집기 — yfinance + PyKRX + Rate Limiter"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from .base import DataFetcher
from ...utils.rate_limiter import RateLimiterRegistry

logger = logging.getLogger(__name__)


class MarketDataFetcher(DataFetcher):
    """주식/ETF 시장 데이터 수집. yfinance + pykrx 사용. Rate Limiter 적용."""

    def __init__(self):
        self._rate_limiter = RateLimiterRegistry.get()

    def fetch(self, tickers: List[str]) -> Dict[str, Any]:
        """종목별 가격, 기술적 지표, 기본 정보 수집."""
        result = {"collected_at": datetime.now().isoformat(), "stocks": {}}

        for ticker in tickers:
            try:
                data = self._fetch_single(ticker)
                result["stocks"][ticker] = data
            except Exception as e:
                logger.warning(f"[MarketFetcher] {ticker} 수집 실패: {e}")
                result["stocks"][ticker] = {"error": str(e)}

        return result

    def _fetch_single(self, ticker: str) -> dict:
        """단일 종목 데이터 수집."""
        if self._is_krx(ticker):
            return self._fetch_krx(ticker)
        else:
            return self._fetch_yfinance(ticker)

    def _fetch_yfinance(self, ticker: str) -> dict:
        """yfinance로 글로벌 주식 데이터 수집."""
        self._rate_limiter.wait("yfinance")
        import yfinance as yf

        stock = yf.Ticker(ticker)
        hist = stock.history(period="3mo")

        if hist.empty:
            return {"error": "데이터 없음"}

        current_price = hist["Close"].iloc[-1]
        prev_price = hist["Close"].iloc[-2] if len(hist) > 1 else current_price

        # 기술적 지표 계산
        close = hist["Close"]
        sma_20 = close.rolling(20).mean().iloc[-1] if len(close) >= 20 else None
        sma_50 = close.rolling(50).mean().iloc[-1] if len(close) >= 50 else None
        rsi = self._calculate_rsi(close)
        volatility = close.pct_change().std() * (252 ** 0.5) * 100  # 연환산

        return {
            "price": round(float(current_price), 2),
            "change_pct": round((current_price / prev_price - 1) * 100, 2),
            "volume": int(hist["Volume"].iloc[-1]),
            "sma_20": round(float(sma_20), 2) if sma_20 else None,
            "sma_50": round(float(sma_50), 2) if sma_50 else None,
            "rsi_14": round(float(rsi), 1) if rsi else None,
            "volatility_annual": round(float(volatility), 1),
            "high_52w": round(float(close.tail(252).max()), 2) if len(close) >= 20 else None,
            "low_52w": round(float(close.tail(252).min()), 2) if len(close) >= 20 else None,
        }

    def _fetch_krx(self, ticker: str) -> dict:
        """pykrx로 한국 주식 데이터 수집."""
        self._rate_limiter.wait("pykrx")
        from pykrx import stock as krx

        code = ticker.replace(".KS", "").replace(".KQ", "")
        today = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d")

        try:
            df = krx.get_market_ohlcv(start, today, code)
            if df.empty:
                return {"error": "KRX 데이터 없음"}

            current = df["종가"].iloc[-1]
            prev = df["종가"].iloc[-2] if len(df) > 1 else current
            close = df["종가"]

            return {
                "price": int(current),
                "change_pct": round((current / prev - 1) * 100, 2),
                "volume": int(df["거래량"].iloc[-1]),
                "sma_20": int(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else None,
                "rsi_14": round(float(self._calculate_rsi(close)), 1) if len(close) >= 14 else None,
            }
        except Exception as e:
            logger.warning(f"[KRX] {code} 수집 실패: {e}")
            return {"error": str(e)}

    @staticmethod
    def _calculate_rsi(prices, period: int = 14) -> float | None:
        """RSI(상대강도지수) 계산."""
        if len(prices) < period + 1:
            return None
        delta = prices.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    @staticmethod
    def _is_krx(ticker: str) -> bool:
        """한국 주식 티커인지 판별."""
        return ticker.endswith((".KS", ".KQ")) or ticker.isdigit()
