"""퀀트 전문가 에이전트 — 기술적 지표, 팩터 분석, 리스크 지표"""

from __future__ import annotations

from pathlib import Path

from ..core.base_agent import BaseAgent
from ..core.schemas import AgentCritique, AgentReport

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "quant.md").read_text(encoding="utf-8")


class QuantAgent(BaseAgent):
    name = "퀀트"
    role = "기술적 지표·팩터·리스크 분석가"
    avatar = "🔢"
    system_prompt = SYSTEM_PROMPT

    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        portfolio_text = self.format_portfolio_summary(portfolio)
        market_text = self.format_market_data(market_data)

        prompt = f"""[포트폴리오]
{portfolio_text}

[시장 데이터]
{market_text}

위 데이터를 기반으로 기술적·팩터·리스크 분석 보고서를 작성하세요.
RSI, MACD, 이동평균, 변동성, Sharpe ratio 등 정량적 지표를 구체적 수치와 함께 분석하세요.
포트폴리오 내 각 종목에 대해 비중 조정 의견을 제시하세요.

반드시 아래 JSON으로만 응답:
{{
  "analysis": "300자 이상 정량 분석 (구체적 수치 포함)",
  "key_points": ["핵심1 (수치 포함)", "핵심2", "핵심3"],
  "confidence_score": 75,
  "overall_stance": "MAINTAIN",
  "ticker_recommendations": [
    {{"ticker": "AAPL", "name": "Apple", "current_weight": 20, "recommended_weight": 15, "stance": "UNDERWEIGHT", "reason": "RSI 과매수 구간"}}
  ],
  "cash_recommendation": 15,
  "evidence": ["RSI 72.5 → 과매수", "Sharpe 0.8 → 평균 이하"]
}}

overall_stance: STRONG_OVERWEIGHT / OVERWEIGHT / MAINTAIN / UNDERWEIGHT / STRONG_UNDERWEIGHT"""

        result = self._call_llm(prompt)
        data = self.parse_json_response(result)
        return self._build_report(data, result)

    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        prompt = f"""퀀트 분석가로서 아래 분석에 데이터 기반 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
종합 판단: {other_report.overall_stance.value} (확신도: {other_report.confidence_score})
분석: {other_report.analysis[:400]}
핵심: {', '.join(other_report.key_points[:3])}

[반론 가이드]
- 상대방 주장의 데이터적 허점을 구체적 수치로 반박하세요
- 정성적 판단에 대해 정량적 반증을 제시하세요
- 150~300자, 논리적으로"""

        result = self._call_llm(prompt, max_tokens=500)
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:500],
        )
