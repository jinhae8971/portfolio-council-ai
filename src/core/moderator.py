"""Moderator — Phase 3 하이브리드 종합 판단

1단계: 규칙 기반 가중 투표 (선행 집계)
2단계: LLM 품질 평가 (토론 내용 기반 최종 판단)
LLM 실패 시 1단계 결과를 fallback으로 사용.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING, Dict, List

from .consensus import determine_consensus_type, rule_based_verdict, weighted_vote, score_to_stance
from .schemas import ConsensusType, DebateResult, PortfolioStance, Verdict

if TYPE_CHECKING:
    from ..infrastructure.llm.base import LLMProvider

logger = logging.getLogger(__name__)

MODERATOR_SYSTEM_PROMPT = """당신은 투자자문 위원회의 의장(Moderator)입니다.

[역할]
- 6명의 전문가 에이전트(퀀트, 매크로, 섹터, 사이클, 크립토, 가치투자자)의 토론을 종합합니다.
- 다수결이 아닌 "근거 품질 가중 합의" 방식으로 최종 판단을 내립니다.
- 데이터 기반 정량 분석은 가중치 1.0, 정성적 분석+데이터는 0.8, 순수 정성적은 0.5로 평가합니다.

[투자 제약 준수]
- 포트폴리오 제약 조건을 반드시 확인하고, 위반하는 추천은 수정합니다.
- 단일 종목 최대 비중, 섹터 최대 비중, 암호화폐 최대 비중 등을 고려합니다.

[출력]
반드시 아래 JSON 형식으로만 응답하세요:
{
  "consensus_type": "strong_consensus | majority_view | split_decision | no_consensus",
  "confidence_score": 68,
  "summary": "종합 판단 근거 (300자 이상)",
  "portfolio_changes": [
    {"ticker": "AAPL", "name": "Apple", "action": "reduce", "from_weight": 20, "to_weight": 15, "reason": "...", "supporters": ["quant", "value"]}
  ],
  "cash_recommendation": {"current": 10, "target": 15, "reason": "..."},
  "new_picks": [
    {"ticker": "GOOGL", "name": "Alphabet", "suggested_weight": 5, "reason": "...", "supporters": ["sector", "value"]}
  ],
  "risk_warnings": ["위험1", "위험2"],
  "key_insights": ["인사이트1", "인사이트2"],
  "action_items": ["행동1", "행동2"],
  "debate_highlights": [
    {"topic": "NVDA 밸류에이션", "for": ["quant"], "against": ["value"], "resolution": "..."}
  ]
}"""


class Moderator:
    """Phase 3 종합 판정관."""

    def __init__(self, llm: LLMProvider):
        self.llm = llm

    def synthesize(
        self,
        debate_result: DebateResult,
        portfolio: dict,
        market_data: dict,
        user_id: str = "default",
        agent_weights: dict | None = None,
    ) -> Verdict:
        """토론 결과를 종합하여 최종 Verdict 도출.

        Args:
            agent_weights: 사용자 커스텀 에이전트 가중치 (예: {"퀀트": 1.5})
        """
        reports = debate_result.phase1_reports
        critiques = debate_result.phase2_critiques

        # 1단계: 규칙 기반 선행 집계 (agent_weights 반영)
        rule_result = rule_based_verdict(reports, agent_weights)
        consensus = determine_consensus_type(reports)

        # 2단계: LLM 종합 판단
        start_time = time.time()
        try:
            llm_result = self._llm_synthesize(reports, critiques, portfolio, rule_result, agent_weights)
            duration_ms = int((time.time() - start_time) * 1000)
            logger.info(f"[Moderator] LLM 종합 완료 ({duration_ms}ms)")

            # LLM 결과와 규칙 기반 결과 병합
            final = self._merge_results(llm_result, rule_result, consensus)

        except Exception as e:
            duration_ms = int((time.time() - start_time) * 1000)
            logger.error(f"[Moderator] LLM 종합 실패: {e} ({duration_ms}ms) — 규칙 기반 fallback")
            final = rule_result
            final["consensus_type"] = consensus.value

        # Verdict 객체 생성
        return Verdict(
            consensus_type=ConsensusType(final.get("consensus_type", "no_consensus")),
            confidence_score=int(final.get("confidence_score", 50)),
            summary=final.get("summary", ""),
            portfolio_changes=final.get("portfolio_changes", []),
            cash_recommendation=final.get("cash_recommendation"),
            new_picks=final.get("new_picks", []),
            risk_warnings=final.get("risk_warnings", []),
            debate_highlights=final.get("debate_highlights", []),
            stance_votes=final.get("stance_votes", {}),
            key_insights=final.get("key_insights", []),
            action_items=final.get("action_items", []),
        )

    def _llm_synthesize(
        self,
        reports: List[dict],
        critiques: List[dict],
        portfolio: dict,
        rule_result: dict,
        agent_weights: dict | None = None,
    ) -> dict:
        """LLM을 사용한 토론 종합."""
        debate_text = self._format_debate(reports, critiques)
        portfolio_text = self._format_portfolio(portfolio)
        weights_text = self._format_agent_weights(agent_weights)

        prompt = f"""아래 포트폴리오에 대한 에이전트 토론을 종합해 최종 투자 의견을 제시해주세요.

