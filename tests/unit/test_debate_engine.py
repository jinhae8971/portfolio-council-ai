"""DebateEngine 테스트 — Phase 1 + Phase 2 동작 검증"""
import pytest
from unittest.mock import MagicMock
from src.core.debate_engine import DebateEngine, CRITIQUE_PAIRS
from src.core.schemas import AgentReport, AgentCritique, PortfolioStance


class FakeAgent:
    """테스트용 가짜 에이전트."""
    def __init__(self, name, stance="MAINTAIN", confidence=70, fail_analyze=False, fail_critique=False):
        self.name = name
        self.role = f"{name} role"
        self.avatar = "🤖"
        self._stance = stance
        self._confidence = confidence
        self._fail_analyze = fail_analyze
        self._fail_critique = fail_critique

    def analyze(self, portfolio, market_data, user_id="default"):
        if self._fail_analyze:
            raise RuntimeError(f"{self.name} analyze failed")
        return AgentReport(
            agent_name=self.name, role=self.role, avatar=self.avatar,
            analysis=f"{self.name}의 분석 결과입니다. " * 10,
            key_points=[f"{self.name} 핵심 포인트"],
            confidence_score=self._confidence,
            overall_stance=PortfolioStance(self._stance),
        )

    def critique(self, other_report, portfolio, market_data, user_id="default"):
        if self._fail_critique:
            raise RuntimeError(f"{self.name} critique failed")
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=f"{self.name}이(가) {other_report.agent_name}에 대해 반론합니다.",
        )


def make_6_agents(**overrides):
    names = ["퀀트", "매크로", "섹터", "사이클", "크립토", "가치투자자"]
    return [FakeAgent(n, **overrides) for n in names]


SAMPLE_PORTFOLIO = {"name": "test", "holdings": [], "cash_weight": 10}
SAMPLE_MARKET = {"collected_at": "2026-04-13"}


def test_phase1_returns_6_reports():
    engine = DebateEngine(make_6_agents())
    result = engine.run(SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert len(result.phase1_reports) == 6


def test_phase2_returns_6_critiques():
    engine = DebateEngine(make_6_agents())
    result = engine.run(SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert len(result.phase2_critiques) == 6


def test_critique_pairs_are_correct():
    """교차 반론 페어링이 설계대로 작동하는지."""
    expected_pairs = [(0, 5), (5, 0), (1, 2), (2, 1), (3, 4), (4, 3)]
    assert CRITIQUE_PAIRS == expected_pairs


def test_failed_agent_gets_zero_confidence():
    """분석 실패한 에이전트는 confidence=0으로 처리."""
    agents = make_6_agents()
    agents[2] = FakeAgent("실패에이전트", fail_analyze=True)
    engine = DebateEngine(agents)
    result = engine.run(SAMPLE_PORTFOLIO, SAMPLE_MARKET)

    failed = result.phase1_reports[2]
    assert failed["confidence_score"] == 0
    assert "오류" in failed["analysis"]


def test_failed_critique_still_returns():
    """반론 실패해도 fallback critique가 반환."""
    agents = make_6_agents()
    agents[0] = FakeAgent("퀀트", fail_critique=True)
    engine = DebateEngine(agents)
    result = engine.run(SAMPLE_PORTFOLIO, SAMPLE_MARKET)

    # 퀀트→가치투자자 반론이 있어야 함 (fallback)
    quant_critiques = [c for c in result.phase2_critiques if c["from_agent"] == "퀀트"]
    assert len(quant_critiques) == 1
    assert "오류" in quant_critiques[0]["critique"]


def test_multiple_debate_rounds():
    """2라운드 토론 시 critique 수가 2배."""
    engine = DebateEngine(make_6_agents(), debate_rounds=2)
    result = engine.run(SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert len(result.phase2_critiques) == 12  # 6 pairs × 2 rounds


def test_custom_critique_pairs():
    """커스텀 페어링 적용."""
    custom_pairs = [(0, 1), (1, 0)]
    engine = DebateEngine(make_6_agents(), critique_pairs=custom_pairs)
    result = engine.run(SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert len(result.phase2_critiques) == 2
