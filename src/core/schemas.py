"""Portfolio Council AI — Core Domain Schemas

외부 의존성 ZERO. 순수 Pydantic 모델로 전체 도메인 객체를 정의한다.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ── 포트폴리오 스탠스 (5단계) ──────────────────────────────────────

class PortfolioStance(str, Enum):
    STRONG_OVERWEIGHT = "STRONG_OVERWEIGHT"    # 적극 비중 확대
    OVERWEIGHT = "OVERWEIGHT"                  # 비중 확대
    MAINTAIN = "MAINTAIN"                      # 현행 유지
    UNDERWEIGHT = "UNDERWEIGHT"                # 비중 축소
    STRONG_UNDERWEIGHT = "STRONG_UNDERWEIGHT"  # 적극 비중 축소

    @property
    def score(self) -> int:
        return {
            "STRONG_OVERWEIGHT": 2,
            "OVERWEIGHT": 1,
            "MAINTAIN": 0,
            "UNDERWEIGHT": -1,
            "STRONG_UNDERWEIGHT": -2,
        }[self.value]


class ConsensusType(str, Enum):
    STRONG_CONSENSUS = "strong_consensus"    # 5-6 에이전트 동의
    MAJORITY_VIEW = "majority_view"          # 4 에이전트 동의
    SPLIT_DECISION = "split_decision"        # 3:3 의견 분열
    NO_CONSENSUS = "no_consensus"            # 분산


# ── 포트폴리오 입력 모델 ──────────────────────────────────────────

class Holding(BaseModel):
    ticker: str = Field(..., description="종목 티커 (예: AAPL, 005930.KS, BTC)")
    name: str = Field(..., description="종목명")
    market: str = Field(..., description="시장 (KRX, NASDAQ, NYSE, Crypto)")
    weight: float = Field(..., ge=0, le=100, description="비중 (%)")
    avg_price: Optional[float] = Field(None, description="평균 매입가")
    sector: Optional[str] = Field(None, description="섹터")


class Constraint(BaseModel):
    max_single_stock_weight: float = Field(30, description="단일 종목 최대 비중 (%)")
    max_sector_weight: float = Field(50, description="단일 섹터 최대 비중 (%)")
    max_crypto_weight: float = Field(15, description="암호화폐 최대 비중 (%)")
    min_cash_weight: float = Field(5, description="최소 현금 비중 (%)")


class Portfolio(BaseModel):
    name: str = Field("my_portfolio", description="포트폴리오 이름")
    updated_at: str = Field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    base_currency: str = Field("KRW", description="기준 통화")
    cash_weight: float = Field(10, ge=0, le=100, description="현금 비중 (%)")
    holdings: List[Holding] = Field(default_factory=list)
    constraints: Constraint = Field(default_factory=Constraint)

    @field_validator("holdings")
    @classmethod
    def validate_total_weight(cls, v: List[Holding]) -> List[Holding]:
        total = sum(h.weight for h in v)
        if total > 100:
            raise ValueError(f"종목 비중 합계({total}%)가 100%를 초과합니다")
        return v


# ── 에이전트 출력 모델 ────────────────────────────────────────────

class TickerRecommendation(BaseModel):
    ticker: str
    name: str
    current_weight: float
    recommended_weight: float
    stance: PortfolioStance
    reason: str


class AgentReport(BaseModel):
    agent_name: str
    role: str
    avatar: str
    analysis: str = Field(..., min_length=50, description="300자 이상 분석")
    key_points: List[str] = Field(default_factory=list)
    confidence_score: int = Field(..., ge=0, le=100)
    overall_stance: PortfolioStance = Field(default=PortfolioStance.MAINTAIN)
    ticker_recommendations: List[TickerRecommendation] = Field(default_factory=list)
    cash_recommendation: Optional[float] = Field(None, description="권고 현금 비중 (%)")
    evidence: List[str] = Field(default_factory=list, description="근거 데이터 목록")

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


class AgentCritique(BaseModel):
    from_agent: str
    to_agent: str
    critique: str = Field(..., min_length=20)
    revised_confidence: Optional[int] = Field(None, ge=0, le=100)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


# ── 토론 결과 모델 ────────────────────────────────────────────────

class DebateResult(BaseModel):
    phase1_reports: List[dict] = Field(default_factory=list)
    phase2_critiques: List[dict] = Field(default_factory=list)


class PortfolioChange(BaseModel):
    ticker: str
    name: str
    action: str  # "increase", "reduce", "add_new", "remove"
    from_weight: float
    to_weight: float
    reason: str
    supporters: List[str] = Field(default_factory=list)


class Verdict(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat())
    consensus_type: ConsensusType
    confidence_score: int = Field(..., ge=0, le=100)
    summary: str
    portfolio_changes: List[PortfolioChange] = Field(default_factory=list)
    cash_recommendation: Optional[dict] = None
    new_picks: List[dict] = Field(default_factory=list)
    risk_warnings: List[str] = Field(default_factory=list)
    debate_highlights: List[dict] = Field(default_factory=list)
    stance_votes: Dict[str, str] = Field(default_factory=dict)
    key_insights: List[str] = Field(default_factory=list)
    action_items: List[str] = Field(default_factory=list)

    def to_dict(self) -> dict:
        return self.model_dump(mode="json")


# ── 전체 보고서 모델 ──────────────────────────────────────────────

class FullReport(BaseModel):
    date: str
    generated_at: str
    user_id: str = "default"
    portfolio: dict
    domain_data: dict
    debate: DebateResult
    verdict: Verdict