[현재 포트폴리오]
{portfolio_text}
{weights_text}
[에이전트 토론 기록]
{debate_text}

[규칙 기반 선행 판단]
합의 유형: {rule_result.get('consensus_type')}
종합 확신도: {rule_result.get('confidence_score')}

위 토론 내용과 포트폴리오를 분석하여, 반드시 지정된 JSON 형식으로만 응답해주세요."""

        result_text = self.llm.complete(
            system=MODERATOR_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=3000,
        )

        # JSON 파싱 (BaseAgent의 파서 재사용)
        import re
        text = re.sub(r"```(?:json)?\s*", "", result_text)
        text = re.sub(r"```\s*", "", text).strip()
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            return json.loads(match.group())

        raise ValueError("LLM 응답에서 유효한 JSON을 찾을 수 없음")

    def _merge_results(self, llm_result: dict, rule_result: dict, consensus: ConsensusType) -> dict:
        """LLM 결과에 규칙 기반 정보를 병합."""
        merged = {**llm_result}

        # stance_votes는 규칙 기반에서 가져옴 (정확한 투표 기록)
        merged["stance_votes"] = rule_result.get("stance_votes", {})

        # consensus_type은 규칙 기반이 더 정확
        merged["consensus_type"] = consensus.value

        return merged

    @staticmethod
    def _format_agent_weights(agent_weights: dict | None) -> str:
        """에이전트 가중치를 텍스트로 포맷팅."""
        if not agent_weights:
            return ""
        non_default = {k: v for k, v in agent_weights.items() if v != 1.0}
        if not non_default:
            return ""
        lines = ["\n[에이전트 가중치 (사용자 커스텀)]"]
        for name, weight in non_default.items():
            label = "강화" if weight > 1.0 else "약화" if weight < 1.0 else "기본"
            lines.append(f"  {name}: {weight}x ({label})")
        lines.append("  ※ 가중치가 높은 에이전트의 의견을 더 비중있게 반영해주세요")
        return "\n".join(lines) + "\n"

    @staticmethod
    def _format_debate(reports: List[dict], critiques: List[dict]) -> str:
        """토론 기록을 텍스트로 포맷팅."""
        lines = ["=== Phase 1: 독립 분석 ==="]
        for r in reports:
            lines.append(f"\n--- {r.get('avatar', '🤖')} {r.get('agent_name', '?')} ({r.get('role', '?')}) ---")
            lines.append(f"종합 판단: {r.get('overall_stance', '?')} (확신도: {r.get('confidence_score', 0)})")
            lines.append(f"분석: {r.get('analysis', '')[:400]}")
            kp = r.get('key_points', [])
            if kp:
                lines.append(f"핵심: {', '.join(kp[:3])}")

        lines.append("\n=== Phase 2: 교차 반론 ===")
        for c in critiques:
            lines.append(f"\n{c.get('from_agent', '?')} → {c.get('to_agent', '?')}:")
            lines.append(f"  {c.get('critique', '')[:300]}")

        return "\n".join(lines)

    @staticmethod
    def _format_portfolio(portfolio: dict) -> str:
        """포트폴리오를 텍스트로 포맷팅."""
        lines = [f"이름: {portfolio.get('name', 'unknown')}"]
        lines.append(f"현금: {portfolio.get('cash_weight', 0)}%")
        for h in portfolio.get("holdings", []):
            lines.append(f"  {h['ticker']} ({h.get('name', '')}) — {h['weight']}%")
        return "\n".join(lines)
