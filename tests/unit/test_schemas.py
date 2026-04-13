"""Core schemas 테스트"""
import pytest
from src.core.schemas import (
    Portfolio, Holding, Constraint, AgentReport, PortfolioStance, ConsensusType
)


def test_portfolio_valid():
    p = Portfolio(
        name="test",
        holdings=[
            Holding(ticker="AAPL", name="Apple", market="NASDAQ", weight=50),
            Holding(ticker="BTC", name="Bitcoin", market="Crypto", weight=30),
        ],
        cash_weight=20,
    )
    assert p.name == "test"
    assert len(p.holdings) == 2
    assert p.cash_weight == 20


def test_portfolio_weight_exceeds_100():
    with pytest.raises(ValueError, match="100%"):
        Portfolio(holdings=[
            Holding(ticker="A", name="A", market="X", weight=60),
            Holding(ticker="B", name="B", market="X", weight=50),
        ])


def test_agent_report_to_dict():
    r = AgentReport(
        agent_name="퀀트", role="분석가", avatar="🔢",
        analysis="이것은 테스트 분석입니다. " * 5,
        key_points=["핵심1"],
        confidence_score=75,
        overall_stance=PortfolioStance.OVERWEIGHT,
    )
    d = r.to_dict()
    assert d["agent_name"] == "퀀트"
    assert d["confidence_score"] == 75
    assert d["overall_stance"] == "OVERWEIGHT"


def test_portfolio_stance_score():
    assert PortfolioStance.STRONG_OVERWEIGHT.score == 2
    assert PortfolioStance.MAINTAIN.score == 0
    assert PortfolioStance.STRONG_UNDERWEIGHT.score == -2


def test_constraint_defaults():
    c = Constraint()
    assert c.max_single_stock_weight == 30
    assert c.min_cash_weight == 5
