"""매크로 전문가 에이전트 — 거시경제, 금리, 환율, 지정학

매크로 에이전트는 시장 데이터에서 금리·경제지표·심리지표를 선별 추출하여
경기 사이클 판단 → 자산배분 의견을 도출한다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

from ..core.base_agent import BaseAgent
from ..core.schemas import AgentCritique, AgentReport

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "macro.md").read_text(encoding="utf-8")


class MacroAgent(BaseAgent):
    name = "매크로"
    role = "거시경제·금리·환율 전략가"
    avatar = "🌍"
    system_prompt = SYSTEM_PROMPT

    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        portfolio_text = self.format_portfolio_summary(portfolio)
        macro_summary = self._extract_macro_data(market_data)
        asset_mix = self._compute_asset_mix(portfolio)

        prompt = f"""[포트폴리오]
{portfolio_text}

[자산군 배분 현황]
{asset_mix}

[매크로 경제 데이터]
{macro_summary}

위 데이터를 기반으로 거시경제 분석 보고서를 작성하세요.

[분석 요구사항]
1. 경기 사이클 판단: 현재 어디에 있는가? (초기확장/중기확장/후기확장/정점/수축/저점)
   - ISM PMI, 고용, GDP 성장률 등의 근거를 제시
2. 금리·채권 환경: 정책금리 방향, 장단기 스프레드, 실질금리 평가
   - 주식/채권 상대적 매력도에 미치는 영향
3. 인플레이션: CPI 추세, 핵심 인플레이션 평가
4. 현재 매크로 환경에서 이 포트폴리오의 자산배분(주식/채권/현금/크립토)이 적절한지 판단
5. 자산군별 비중 조정 의견 (주식 비중 확대/축소, 채권 확대/축소, 현금 확대/축소)

반드시 아래 JSON으로만 응답:
{{
  "analysis": "300자 이상 거시경제 분석 (경기사이클 판단 + 근거)",
  "key_points": ["핵심1 (구체적 수치)", "핵심2", "핵심3"],
  "confidence_score": 68,
  "overall_stance": "MAINTAIN",
  "ticker_recommendations": [
    {{"ticker": "TLT", "name": "Treasury Bond ETF", "current_weight": 10, "recommended_weight": 15, "stance": "OVERWEIGHT", "reason": "금리 인하 사이클 수혜"}}
  ],
  "cash_recommendation": 15,
  "evidence": ["10Y-2Y 스프레드 +0.2% 정상화", "CPI 2.8% 하락 추세"]
}}

overall_stance: STRONG_OVERWEIGHT / OVERWEIGHT / MAINTAIN / UNDERWEIGHT / STRONG_UNDERWEIGHT"""

        result = self._call_llm(prompt)
        data = self.parse_json_response(result)
        return self._build_report(data, result)

    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        macro_summary = self._extract_macro_data(market_data)

        prompt = f"""매크로 전략가로서 아래 분석에 거시적 관점의 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
종합 판단: {other_report.overall_stance.value} (확신도: {other_report.confidence_score})
분석: {other_report.analysis[:400]}
핵심: {', '.join(other_report.key_points[:3])}

[현재 매크로 환경]
{macro_summary}

[반론 가이드]
- 상대방의 판단이 거시경제 환경(금리 방향, 경기사이클, 인플레이션)과 어떻게 충돌하는지 지적
- 개별 종목/섹터 판단이 매크로 맥락을 놓치고 있다면 구체적으로 반박
- 150~300자, 논리적으로"""

        result = self._call_llm(prompt, max_tokens=500)
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:500],
        )

    # ── 데이터 추출 헬퍼 ───────────────────────────────────────

    @staticmethod
    def _extract_macro_data(market_data: dict) -> str:
        """시장 데이터에서 매크로 관련 정보만 추출."""
        lines = []
        macro = market_data.get("macro", {})

        rates = macro.get("rates", {})
        if rates and not rates.get("error"):
            lines.append("[금리 환경]")
            if rates.get("fed_funds_rate"):
                lines.append(f"  연방기금금리: {rates['fed_funds_rate']}%")
            if rates.get("us_10y_yield"):
                lines.append(f"  미국 10년물: {rates['us_10y_yield']}%")
            if rates.get("us_2y_yield"):
                lines.append(f"  미국 2년물: {rates['us_2y_yield']}%")
            if rates.get("yield_spread_10y_2y") is not None:
                spread = rates["yield_spread_10y_2y"]
                status = "정상(양수)" if spread > 0 else "역전(음수) — 침체 신호"
                lines.append(f"  장단기 스프레드(10Y-2Y): {spread}% → {status}")

        econ = macro.get("economic", {})
        if econ and not econ.get("error"):
            lines.append("\n[경제 지표]")
            if econ.get("cpi_yoy"):
                lines.append(f"  CPI YoY: {econ['cpi_yoy']}%")
            if econ.get("unemployment"):
                lines.append(f"  실업률: {econ['unemployment']}%")
            if econ.get("gdp_growth"):
                lines.append(f"  GDP 성장률: {econ['gdp_growth']}%")
            if econ.get("vix"):
                vix = econ["vix"]
                vix_level = "안정" if vix < 20 else "경계" if vix < 30 else "불안"
                lines.append(f"  VIX: {vix} → {vix_level}")

        sentiment = macro.get("sentiment", {})
        if sentiment and not sentiment.get("error"):
            lines.append("\n[투자 심리]")
            if sentiment.get("fear_greed_score"):
                fg = sentiment["fear_greed_score"]
                level = "극단적 공포" if fg < 25 else "공포" if fg < 40 else "중립" if fg < 60 else "탐욕" if fg < 75 else "극단적 탐욕"
                lines.append(f"  Fear & Greed: {fg} → {level}")
            if sentiment.get("rating"):
                lines.append(f"  등급: {sentiment['rating']}")

        return "\n".join(lines) if lines else "매크로 데이터 없음"

    @staticmethod
    def _compute_asset_mix(portfolio: dict) -> str:
        """포트폴리오의 자산군별 비중 계산."""
        mix = {"주식": 0, "채권": 0, "크립토": 0, "기타": 0}
        for h in portfolio.get("holdings", []):
            market = h.get("market", "")
            sector = h.get("sector", "")
            w = h.get("weight", 0)
            if market == "Crypto" or sector == "Crypto":
                mix["크립토"] += w
            elif sector == "Bond" or "bond" in h.get("name", "").lower() or "treasury" in h.get("name", "").lower():
                mix["채권"] += w
            elif market in ("KRX", "NASDAQ", "NYSE"):
                mix["주식"] += w
            else:
                mix["기타"] += w

        cash = portfolio.get("cash_weight", 0)
        lines = [f"  주식: {mix['주식']}%", f"  채권: {mix['채권']}%",
                 f"  크립토: {mix['크립토']}%", f"  현금: {cash}%"]
        if mix["기타"]:
            lines.append(f"  기타: {mix['기타']}%")
        return "\n".join(lines)
