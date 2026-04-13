"""암호화폐 데이터 수집기 — CoinGecko API + Rate Limiter"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, List

from .base import CryptoFetcher
from ...utils.rate_limiter import RateLimiterRegistry

logger = logging.getLogger(__name__)

# 티커 → CoinGecko ID 매핑
TICKER_TO_COINGECKO = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "BNB": "binancecoin",
    "XRP": "ripple",
    "ADA": "cardano",
    "DOGE": "dogecoin",
    "AVAX": "avalanche-2",
    "DOT": "polkadot",
    "MATIC": "matic-network",
    "LINK": "chainlink",
    "UNI": "uniswap",
}


class CoinGeckoCryptoFetcher(CryptoFetcher):
    """CoinGecko 무료 API로 암호화폐 데이터 수집. Rate Limiter 적용."""

    def __init__(self):
        self._rate_limiter = RateLimiterRegistry.get()

    def fetch(self, coins: List[str]) -> Dict[str, Any]:
        result = {"collected_at": datetime.now().isoformat(), "coins": {}}

        # 티커를 CoinGecko ID로 변환
        coin_ids = []
        ticker_map = {}
        for coin in coins:
            cg_id = TICKER_TO_COINGECKO.get(coin.upper(), coin.lower())
            coin_ids.append(cg_id)
            ticker_map[cg_id] = coin.upper()

        try:
            self._rate_limiter.wait("coingecko")
            import requests
            resp = requests.get(
                "https://api.coingecko.com/api/v3/coins/markets",
                params={
                    "vs_currency": "usd",
                    "ids": ",".join(coin_ids),
                    "order": "market_cap_desc",
                    "sparkline": "false",
                    "price_change_percentage": "24h,7d,30d",
                },
                headers={"User-Agent": "PortfolioCouncilAI/1.0"},
                timeout=15,
            )

            if resp.status_code == 200:
                for item in resp.json():
                    ticker = ticker_map.get(item["id"], item["symbol"].upper())
                    result["coins"][ticker] = {
                        "price_usd": item.get("current_price"),
                        "market_cap": item.get("market_cap"),
                        "volume_24h": item.get("total_volume"),
                        "change_24h": round(item.get("price_change_percentage_24h", 0), 2),
                        "change_7d": round(item.get("price_change_percentage_7d_in_currency", 0) or 0, 2),
                        "change_30d": round(item.get("price_change_percentage_30d_in_currency", 0) or 0, 2),
                        "ath": item.get("ath"),
                        "ath_change_pct": round(item.get("ath_change_percentage", 0), 1),
                        "market_cap_rank": item.get("market_cap_rank"),
                    }
            else:
                logger.warning(f"[Crypto] CoinGecko HTTP {resp.status_code}")
                result["error"] = f"HTTP {resp.status_code}"

        except Exception as e:
            logger.error(f"[Crypto] CoinGecko 수집 실패: {e}")
            result["error"] = str(e)

        # 글로벌 크립토 메트릭
        result["global"] = self._fetch_global_metrics()

        return result

    @classmethod
    def _fetch_global_metrics(cls) -> dict:
        """크립토 시장 전체 메트릭 수집."""
        try:
            RateLimiterRegistry.get().wait("coingecko")
            import requests
            resp = requests.get(
                "https://api.coingecko.com/api/v3/global",
                headers={"User-Agent": "PortfolioCouncilAI/1.0"},
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json().get("data", {})
                return {
                    "total_market_cap_usd": data.get("total_market_cap", {}).get("usd"),
                    "btc_dominance": round(data.get("market_cap_percentage", {}).get("btc", 0), 1),
                    "eth_dominance": round(data.get("market_cap_percentage", {}).get("eth", 0), 1),
                    "active_cryptocurrencies": data.get("active_cryptocurrencies"),
                }
            return {"error": f"HTTP {resp.status_code}"}
        except Exception as e:
            return {"error": str(e)}
