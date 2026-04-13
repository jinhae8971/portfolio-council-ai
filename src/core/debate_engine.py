"""DebateEngine — Phase 1(독립 분석) + Phase 2(교차 반론) 실행기

LangGraph 없이 직접 구현. 고정된 3-Phase 파이프라인에 최적화.
"""

from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, List, Tuple

from .schemas import AgentCritique, AgentReport, DebateResult

if TYPE_CHECKING:
    from .base_agent import BaseAgent

logger = logging.getLogger(__name__)

# 6에이전트 교차 반론 페어링
# 원칙: 분석 축이 다른 에이전트끼리 연결
# 0=퀀트, 1=매크로, 2=섹터, 3=사이클, 4=크립토, 5=가치투자자
CRITIQUE_PAIRS: List[Tuple[int, int]] = [
    (0, 5),  # 퀀트(단기 기술적) → 가치투자자(장기 펀더멘탈)
    (5, 0),  # 가치투자자 → 퀀트
    (1, 2),  # 매크로(하향식) → 섹터(상향식)
    (2, 1),  # 섹터 → 매크로
    (3, 4),  # 사이클(전통 타이밍) → 크립토(대안자산)
    (4, 3),  # 크립토 → 사이클
]


class DebateEngine:
    """Phase 1 + Phase 2를 실행하는 토론 엔진."""

    def __init__(
        self,
        agents: List[BaseAgent],
        critique_pairs: List[Tuple[int, int]] | None = None,
        debate_rounds: int = 1,
    ):
        self.agents = agents
        self.critique_pairs = critique_pairs or CRITIQUE_PAIRS
        self.debate_rounds = debate_rounds

    def run(
        self,
        portfolio: dict,
        market_data: dict,
        user_id: str = "default",
    ) -> DebateResult:
        """전체 토론 실행 (Phase 1 + Phase 2)."""
        logger.info(f"[DebateEngine] 토론 시작 — 에이전트 {len(self.agents)}명, user={user_id}")

        # Phase 1: 독립 분석
        reports = self._phase1_analyze(portfolio, market_data, user_id)

        # Phase 2: 교차 반론 (N라운드)
        all_critiques = []
        for round_num in range(self.debate_rounds):
            logger.info(f"[DebateEngine] Phase 2 Round {round_num + 1}/{self.debate_rounds}")
            critiques = self._phase2_debate(reports, portfolio, market_data, user_id)
            all_critiques.extend(critiques)

        return DebateResult(
            phase1_reports=[r.to_dict() for r in reports],
            phase2_critiques=[c.to_dict() for c in all_critiques],
        )

    def _phase1_analyze(
        self,
        portfolio: dict,
        market_data: dict,
        user_id: str,
    ) -> List[AgentReport]:
        """Phase 1: 각 에이전트 독립 분석."""
        reports: List[AgentReport] = []

        for agent in self.agents:
            start_time = time.time()
            try:
                report = agent.analyze(portfolio, market_data, user_id)
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    f"[Phase1] {agent.name} 분석 완료 — "
                    f"stance={report.overall_stance.value}, "
                    f"confidence={report.confidence_score}, "
                    f"duration={duration_ms}ms"
                )
                reports.append(report)

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(f"[Phase1] {agent.name} 분석 실패: {e} ({duration_ms}ms)")

                # Fallback: confidence=0으로 투표에서 제외
                fallback_report = AgentReport(
                    agent_name=agent.name,
                    role=agent.role,
                    avatar=agent.avatar,
                    analysis=f"분석 중 오류 발생: {str(e)[:200]}. 이 에이전트의 의견은 최종 판단에서 제외됩니다.",
                    key_points=["분석 실패"],
                    confidence_score=0,
                    overall_stance="MAINTAIN",
                    evidence=[],
                )
                reports.append(fallback_report)

        return reports

    def _phase2_debate(
        self,
        reports: List[AgentReport],
        portfolio: dict,
        market_data: dict,
        user_id: str,
    ) -> List[AgentCritique]:
        """Phase 2: 교차 반론."""
        critiques: List[AgentCritique] = []

        for from_idx, to_idx in self.critique_pairs:
            if from_idx >= len(self.agents) or to_idx >= len(reports):
                logger.warning(
                    f"[Phase2] 페어링 ({from_idx}, {to_idx}) 범위 초과 — 건너뜀"
                )
                continue

            agent = self.agents[from_idx]
            target_report = reports[to_idx]

            start_time = time.time()
            try:
                critique = agent.critique(target_report, portfolio, market_data, user_id)
                duration_ms = int((time.time() - start_time) * 1000)
                logger.info(
                    f"[Phase2] {agent.name} → {target_report.agent_name} 반론 완료 "
                    f"({duration_ms}ms)"
                )
                critiques.append(critique)

            except Exception as e:
                duration_ms = int((time.time() - start_time) * 1000)
                logger.error(
                    f"[Phase2] {agent.name} → {target_report.agent_name} 반론 실패: {e}"
                )
                fallback_critique = AgentCritique(
                    from_agent=agent.name,
                    to_agent=target_report.agent_name,
                    critique=f"반론 생성 중 오류: {str(e)[:100]}",
                )
                critiques.append(fallback_critique)

        return critiques
