"""사이클 전문가 에이전트 — 시장 사이클, 기술적 타이밍, 투자 심리

사이클 에이전트는 시장 심리 지표(VIX, Fear & Greed)와 기술적 데이터를 종합하여
Wyckoff 사이클 위치를 판단하고 방어적/공격적 포지셔닝을 제안한다.
"""

from __future__ import annotations

from pathlib import Path

from ..core.base_agent import BaseAgent
from ..core.schemas import AgentCritique, AgentReport

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "cycle.md").read_text(encoding="utf-8")


class CycleAgent(BaseAgent):
    name = "사이클"
    role = "시장 사이클·타이밍 분석가"
    avatar = "🔄"
    system_prompt = SYSTEM_PROMPT

    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        portfolio_text = self.format_portfolio_summary(portfolio)
        sentiment_data = self._extract_sentiment(market_data)
        technical_data = self._extract_technicals(market_data)

        prompt = f"""[포트폴리오]
{portfolio_text}

[투자 심리 지표]
{sentiment_data}

[종목별 기술적 지표]
{technical_data}

위 데이터를 기반으로 시장 사이클 분석 보고서를 작성하세요.

[분석 요구사항]
1. Wyckoff 시장 사이클 위치 판단
   - 축적(Accumulation) / 상승(Markup) / 분배(Distribution) / 하락(Markdown)
   - 판단 근거: VIX 수준, Fear & Greed, 종목 RSI 분포, 거래량 패턴
2. 투자 심리 분석
   - Fear & Greed Index 해석 (25 이하 극단적 공포, 75 이상 극단적 탐욕)
   - VIX 수준 해석 (20 이하 안정, 30 이상 불안, 40 이상 패닉)
3. 포지셔닝 제안
   - 공격적(사이클 초기): 주식 비중 확대, 현금 최소화
   - 중립적(사이클 중반): 균형 유지
   - 방어적(사이클 후반/하락): 현금 비중 확대, 방어주 전환
4. 현금 비중 구체적 권고

반드시 아래 JSON으로만 응답:
{{
  "analysis": "300자 이상 사이클 분석 (사이클 위치 + 심리 해석)",
  "key_points": ["핵심1 (지표 수치)", "핵심2", "핵심3"],
  "confidence_score": 65,
  "overall_stance": "UNDERWEIGHT",
  "ticker_recommendations": [],
  "cash_recommendation": 20,
  "evidence": ["VIX 22.5 → 경계 구간", "Fear & Greed 35 → 공포"]
}}

overall_stance: STRONG_OVERWEIGHT / OVERWEIGHT / MAINTAIN / UNDERWEIGHT / STRONG_UNDERWEIGHT"""

        result = self._call_llm(prompt)
        data = self.parse_json_response(result)
        return self._build_report(data, result)

    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        sentiment_data = self._extract_sentiment(market_data)

        prompt = f"""사이클 분석가로서 아래 분석에 타이밍·심리 관점의 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
종합 판단: {other_report.overall_stance.value} (확신도: {other_report.confidence_score})
분석: {other_report.analysis[:400]}
핵심: {', '.join(other_report.key_points[:3])}

[현재 투자 심리]
{sentiment_data}

[반론 가이드]
- 현재 시장 사이클 위치와 투자 심리가 상대방 판단과 어떻게 충돌하는지 지적
- 타이밍 관점에서 지금 해당 포지션을 잡는 것이 적절한지 비판
- 150~300자, 논리적으로"""

        result = self._call_llm(prompt, max_tokens=500)
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:500],
        )

    @staticmethod
    def _extract_sentiment(market_data: dict) -> str:
        lines = []
        macro = market_data.get("macro", {})

        econ = macro.get("economic", {})
        if econ.get("vix"):
            vix = econ["vix"]
            level = "안정" if vix < 20 else "경계" if vix < 30 else "불안" if vix < 40 else "패닉"
            lines.append(f"VIX: {vix} → {level}")

        sentiment = macro.get("sentiment", {})
        if sentiment.get("fear_greed_score"):
            fg = sentiment["fear_greed_score"]
            level = "극단적 공포" if fg < 25 else "공포" if fg < 40 else "중립" if fg < 60 else "탐욕" if fg < 75 else "극단적 탐욕"
            lines.append(f"Fear & Greed: {fg} → {level}")
            if sentiment.get("rating"):
                lines.append(f"등급: {sentiment['rating']}")

        return "\n".join(lines) if lines else "심리 지표 데이터 없음"

    @staticmethod
    def _extract_technicals(market_data: dict) -> str:
        lines = []
        stocks = market_data.get("stocks", {})
        if isinstance(stocks, dict):
            overbought = []
            oversold = []
            for ticker, data in stocks.items():
                if isinstance(data, dict) and not data.get("error"):
                    rsi = data.get("rsi_14")
                    sma20 = data.get("sma_20")
                    price = data.get("price")
                    parts = [f"{ticker}:"]
                    if rsi:
                        parts.append(f"RSI {rsi}")
                        if rsi > 70: overbought.append(ticker)
                        elif rsi < 30: oversold.append(ticker)
                    if price and sma20:
                        pct = round((price / sma20 - 1) * 100, 1)
                        parts.append(f"SMA20 대비 {'+' if pct > 0 else ''}{pct}%")
                    lines.append("  " + " / ".join(parts))

            if overbought:
                lines.append(f"\n  과매수 종목: {', '.join(overbought)}")
            if oversold:
                lines.append(f"  과매도 종목: {', '.join(oversold)}")

        return "\n".join(lines) if lines else "기술적 지표 없음"
