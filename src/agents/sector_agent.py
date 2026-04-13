"""섹터 전문가 에이전트 — 섹터 로테이션, 업종 분석, 편중도 진단

섹터 에이전트는 포트폴리오의 섹터 분포를 계산하고,
시장 데이터에서 종목별 성과를 비교하여 섹터 수준의 의견을 제시한다.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

from ..core.base_agent import BaseAgent
from ..core.schemas import AgentCritique, AgentReport

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "sector.md").read_text(encoding="utf-8")


class SectorAgent(BaseAgent):
    name = "섹터"
    role = "섹터 로테이션·업종 분석가"
    avatar = "🏭"
    system_prompt = SYSTEM_PROMPT

    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        portfolio_text = self.format_portfolio_summary(portfolio)
        sector_breakdown = self._compute_sector_breakdown(portfolio)
        stock_performance = self._extract_stock_performance(market_data)

        prompt = f"""[포트폴리오]
{portfolio_text}

[섹터별 비중 분석]
{sector_breakdown}

[종목별 시장 성과]
{stock_performance}

위 데이터를 기반으로 섹터 분석 보고서를 작성하세요.

[분석 요구사항]
1. 섹터 편중도 진단: 과도한 집중 섹터가 있는가? (40% 이상이면 경고)
2. 누락된 방어적 섹터(헬스케어, 유틸리티, 필수소비재)가 있는가?
3. 섹터 로테이션 판단: 현재 환경에서 유망/위험 섹터
4. 종목별 상대강도: 동일 섹터 내 각 종목의 상대적 위치
5. 비중 조정 제안: 섹터 확대/축소 + 신규 섹터 추가 종목 예시

반드시 아래 JSON으로만 응답:
{{
  "analysis": "300자 이상 섹터 분석 (편중도 + 로테이션 판단)",
  "key_points": ["핵심1 (섹터명+비중)", "핵심2", "핵심3"],
  "confidence_score": 72,
  "overall_stance": "UNDERWEIGHT",
  "ticker_recommendations": [
    {{"ticker": "XLV", "name": "Healthcare ETF", "current_weight": 0, "recommended_weight": 5, "stance": "OVERWEIGHT", "reason": "방어적 섹터 분산"}}
  ],
  "cash_recommendation": null,
  "evidence": ["Technology 65% 과편중", "Healthcare 0% 부재"]
}}

overall_stance: STRONG_OVERWEIGHT / OVERWEIGHT / MAINTAIN / UNDERWEIGHT / STRONG_UNDERWEIGHT"""

        result = self._call_llm(prompt)
        data = self.parse_json_response(result)
        return self._build_report(data, result)

    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        sector_breakdown = self._compute_sector_breakdown(portfolio)

        prompt = f"""섹터 분석가로서 아래 분석에 업종/산업 관점의 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
종합 판단: {other_report.overall_stance.value} (확신도: {other_report.confidence_score})
분석: {other_report.analysis[:400]}
핵심: {', '.join(other_report.key_points[:3])}

[현재 포트폴리오 섹터 분포]
{sector_breakdown}

[반론 가이드]
- 상대방의 판단이 섹터 수준에서 어떤 차이를 보이는지 구체적 예시로 지적
- 거시적 판단이라도 개별 섹터의 펀더멘탈과 다를 수 있음을 반박
- 150~300자, 논리적으로"""

        result = self._call_llm(prompt, max_tokens=500)
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:500],
        )

    @staticmethod
    def _compute_sector_breakdown(portfolio: dict) -> str:
        sectors: Dict[str, float] = defaultdict(float)
        sector_tickers: Dict[str, List[str]] = defaultdict(list)
        for h in portfolio.get("holdings", []):
            sector = h.get("sector", "Unknown")
            weight = h.get("weight", 0)
            sectors[sector] += weight
            sector_tickers[sector].append(f"{h['ticker']}({weight}%)")

        lines = []
        for sector, weight in sorted(sectors.items(), key=lambda x: -x[1]):
            warning = " ⚠️ 과편중" if weight >= 40 else ""
            tickers = ", ".join(sector_tickers[sector])
            lines.append(f"  {sector}: {weight}%{warning} — {tickers}")

        essential = {"Healthcare", "Energy", "Utilities"}
        missing = essential - set(sectors.keys())
        if missing:
            lines.append(f"\n  [누락 섹터] {', '.join(missing)}")
        return "\n".join(lines)

    @staticmethod
    def _extract_stock_performance(market_data: dict) -> str:
        lines = []
        stocks = market_data.get("stocks", {})
        if isinstance(stocks, dict):
            for ticker, data in stocks.items():
                if isinstance(data, dict) and not data.get("error"):
                    change = data.get("change_pct", "?")
                    rsi = data.get("rsi_14", "N/A")
                    lines.append(f"  {ticker}: 변동 {change}%, RSI {rsi}")
        return "\n".join(lines) if lines else "종목별 성과 데이터 없음"
