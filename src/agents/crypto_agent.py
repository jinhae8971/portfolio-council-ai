"""암호화폐 전문가 에이전트 — 온체인, DeFi, 크립토 사이클

크립토 에이전트는 CoinGecko 데이터에서 코인별 성과와 글로벌 메트릭을 추출하여
BTC 사이클 위치 판단 → 크립토 배분 의견을 도출한다.
"""

from __future__ import annotations

from pathlib import Path

from ..core.base_agent import BaseAgent
from ..core.schemas import AgentCritique, AgentReport

SYSTEM_PROMPT = (Path(__file__).parent.parent / "prompts" / "crypto.md").read_text(encoding="utf-8")


class CryptoAgent(BaseAgent):
    name = "크립토"
    role = "암호화폐·DeFi·온체인 분석가"
    avatar = "₿"
    system_prompt = SYSTEM_PROMPT

    def analyze(self, portfolio: dict, market_data: dict, user_id: str = "default") -> AgentReport:
        portfolio_text = self.format_portfolio_summary(portfolio)
        crypto_data = self._extract_crypto_data(market_data)
        crypto_allocation = self._compute_crypto_allocation(portfolio)

        prompt = f"""[포트폴리오]
{portfolio_text}

[크립토 자산 배분]
{crypto_allocation}

[암호화폐 시장 데이터]
{crypto_data}

위 데이터를 기반으로 암호화폐 분석 보고서를 작성하세요.

[분석 요구사항]
1. BTC 사이클 분석
   - BTC 반감기(2024년 4월) 이후 현재 사이클 위치 (축적/상승/과열/하락)
   - 이전 사이클 대비 현재 진행 속도
2. 시장 구조
   - BTC 도미넌스 해석 (60% 이상 BTC 집중, 40% 이하 알트 시즌)
   - 총 시가총액 추세, 주요 코인 성과
3. 포트폴리오 내 크립토 배분
   - 전체 포트폴리오 대비 크립토 비중이 적절한지
   - BTC/ETH/알트코인 내부 배분 의견
   - 포트폴리오 제약 조건(max_crypto_weight) 준수 여부
4. 전통 자산 대비 매력도
   - 금리 환경에서 크립토의 상대적 위치

반드시 아래 JSON으로만 응답:
{{
  "analysis": "300자 이상 크립토 분석 (BTC 사이클 + 배분 의견)",
  "key_points": ["핵심1 (수치)", "핵심2", "핵심3"],
  "confidence_score": 60,
  "overall_stance": "MAINTAIN",
  "ticker_recommendations": [
    {{"ticker": "ETH", "name": "Ethereum", "current_weight": 5, "recommended_weight": 7, "stance": "OVERWEIGHT", "reason": "ETH/BTC 비율 저점 근접"}}
  ],
  "cash_recommendation": null,
  "evidence": ["BTC 도미넌스 52% → BTC 선호", "반감기 후 12개월 확장 국면"]
}}

overall_stance: STRONG_OVERWEIGHT / OVERWEIGHT / MAINTAIN / UNDERWEIGHT / STRONG_UNDERWEIGHT"""

        result = self._call_llm(prompt)
        data = self.parse_json_response(result)
        return self._build_report(data, result)

    def critique(self, other_report: AgentReport, portfolio: dict,
                 market_data: dict, user_id: str = "default") -> AgentCritique:
        crypto_data = self._extract_crypto_data(market_data)

        prompt = f"""크립토 분석가로서 아래 분석에 대안자산·탈중앙 관점의 반론을 제시하세요.

[{other_report.agent_name} — {other_report.role}의 분석]
종합 판단: {other_report.overall_stance.value} (확신도: {other_report.confidence_score})
분석: {other_report.analysis[:400]}
핵심: {', '.join(other_report.key_points[:3])}

[현재 크립토 시장]
{crypto_data}

[반론 가이드]
- 전통 금융 지표(RSI, PER 등)가 24/7 크립토 시장에 적용되지 않는 사례를 제시
- BTC 반감기 사이클의 독자적 동학이 전통 시장과 다름을 지적
- 150~300자, 논리적으로"""

        result = self._call_llm(prompt, max_tokens=500)
        return AgentCritique(
            from_agent=self.name,
            to_agent=other_report.agent_name,
            critique=result.strip()[:500],
        )

    @staticmethod
    def _extract_crypto_data(market_data: dict) -> str:
        lines = []
        crypto = market_data.get("crypto", {})

        # 글로벌 메트릭
        glob = crypto.get("global", {})
        if glob and not glob.get("error"):
            lines.append("[글로벌 크립토 시장]")
            if glob.get("total_market_cap_usd"):
                cap_t = glob["total_market_cap_usd"] / 1e12
                lines.append(f"  총 시가총액: ${cap_t:.1f}T")
            if glob.get("btc_dominance"):
                dom = glob["btc_dominance"]
                phase = "BTC 집중" if dom > 55 else "균형" if dom > 45 else "알트 시즌"
                lines.append(f"  BTC 도미넌스: {dom}% → {phase}")
            if glob.get("eth_dominance"):
                lines.append(f"  ETH 도미넌스: {glob['eth_dominance']}%")

        # 코인별 데이터
        coins = crypto.get("coins", {})
        if coins:
            lines.append("\n[코인별 성과]")
            for ticker, data in coins.items():
                if isinstance(data, dict):
                    price = data.get("price_usd", "?")
                    d1 = data.get("change_24h", "?")
                    d7 = data.get("change_7d", "?")
                    d30 = data.get("change_30d", "?")
                    rank = data.get("market_cap_rank", "?")
                    ath_pct = data.get("ath_change_pct", "?")
                    lines.append(f"  {ticker}: ${price:,} / 24h {d1}% / 7d {d7}% / 30d {d30}% / ATH대비 {ath_pct}% / 순위 #{rank}")

        return "\n".join(lines) if lines else "크립토 데이터 없음"

    @staticmethod
    def _compute_crypto_allocation(portfolio: dict) -> str:
        crypto_holdings = []
        total_crypto = 0
        for h in portfolio.get("holdings", []):
            if h.get("market") == "Crypto" or h.get("sector") == "Crypto":
                crypto_holdings.append(h)
                total_crypto += h.get("weight", 0)

        max_crypto = portfolio.get("constraints", {}).get("max_crypto_weight", 15)
        status = "제약 이내" if total_crypto <= max_crypto else f"⚠️ 제약({max_crypto}%) 초과"

        lines = [f"크립토 총 비중: {total_crypto}% (제약 {max_crypto}%) → {status}"]
        for h in crypto_holdings:
            lines.append(f"  {h['ticker']} ({h.get('name', '')}): {h['weight']}%")

        if not crypto_holdings:
            lines.append("  크립토 보유 없음")

        return "\n".join(lines)
