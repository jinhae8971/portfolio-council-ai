"""E2E 통합 테스트 — 샘플 데이터로 전체 파이프라인 검증

실제 LLM API 없이 FakeLLM으로 전체 플로우를 검증한다.
"""
import json
import pytest
import tempfile
from pathlib import Path

from src.core.debate_engine import DebateEngine
from src.core.moderator import Moderator
from src.core.schemas import DebateResult, PortfolioStance
from src.infrastructure.storage.json_storage import JSONFileStorage


# ── Fake LLM Provider ─────────────────────────────────────────

class FakeLLMProvider:
    """E2E 테스트용 가짜 LLM. 에이전트 이름에 따라 다른 응답 반환."""

    AGENT_RESPONSES = {
        "퀀트": '{"analysis": "RSI 14일 기준 NVDA 72.5로 과매수 직전. 포트폴리오 Sharpe ratio 0.92, 연환산 변동성 22.1%. 기술주 상관계수 0.78로 집중 리스크 존재. AAPL RSI 58.3 중립.", "key_points": ["NVDA RSI 72.5 과매수", "Sharpe 0.92 양호", "기술주 상관 0.78"], "confidence_score": 75, "overall_stance": "UNDERWEIGHT", "evidence": ["RSI 72.5", "상관 0.78"]}',
        "매크로": '{"analysis": "미 연준 금리 인하 사이클 진입. 10Y-2Y 스프레드 +0.2%로 정상화. CPI 2.8% YoY 하락 추세. 경기 후기확장 판단. 채권 비중 확대 유리한 환경으로 보입니다.", "key_points": ["경기 후기확장", "금리 인하 사이클", "채권 확대 유리"], "confidence_score": 68, "overall_stance": "MAINTAIN", "evidence": ["10Y-2Y +0.2%", "CPI 2.8%"]}',
        "섹터": '{"analysis": "기술섹터 포트폴리오 비중 65%로 과도한 편중. 헬스케어, 에너지 섹터 부재. AI 반도체 상대강도 상위이나 방어적 섹터 추가가 필요합니다. 경기 후반 대비 필요.", "key_points": ["기술 65% 편중", "헬스케어 부재", "방어 섹터 추가"], "confidence_score": 72, "overall_stance": "UNDERWEIGHT", "evidence": ["기술 65%"]}',
        "사이클": '{"analysis": "S&P500 분배 국면 진입 신호 감지. Fear & Greed 35로 공포 구간. VIX 22.5 경계 수준. 방어적 포지셔닝 및 현금 비중 확대를 권고합니다. 리스크 관리가 우선입니다.", "key_points": ["분배 국면 진입", "F&G 35 공포", "방어적 포지셔닝"], "confidence_score": 65, "overall_stance": "UNDERWEIGHT", "evidence": ["VIX 22.5", "F&G 35"]}',
        "크립토": '{"analysis": "BTC 반감기 후 확장 국면 진행 중. 도미넌스 52.3% 안정적. 총 시가총액 3.2조 달러. 현재 크립토 비중 15%는 적정 수준이며 유지 권고합니다.", "key_points": ["BTC 반감기 후 확장", "도미넌스 52.3%", "15% 적정"], "confidence_score": 60, "overall_stance": "MAINTAIN", "evidence": ["도미넌스 52.3%"]}',
        "가치투자자": '{"analysis": "삼성전자 PBR 0.95 저평가, 안전마진 18%. NVDA PER 65로 업종평균 25 대비 160% 프리미엄. GOOGL PER 22 합리적. 삼성전자 비중 확대와 NVDA 축소를 권고합니다.", "key_points": ["삼성전자 안전마진 18%", "NVDA 고평가", "GOOGL 합리적"], "confidence_score": 70, "overall_stance": "MAINTAIN", "evidence": ["PBR 0.95", "PER 65"]}',
    }

    MODERATOR_RESPONSE = json.dumps({
        "consensus_type": "majority_view",
        "confidence_score": 68,
        "summary": "6명 에이전트 중 4명이 기술주 편중 리스크와 방어적 포지셔닝 필요성에 동의. NVDA 비중 축소, 현금 확대, 방어 섹터 추가 권고.",
        "portfolio_changes": [
            {"ticker": "NVDA", "name": "NVIDIA", "action": "reduce", "from_weight": 15, "to_weight": 10, "reason": "고평가+과매수", "supporters": ["퀀트", "가치투자자"]}
        ],
        "cash_recommendation": {"current": 10, "target": 15, "reason": "분배 국면"},
        "risk_warnings": ["기술주 편중", "VIX 상승"],
        "key_insights": ["NVDA 이중 경고", "삼성전자 기회"],
        "action_items": ["NVDA 5% 축소", "현금 5% 확대"],
        "debate_highlights": []
    })

    def complete(self, system: str, messages: list, max_tokens: int = 2048) -> str:
        user_msg = messages[0]["content"] if messages else ""
        # 에이전트 분석 응답
        for agent_name, response in self.AGENT_RESPONSES.items():
            if agent_name in system or agent_name in user_msg:
                return response
        # 반론 응답
        if "반론" in user_msg or "critique" in user_msg.lower():
            return "상대방의 분석은 단기 지표에 과도하게 의존하고 있으며, 장기 펀더멘탈 관점이 부족합니다."
        # Moderator 응답
        if "의장" in system or "Moderator" in system or "종합" in user_msg:
            return self.MODERATOR_RESPONSE
        return '{"analysis": "기본 분석입니다. " + "x" * 50, "key_points": ["기본"], "confidence_score": 50, "overall_stance": "MAINTAIN"}'


