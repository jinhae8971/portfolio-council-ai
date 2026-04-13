"""BaseAgent — 모든 전문가 에이전트의 추상 기본 클래스

Domain Layer에 속하므로 외부 의존성(anthropic 등)을 직접 import하지 않는다.
LLM 호출은 Infrastructure Layer의 LLMProvider 인터페이스를 통해 수행한다.
"""

from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, Dict

from .schemas import AgentCritique, AgentReport, PortfolioStance

if TYPE_CHECKING:
    from ..infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)


class BaseAgent(ABC):
    """멀티에이전트 토론 시스템의 에이전트 기본 클래스."""

    name: str = ""
    role: str = ""
    avatar: str = "🤖"
    system_prompt: str = ""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    # ── 서브클래스에서 반드시 구현 ──────────────────────────────────

    @abstractmethod
    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        """Phase 1: 독립 분석. 포트폴리오와 시장 데이터를 받아 분석 보고서 반환."""
        raise NotImplementedError

    @abstractmethod
    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        """Phase 2: 다른 에이전트의 분석에 대한 교차 반론."""
        raise NotImplementedError

    # ── LLM 호출 헬퍼 ─────────────────────────────────────────────

    def _call_llm(self, user_message: str, max_tokens: int = 4096) -> str:
        """LLMProvider를 통해 LLM 호출."""
        return self.llm.complete(
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
            max_tokens=max_tokens,
        )

    # ── JSON 파싱 (강화 패턴) ──────────────────────────────────────

    @staticmethod
    def parse_json_response(text: str) -> dict:
        """LLM 응답에서 JSON 추출. 코드블록·설명문 혼재에도 안전."""
        # 1) 마크다운 코드블록 제거
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = re.sub(r"```\s*", "", text)
        text = text.strip()

        # 2) 첫 번째 JSON 객체 추출
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                # 3) 줄바꿈/탭 정리 후 재시도
                cleaned = match.group().replace("\n", " ").replace("\t", " ")
                try:
                    return json.loads(cleaned)
                except json.JSONDecodeError:
                    pass

        logger.warning(f"JSON 파싱 실패, 빈 dict 반환. 원문 앞 200자: {text[:200]}")
        return {}

    # ── 데이터 포맷팅 헬퍼 ─────────────────────────────────────────

    @staticmethod
    def format_portfolio_summary(portfolio: dict) -> str:
        """포트폴리오를 에이전트가 읽기 좋은 텍스트로 변환."""
        lines = [f"포트폴리오: {portfolio.get('name', 'unknown')}"]
        lines.append(f"현금 비중: {portfolio.get('cash_weight', 0)}%")
        lines.append(f"기준 통화: {portfolio.get('base_currency', 'KRW')}")
        lines.append("")
        lines.append("[보유 종목]")

        for h in portfolio.get("holdings", []):
            line = f"  {h['ticker']} ({h['name']}) — {h['weight']}%"
            if h.get("sector"):
                line += f" [{h['sector']}]"
            if h.get("avg_price"):
                line += f" / 평단가: {h['avg_price']}"
            lines.append(line)

        constraints = portfolio.get("constraints", {})
        if constraints:
            lines.append("")
            lines.append("[투자 제약]")
            for k, v in constraints.items():
                lines.append(f"  {k}: {v}%")

        return "\n".join(lines)

    @staticmethod
    def format_market_data(market_data: dict) -> str:
        """시장 데이터를 읽기 좋은 텍스트로 변환."""
        lines = [f"수집 시각: {market_data.get('collected_at', 'unknown')}"]
        for k, v in market_data.items():
            if k == "collected_at":
                continue
            if isinstance(v, dict):
                lines.append(f"\n[{k}]")
                for sk, sv in v.items():
                    lines.append(f"  {sk}: {sv}")
            else:
                lines.append(f"{k}: {v}")
        return "\n".join(lines)

    # ── 안전한 AgentReport 생성 ────────────────────────────────────

    def _build_report(self, data: dict, raw_text: str) -> AgentReport:
        """파싱된 JSON에서 AgentReport를 안전하게 생성."""
        stance_str = data.get("overall_stance", "MAINTAIN").upper()
        try:
            stance = PortfolioStance(stance_str)
        except ValueError:
            stance = PortfolioStance.MAINTAIN

        return AgentReport(
            agent_name=self.name,
            role=self.role,
            avatar=self.avatar,
            analysis=data.get("analysis", raw_text[:600]),
            key_points=data.get("key_points", ["분석 완료"]),
            confidence_score=max(0, min(100, int(data.get("confidence_score", 50)))),
            overall_stance=stance,
            ticker_recommendations=data.get("ticker_recommendations", []),
            cash_recommendation=data.get("cash_recommendation"),
            evidence=data.get("evidence", []),
        )
