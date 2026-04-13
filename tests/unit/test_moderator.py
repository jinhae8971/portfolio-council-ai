"""Moderator 테스트 — Phase 3 종합 판단 검증"""
import pytest
from unittest.mock import MagicMock
from src.core.moderator import Moderator
from src.core.schemas import DebateResult, ConsensusType


def _make_debate_result(stances_and_confs):
    """테스트용 DebateResult 생성."""
    reports = []
    names = ["퀀트", "매크로", "섹터", "사이클", "크립토", "가치투자자"]
    for i, (stance, conf) in enumerate(stances_and_confs):
        reports.append({
            "agent_name": names[i] if i < len(names) else f"agent_{i}",
            "role": "test role",
            "avatar": "🤖",
            "analysis": f"테스트 분석 " * 20,
            "key_points": ["핵심1"],
            "confidence_score": conf,
            "overall_stance": stance,
        })

    return DebateResult(
        phase1_reports=reports,
        phase2_critiques=[{
            "from_agent": "퀀트", "to_agent": "가치투자자",
            "critique": "테스트 반론입니다."
        }],
    )


class FakeLLM:
    """LLM을 시뮬레이션하는 가짜 Provider."""
    def __init__(self, response: str = "", should_fail: bool = False):
        self.response = response
        self.should_fail = should_fail

    def complete(self, system, messages, max_tokens=2048):
        if self.should_fail:
            raise RuntimeError("LLM 호출 실패")
        return self.response


SAMPLE_PORTFOLIO = {"name": "test", "holdings": [{"ticker": "AAPL", "name": "Apple", "weight": 50}], "cash_weight": 20}
SAMPLE_MARKET = {"collected_at": "2026-04-13"}


def test_moderator_fallback_on_llm_failure():
    """LLM 실패 시 규칙 기반 fallback 사용."""
    llm = FakeLLM(should_fail=True)
    moderator = Moderator(llm)

    debate = _make_debate_result([
        ("OVERWEIGHT", 80), ("OVERWEIGHT", 70), ("OVERWEIGHT", 60),
        ("OVERWEIGHT", 50), ("MAINTAIN", 40), ("UNDERWEIGHT", 30),
    ])

    verdict = moderator.synthesize(debate, SAMPLE_PORTFOLIO, SAMPLE_MARKET)

    # fallback이므로 기본 필드가 있어야 함
    assert verdict.confidence_score > 0
    assert verdict.consensus_type in ConsensusType


def test_moderator_with_valid_llm_response():
    """유효한 LLM 응답 시 정상 처리."""
    llm_response = '''{
        "consensus_type": "majority_view",
        "confidence_score": 72,
        "summary": "테스트 종합 판단입니다. 다수 에이전트가 비중 확대를 권고했습니다.",
        "portfolio_changes": [{"ticker": "AAPL", "name": "Apple", "action": "increase", "from_weight": 50, "to_weight": 55, "reason": "테스트", "supporters": ["퀀트"]}],
        "risk_warnings": ["테스트 리스크"],
        "key_insights": ["테스트 인사이트"],
        "action_items": ["테스트 행동"]
    }'''
    llm = FakeLLM(response=llm_response)
    moderator = Moderator(llm)

    debate = _make_debate_result([
        ("OVERWEIGHT", 80), ("OVERWEIGHT", 70), ("MAINTAIN", 60),
        ("OVERWEIGHT", 50), ("MAINTAIN", 40), ("UNDERWEIGHT", 30),
    ])

    verdict = moderator.synthesize(debate, SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert verdict.confidence_score == 72
    assert len(verdict.portfolio_changes) == 1
    assert verdict.risk_warnings == ["테스트 리스크"]


def test_moderator_strong_consensus_detection():
    """5-6 에이전트 동의 시 strong_consensus."""
    llm = FakeLLM(should_fail=True)  # fallback 사용
    moderator = Moderator(llm)

    debate = _make_debate_result([("OVERWEIGHT", 80)] * 6)
    verdict = moderator.synthesize(debate, SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert verdict.consensus_type == ConsensusType.STRONG_CONSENSUS


def test_moderator_split_decision():
    """3:3 분열 시 split_decision."""
    llm = FakeLLM(should_fail=True)
    moderator = Moderator(llm)

    debate = _make_debate_result([
        ("OVERWEIGHT", 70), ("OVERWEIGHT", 70), ("OVERWEIGHT", 70),
        ("UNDERWEIGHT", 70), ("UNDERWEIGHT", 70), ("UNDERWEIGHT", 70),
    ])
    verdict = moderator.synthesize(debate, SAMPLE_PORTFOLIO, SAMPLE_MARKET)
    assert verdict.consensus_type == ConsensusType.SPLIT_DECISION
