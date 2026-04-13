"""매크로 경제 데이터 수집기 — FRED + Fear & Greed Index + Rate Limiter"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Any, Dict

from .base import MacroFetcher
from ...utils.rate_limiter import RateLimiterRegistry

logger = logging.getLogger(__name__)


class FREDMacroFetcher(MacroFetcher):
    """FRED API + CNN Fear & Greed Index로 매크로 데이터 수집."""

    def __init__(self, fred_api_key: str | None = None):
        self.fred_api_key = fred_api_key or os.environ.get("FRED_API_KEY")

    def fetch(self) -> Dict[str, Any]:
        result = {"collected_at": datetime.now().isoformat()}

        # FRED 데이터
        if self.fred_api_key:
            result["rates"] = self._fetch_rates()
            result["economic"] = self._fetch_economic()
        else:
            logger.warning("[Macro] FRED_API_KEY 없음 — 매크로 데이터 건너뜀")
            result["rates"] = {"error": "FRED_API_KEY not set"}
            result["economic"] = {"error": "FRED_API_KEY not set"}

        # Fear & Greed Index
        result["sentiment"] = self._fetch_fear_greed()

        return result

    def _fetch_rates(self) -> dict:
        """금리 데이터 수집."""
        try:
            from fredapi import Fred
            fred = Fred(api_key=self.fred_api_key)
            rate_limiter = RateLimiterRegistry.get()

            indicators = {
                "fed_funds_rate": "FEDFUNDS",
                "us_10y_yield": "DGS10",
                "us_2y_yield": "DGS2",
                "us_30y_yield": "DGS30",
            }

            data = {}
            for name, series_id in indicators.items():
                try:
                    rate_limiter.wait("fred")
                    series = fred.get_series(series_id, limit=5)
                    data[name] = round(float(series.dropna().iloc[-1]), 2)
                except Exception:
                    data[name] = None

            # 장단기 금리차
            if data.get("us_10y_yield") and data.get("us_2y_yield"):
                data["yield_spread_10y_2y"] = round(
                    data["us_10y_yield"] - data["us_2y_yield"], 2
                )

            return data
        except Exception as e:
            logger.error(f"[Macro] FRED 금리 수집 실패: {e}")
            return {"error": str(e)}

    def _fetch_economic(self) -> dict:
        """경제 지표 수집."""
        try:
            from fredapi import Fred
            fred = Fred(api_key=self.fred_api_key)
            rate_limiter = RateLimiterRegistry.get()

            indicators = {
                "cpi_yoy": "CPIAUCSL",
                "unemployment": "UNRATE",
                "gdp_growth": "A191RL1Q225SBEA",
                "vix": "VIXCLS",
            }

            data = {}
            for name, series_id in indicators.items():
                try:
                    rate_limiter.wait("fred")
                    series = fred.get_series(series_id, limit=5)
                    data[name] = round(float(series.dropna().iloc[-1]), 2)
                except Exception:
                    data[name] = None

            return data
        except Exception as e:
            logger.error(f"[Macro] FRED 경제지표 수집 실패: {e}")
            return {"error": str(e)}

    @staticmethod
    def _fetch_fear_greed() -> dict:
        """CNN Fear & Greed Index 수집."""
        try:
            import requests
            resp = requests.get(
                "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                score = data.get("fear_and_greed", {}).get("score", None)
                rating = data.get("fear_and_greed", {}).get("rating", None)
                return {"fear_greed_score": round(score, 1) if score else None, "rating": rating}
            return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            logger.warning(f"[Macro] Fear & Greed 수집 실패: {e}")
            return {"error": str(e)}