# ── Fixtures ──────────────────────────────────────────────────

@pytest.fixture
def sample_portfolio():
    return json.loads(
        (Path(__file__).parent.parent / "fixtures" / "sample_portfolio.json").read_text()
    )

@pytest.fixture
def sample_market_data():
    return json.loads(
        (Path(__file__).parent.parent / "fixtures" / "sample_market_data.json").read_text()
    )

@pytest.fixture
def fake_llm():
    return FakeLLMProvider()


# ── E2E 테스트 ────────────────────────────────────────────────

def test_full_pipeline_e2e(sample_portfolio, sample_market_data, fake_llm):
    """전체 파이프라인 E2E: 에이전트 생성 → 토론 → Moderator → 저장."""
    from src.agents.quant_agent import QuantAgent
    from src.agents.macro_agent import MacroAgent
    from src.agents.sector_agent import SectorAgent
    from src.agents.cycle_agent import CycleAgent
    from src.agents.crypto_agent import CryptoAgent
    from src.agents.value_agent import ValueAgent

    # 1. 에이전트 생성
    agents = [
        QuantAgent(fake_llm), MacroAgent(fake_llm), SectorAgent(fake_llm),
        CycleAgent(fake_llm), CryptoAgent(fake_llm), ValueAgent(fake_llm),
    ]

    # 2. 토론 실행
    engine = DebateEngine(agents)
    debate_result = engine.run(sample_portfolio, sample_market_data)

    assert len(debate_result.phase1_reports) == 6
    assert len(debate_result.phase2_critiques) == 6

    # 모든 에이전트가 유효한 stance를 반환했는지
    for report in debate_result.phase1_reports:
        assert report["confidence_score"] >= 0
        assert report["overall_stance"] in [s.value for s in PortfolioStance]

    # 3. Moderator 종합
    moderator = Moderator(fake_llm)
    verdict = moderator.synthesize(debate_result, sample_portfolio, sample_market_data)

    assert verdict.confidence_score > 0
    assert verdict.consensus_type is not None
    assert len(verdict.summary) > 0

    # 4. 저장
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JSONFileStorage(base_dir=tmpdir)
        report = {
            "date": "2026-04-13",
            "generated_at": "2026-04-13T10:00:00",
            "user_id": "test",
            "portfolio": sample_portfolio,
            "domain_data": sample_market_data,
            "debate": debate_result.model_dump(mode="json"),
            "verdict": verdict.to_dict(),
        }

        report_id = storage.save_report(report, "test")
        assert report_id is not None

        loaded = storage.load_report(report_id)
        assert loaded is not None
        assert loaded["date"] == "2026-04-13"
        assert loaded["verdict"]["confidence_score"] == verdict.confidence_score


def test_pipeline_with_agent_failure(sample_portfolio, sample_market_data):
    """에이전트 1개 실패해도 파이프라인은 계속 동작."""
    class FailingLLM:
        call_count = 0
        def complete(self, system, messages, max_tokens=2048):
            self.call_count += 1
            if self.call_count == 1:  # 첫 번째 호출만 실패
                raise RuntimeError("LLM 장애 시뮬레이션")
            return '{"analysis": "정상 분석입니다. 테스트용 더미 데이터 분석 결과입니다.", "key_points": ["정상"], "confidence_score": 60, "overall_stance": "MAINTAIN"}'

    from src.agents.quant_agent import QuantAgent
    from src.agents.macro_agent import MacroAgent

    agents = [QuantAgent(FailingLLM()), MacroAgent(FakeLLMProvider())]
    engine = DebateEngine(agents, critique_pairs=[(0, 1), (1, 0)])
    result = engine.run(sample_portfolio, sample_market_data)

    # 실패한 에이전트는 confidence=0으로 처리
    assert result.phase1_reports[0]["confidence_score"] == 0
    # 정상 에이전트는 유효한 결과
    assert result.phase1_reports[1]["confidence_score"] > 0


def test_json_storage_roundtrip():
    """저장소 라운드트립 테스트."""
    with tempfile.TemporaryDirectory() as tmpdir:
        storage = JSONFileStorage(base_dir=tmpdir)

        report = {
            "date": "2026-04-13",
            "verdict": {"consensus_type": "majority_view", "confidence_score": 72},
        }

        rid = storage.save_report(report, "user1")
        loaded = storage.load_report(rid)
        assert loaded["verdict"]["confidence_score"] == 72

        reports = storage.list_reports("user1")
        assert len(reports) == 1
        assert reports[0]["date"] == "2026-04-13"


def test_debate_result_serialization(sample_portfolio, sample_market_data, fake_llm):
    """DebateResult가 JSON 직렬화 가능한지."""
    from src.agents.quant_agent import QuantAgent
    from src.agents.macro_agent import MacroAgent

    agents = [QuantAgent(fake_llm), MacroAgent(fake_llm)]
    engine = DebateEngine(agents, critique_pairs=[(0, 1), (1, 0)])
    result = engine.run(sample_portfolio, sample_market_data)

    # model_dump가 정상 동작하는지
    serialized = result.model_dump(mode="json")
    assert isinstance(serialized, dict)
    assert "phase1_reports" in serialized

    # JSON 문자열로 변환 가능한지
    json_str = json.dumps(serialized, ensure_ascii=False)
    assert len(json_str) > 100
