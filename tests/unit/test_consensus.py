"""합의 도출 알고리즘 테스트"""
from src.core.consensus import (
    weighted_vote, score_to_stance, determine_consensus_type, rule_based_verdict
)
from src.core.schemas import PortfolioStance, ConsensusType


def _make_reports(stances_and_confs):
    return [
        {"agent_name": f"agent_{i}", "overall_stance": s, "confidence_score": c}
        for i, (s, c) in enumerate(stances_and_confs)
    ]


def test_weighted_vote_all_overweight():
    reports = _make_reports([
        ("OVERWEIGHT", 80), ("OVERWEIGHT", 70), ("OVERWEIGHT", 60),
        ("OVERWEIGHT", 50), ("OVERWEIGHT", 90), ("OVERWEIGHT", 75),
    ])
    score, avg_conf = weighted_vote(reports)
    assert score > 0.5
    assert avg_conf > 50


def test_weighted_vote_split():
    reports = _make_reports([
        ("OVERWEIGHT", 80), ("OVERWEIGHT", 70), ("OVERWEIGHT", 60),
        ("UNDERWEIGHT", 80), ("UNDERWEIGHT", 70), ("UNDERWEIGHT", 60),
    ])
    score, _ = weighted_vote(reports)
    assert abs(score) < 0.1  # 거의 0


def test_score_to_stance():
    assert score_to_stance(1.8) == PortfolioStance.STRONG_OVERWEIGHT
    assert score_to_stance(0.7) == PortfolioStance.OVERWEIGHT
    assert score_to_stance(0.0) == PortfolioStance.MAINTAIN
    assert score_to_stance(-0.7) == PortfolioStance.UNDERWEIGHT
    assert score_to_stance(-1.8) == PortfolioStance.STRONG_UNDERWEIGHT


def test_strong_consensus():
    reports = _make_reports([("OVERWEIGHT", 80)] * 6)
    assert determine_consensus_type(reports) == ConsensusType.STRONG_CONSENSUS


def test_majority_view():
    reports = _make_reports([
        ("OVERWEIGHT", 80), ("OVERWEIGHT", 70), ("OVERWEIGHT", 60),
        ("OVERWEIGHT", 50), ("MAINTAIN", 40), ("UNDERWEIGHT", 30),
    ])
    assert determine_consensus_type(reports) == ConsensusType.MAJORITY_VIEW


def test_split_decision():
    reports = _make_reports([
        ("OVERWEIGHT", 80), ("OVERWEIGHT", 70), ("OVERWEIGHT", 60),
        ("UNDERWEIGHT", 80), ("UNDERWEIGHT", 70), ("UNDERWEIGHT", 60),
    ])
    assert determine_consensus_type(reports) == ConsensusType.SPLIT_DECISION


def test_rule_based_verdict_has_required_fields():
    reports = _make_reports([("OVERWEIGHT", 80), ("MAINTAIN", 50)])
    result = rule_based_verdict(reports)
    assert "consensus_type" in result
    assert "confidence_score" in result
    assert "stance_votes" in result
