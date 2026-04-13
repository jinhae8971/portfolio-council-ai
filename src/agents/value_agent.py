"""가치투자자 에이전트 — DCF, 밸류에이션, 안전마진

가치투자자 에이전트는 종목별 평균 매입가, 시장 가격, 기본 밸류에이션 데이터를
종합하여 내재가치 대비 현재가를 평가하고 안전마진을 산출한다.
"""

from __future__ import annotations

from pathlib import Path

from ..core.base_agent import BaseAgent
from ..core.schemas import AgentCritique, AgentReport

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "value.md").read_text(encoding="utf-8")


class ValueAgent(BaseAgent):
    name = "가치투자자"
    role = "펀더멘탈·밸류에이션 분석가"
    avatar = "📚"
    system_prompt = SYSTEM_PROMPT

    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        portfolio_text = self.format_portfolio_summary(portfolio)
        valuation_data = self._build_valuation_context(portfolio, market_data)

        prompt = f"""[포트폴리오]
{portfolio_text}

[밸류에이션 데이터]
{valuation_data}

위 데이터를 기반으로 가치투자 분석 보고서를 작성하세요.

[분석 요구사항]
1. 종목별 밸류에이션 평가
   - 현재가 대비 평균 매입가 수익률
   - 가용한 밸류에이션 지표(PER, PBR 등) 기반 고평가/저평가 판단
   - 업종 평균 대비 상대적 위치
2. 안전마진(Margin of Safety) 추정
   - 각 종목의 내재가치를 개략적으로 추정
   - 안전마진(%) = (내재가치 - 현재가) / 내재가치 × 100
   - 20% 이상: 매력적, 10-20%: 적정, 0% 이하: 고평가
3. 포트폴리오 전체 밸류에이션
   - 전체적으로 가치 대비 비싼가 / 싼가?
   - 비중 확대할 저평가 종목과 축소할 고평가 종목
4. 배당 관점 (해당 종목)
   - 배당 수익률, 배당 성장 가능성
5. 장기 경쟁력(경제적 해자)
   - 브랜드, 네트워크 효과, 전환비용, 원가우위

반드시 아래 JSON으로만 응답:
{{
  "analysis": "300자 이상 밸류에이션 분석 (종목별 내재가치+안전마진 수치)",
  "key_points": ["핵심1 (PER/PBR 수치)", "핵심2", "핵심3"],
  "confidence_score": 70,
  "overall_stance": "MAINTAIN",
  "ticker_recommendations": [
    {{"ticker": "005930.KS", "name": "삼성전자", "current_weight": 25, "recommended_weight": 28, "stance": "OVERWEIGHT", "reason": "PBR 0.95 저평가, 안전마진 18%"}}
  ],
  "cash_recommendation": null,
  "evidence": ["삼성전자 PBR 0.95 → 자산가치 이하", "NVDA PER 65 → 업종평균 25 대비 160% 프리미엄"]
}}

overall_stance: STRONG_OVERWEIGHT / OVERWEIGHT / MAINTAIN / UNDERWEIGHT / STRONG_UNDERWEIGHT
"비싸다" 대신 "PER 65.3으로 업종 평균(25.1) 대비 160% 프리미엄"처럼 구체적 수치를 사용하세요."""

        result = self._call_llm(prompt)
        data = self.parse_json_response(result)
        return self._build_report(data, result)

    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        prompt = f"""가치투자자로서 아래 분석에 장기 펀더멘탈 관점의 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
종합 판단: {other_report.overall_stance.value} (확신도: {other_report.confidence_score})
분석: {other_report.analysis[:400]}
핵심: {', '.join(other_report.key_points[:3])}

[반론 가이드]
- 단기 기술적 시그널(RSI, MACD)이나 시장 심리에 과도하게 의존하고 있다면 지적
- 내재가치와 안전마진이 왜 단기 변동보다 중요한지 근거를 들어 반박
- "가격은 단기적으로 투표 기계, 장기적으로 저울" — 그레이엄 관점
- 150~300자, 논리적으로"""

        result = self._call_llm(prompt, max_tokens=500)
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:500],
        )

    @staticmethod
    def _build_valuation_context(portfolio: dict, market_data: dict) -> str:
        """각 종목의 매입가, 현재가, 수익률을 정리."""
        lines = []
        stocks = market_data.get("stocks", {})
        crypto = market_data.get("crypto", {}).get("coins", {})

        for h in portfolio.get("holdings", []):
            ticker = h["ticker"]
            name = h.get("name", ticker)
            avg_price = h.get("avg_price")

            # 현재가 가져오기
            current_price = None
            if ticker in stocks and isinstance(stocks[ticker], dict):
                current_price = stocks[ticker].get("price")
            elif ticker in crypto and isinstance(crypto[ticker], dict):
                current_price = crypto[ticker].get("price_usd")

            parts = [f"{ticker} ({name}): 비중 {h.get('weight', 0)}%"]

            if avg_price:
                parts.append(f"평단가 {avg_price:,}")
            if current_price:
                parts.append(f"현재가 {current_price:,}")
            if avg_price and current_price and avg_price > 0:
                ret = (current_price / avg_price - 1) * 100
                parts.append(f"수익률 {ret:+.1f}%")

            # 기술적 데이터에서 추가 정보
            stock_data = stocks.get(ticker, {})
            if isinstance(stock_data, dict):
                vol = stock_data.get("volatility_annual")
                if vol:
                    parts.append(f"변동성 {vol}%")

            lines.append("  " + " / ".join(parts))

        # 크립토는 별도 표기
        if not lines:
            lines.append("  밸류에이션 데이터 없음")

        return "\n".join(lines)
