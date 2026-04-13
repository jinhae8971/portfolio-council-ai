"""PortfolioService — 전체 분석 파이프라인 오케스트레이션"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from ..core.base_agent import BaseAgent
from ..core.debate_engine import DebateEngine
from ..core.moderator import Moderator
from ..core.schemas import FullReport
from ..infrastructure.data.market_fetcher import MarketDataFetcher
from ..infrastructure.data.macro_fetcher import FREDMacroFetcher
from ..infrastructure.data.crypto_fetcher import CoinGeckoCryptoFetcher
from ..infrastructure.llm.base import LLMProvider
from ..infrastructure.storage.base import ResultStorage
from ..infrastructure.notification.telegram_notifier import TelegramNotifier

logger = logging.getLogger(__name__)


class PortfolioService:
    """전체 투자 분석 파이프라인."""

    def __init__(
        self,
        agents: List[BaseAgent],
        llm: LLMProvider,
        storage: ResultStorage,
        debate_rounds: int = 1,
    ):
        self.agents = agents
        self.llm = llm
        self.storage = storage
        self.debate_engine = DebateEngine(agents, debate_rounds=debate_rounds)
        self.moderator = Moderator(llm)
        self.notifier = TelegramNotifier()

    def run(
        self,
        portfolio: dict,
        user_id: str = "default",
        notify: bool = True,
        dashboard_url: str = "",
    ) -> dict:
        """전체 파이프라인 실행.

        1. 시장 데이터 수집
        2. 6에이전트 토론 (Phase 1 + 2)
        3. Moderator 종합 (Phase 3)
        4. 결과 저장 + 알림
        """
        today = datetime.now().strftime("%Y-%m-%d")
        logger.info(f"[Pipeline] 분석 시작 — {today}, user={user_id}")

        # 1. 데이터 수집
        market_data = self._collect_data(portfolio)

        # 2. 토론 실행
        debate_result = self.debate_engine.run(portfolio, market_data, user_id)

        # 3. Moderator 종합 (agent_weights 전달)
        agent_weights = portfolio.get("agent_weights")
        verdict = self.moderator.synthesize(
            debate_result, portfolio, market_data, user_id,
            agent_weights=agent_weights,
        )

        # 4. 보고서 조립
        report = {
            "date": today,
            "generated_at": datetime.now().isoformat(),
            "user_id": user_id,
            "portfolio": portfolio,
            "domain_data": market_data,
            "debate": debate_result.model_dump(mode="json"),
            "verdict": verdict.to_dict(),
        }

        # 5. 저장
        self.storage.save_report(report, user_id)
        self.storage.save_latest(report, user_id)
        logger.info(f"[Pipeline] 보고서 저장 완료 — {today}")

        # 6. 알림
        if notify:
            self.notifier.send(verdict.to_dict(), today, dashboard_url)

        logger.info(
            f"[Pipeline] 분석 완료 — "
            f"합의={verdict.consensus_type.value}, "
            f"확신도={verdict.confidence_score}%"
        )

        return report

    def _collect_data(self, portfolio: dict) -> dict:
        """포트폴리오 종목에 맞춰 데이터 수집."""
        tickers = []
        crypto_tickers = []

        for h in portfolio.get("holdings", []):
            if h.get("market") == "Crypto":
                crypto_tickers.append(h["ticker"])
            else:
                tickers.append(h["ticker"])

        market_data = {"collected_at": datetime.now().isoformat()}

        # 주식 데이터
        if tickers:
            try:
                fetcher = MarketDataFetcher()
                market_data["stocks"] = fetcher.fetch(tickers).get("stocks", {})
            except Exception as e:
                logger.error(f"[Data] 주식 데이터 수집 실패: {e}")
                market_data["stocks"] = {"error": str(e)}

        # 매크로 데이터
        try:
            macro = FREDMacroFetcher()
            macro_data = macro.fetch()
            market_data["macro"] = macro_data
        except Exception as e:
            logger.error(f"[Data] 매크로 데이터 수집 실패: {e}")
            market_data["macro"] = {"error": str(e)}

        # 크립토 데이터
        if crypto_tickers:
            try:
                crypto = CoinGeckoCryptoFetcher()
                market_data["crypto"] = crypto.fetch(crypto_tickers)
            except Exception as e:
                logger.error(f"[Data] 크립토 데이터 수집 실패: {e}")
                market_data["crypto"] = {"error": str(e)}

        return market_data
