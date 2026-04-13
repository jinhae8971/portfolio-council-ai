#!/usr/bin/env python3
"""프롬프트 A/B 테스트 프레임워크

동일한 포트폴리오+시장 데이터에 대해 프롬프트 변형을 적용하고,
분석 품질을 자동 비교하는 도구.

Usage:
    python scripts/prompt_ab_test.py --agent quant --rounds 3
    python scripts/prompt_ab_test.py --agent macro --variant-file prompts/macro_v2.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.core.base_agent import BaseAgent
from src.core.schemas import AgentReport
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)

# ── 품질 평가 기준 ─────────────────────────────────────────────

def evaluate_report_quality(report: AgentReport) -> Dict[str, float]:
    """에이전트 보고서의 품질을 0-100 점수로 평가.

    평가 기준:
    1. 분석 길이 (300자 이상 목표)
    2. 핵심 포인트 수 (3개 이상 목표)
    3. 근거 데이터 수 (2개 이상 목표)
    4. 확신도 합리성 (극단값 패널티)
    5. 종목 추천 존재 여부
    6. 수치 포함 여부 (정량적 분석)
    """
    scores = {}

    # 1. 분석 길이 (max 25점)
    analysis_len = len(report.analysis)
    scores["analysis_length"] = min(25, analysis_len / 300 * 25)

    # 2. 핵심 포인트 (max 15점)
    kp_count = len(report.key_points)
    scores["key_points"] = min(15, kp_count / 3 * 15)

    # 3. 근거 데이터 (max 15점)
    evidence_count = len(report.evidence)
    scores["evidence"] = min(15, evidence_count / 2 * 15)

    # 4. 확신도 합리성 (max 15점)
    conf = report.confidence_score
    if 30 <= conf <= 85:
        scores["confidence_rationality"] = 15
    elif 20 <= conf <= 90:
        scores["confidence_rationality"] = 10
    else:
        scores["confidence_rationality"] = 5  # 극단값 패널티

    # 5. 종목 추천 (max 15점)
    recs = report.ticker_recommendations
    if isinstance(recs, list) and len(recs) > 0:
        scores["has_recommendations"] = 15
    elif report.cash_recommendation is not None:
        scores["has_recommendations"] = 10
    else:
        scores["has_recommendations"] = 0

    # 6. 수치 포함 (max 15점) — 분석 텍스트에 숫자가 있는지
    import re
    numbers = re.findall(r'\d+\.?\d*%?', report.analysis)
    scores["numeric_content"] = min(15, len(numbers) / 3 * 15)

    scores["total"] = round(sum(scores.values()), 1)
    return scores


# ── A/B 테스트 실행기 ──────────────────────────────────────────

class PromptABTest:
    """프롬프트 A/B 테스트 실행."""

    def __init__(self, llm, portfolio: dict, market_data: dict):
        self.llm = llm
        self.portfolio = portfolio
        self.market_data = market_data

    def run_test(
        self,
        agent_class,
        variant_prompt: str | None = None,
        rounds: int = 3,
    ) -> dict:
        """A(현재 프롬프트) vs B(변형 프롬프트) 테스트.

        Args:
            agent_class: 에이전트 클래스
            variant_prompt: B 변형 프롬프트 (None이면 A만 측정)
            rounds: 반복 횟수 (평균 산출)

        Returns:
            비교 결과 dict
        """
        results_a = []
        results_b = []

        # A: 현재 프롬프트
        agent_a = agent_class(self.llm)
        logger.info(f"[A/B] Variant A (현재): {agent_a.name}")

        for i in range(rounds):
            start = time.time()
            try:
                report = agent_a.analyze(self.portfolio, self.market_data)
                duration = time.time() - start
                quality = evaluate_report_quality(report)
                results_a.append({
                    "round": i + 1,
                    "quality": quality,
                    "duration_s": round(duration, 2),
                    "stance": report.overall_stance.value,
                    "confidence": report.confidence_score,
                })
                logger.info(f"  Round {i+1}/A: score={quality['total']}, {duration:.1f}s")
            except Exception as e:
                logger.error(f"  Round {i+1}/A 실패: {e}")
                results_a.append({"round": i + 1, "error": str(e)})

        # B: 변형 프롬프트 (있으면)
        if variant_prompt:
            agent_b = agent_class(self.llm)
            agent_b.system_prompt = variant_prompt
            logger.info(f"[A/B] Variant B (변형): {agent_b.name}")

            for i in range(rounds):
                start = time.time()
                try:
                    report = agent_b.analyze(self.portfolio, self.market_data)
                    duration = time.time() - start
                    quality = evaluate_report_quality(report)
                    results_b.append({
                        "round": i + 1,
                        "quality": quality,
                        "duration_s": round(duration, 2),
                        "stance": report.overall_stance.value,
                        "confidence": report.confidence_score,
                    })
                    logger.info(f"  Round {i+1}/B: score={quality['total']}, {duration:.1f}s")
                except Exception as e:
                    logger.error(f"  Round {i+1}/B 실패: {e}")
                    results_b.append({"round": i + 1, "error": str(e)})

        return self._compile_results(agent_a.name, results_a, results_b)

    def _compile_results(self, agent_name: str, a: list, b: list) -> dict:
        """결과 종합."""
        def avg_score(results):
            scores = [r["quality"]["total"] for r in results if "quality" in r]
            return round(sum(scores) / len(scores), 1) if scores else 0

        def avg_duration(results):
            durations = [r["duration_s"] for r in results if "duration_s" in r]
            return round(sum(durations) / len(durations), 2) if durations else 0

        result = {
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
            "rounds": len(a),
            "variant_a": {
                "avg_quality": avg_score(a),
                "avg_duration_s": avg_duration(a),
                "details": a,
            },
        }

        if b:
            result["variant_b"] = {
                "avg_quality": avg_score(b),
                "avg_duration_s": avg_duration(b),
                "details": b,
            }
            diff = avg_score(b) - avg_score(a)
            result["comparison"] = {
                "quality_diff": round(diff, 1),
                "winner": "B" if diff > 2 else "A" if diff < -2 else "TIE",
                "recommendation": (
                    "변형 B 채택 권고" if diff > 5 else
                    "변형 B 소폭 우세, 추가 테스트 필요" if diff > 2 else
                    "차이 없음, 현행 유지" if diff > -2 else
                    "현행 A가 우세"
                ),
            }

        return result


# ── CLI ────────────────────────────────────────────────────────

AGENT_MAP = {
    "quant": "src.agents.quant_agent.QuantAgent",
    "macro": "src.agents.macro_agent.MacroAgent",
    "sector": "src.agents.sector_agent.SectorAgent",
    "cycle": "src.agents.cycle_agent.CycleAgent",
    "crypto": "src.agents.crypto_agent.CryptoAgent",
    "value": "src.agents.value_agent.ValueAgent",
}


def main():
    parser = argparse.ArgumentParser(description="프롬프트 A/B 테스트")
    parser.add_argument("--agent", required=True, choices=AGENT_MAP.keys(), help="테스트할 에이전트")
    parser.add_argument("--rounds", type=int, default=3, help="반복 횟수 (기본: 3)")
    parser.add_argument("--variant-file", help="변형 프롬프트 MD 파일 경로 (없으면 A만 측정)")
    parser.add_argument("--portfolio", default="data/portfolio.json", help="포트폴리오 JSON")
    parser.add_argument("--market-data", default="tests/fixtures/sample_market_data.json", help="시장 데이터 JSON")
    parser.add_argument("--output", help="결과 저장 경로 (없으면 stdout)")
    args = parser.parse_args()

    setup_logging("INFO")

    # 에이전트 클래스 동적 로드
    module_path, class_name = AGENT_MAP[args.agent].rsplit(".", 1)
    import importlib
    module = importlib.import_module(module_path)
    agent_class = getattr(module, class_name)

    # LLM Provider
    from src.infrastructure.llm.claude_provider import ClaudeLLMProvider
    import os
    llm = ClaudeLLMProvider(
        api_key=os.environ.get("ANTHROPIC_API_KEY"),
        model=os.environ.get("LLM_MODEL", "claude-sonnet-4-6"),
    )

    # 데이터 로드
    portfolio = json.loads(Path(args.portfolio).read_text(encoding="utf-8"))
    market_data = json.loads(Path(args.market_data).read_text(encoding="utf-8"))

    # 변형 프롬프트
    variant = None
    if args.variant_file:
        variant = Path(args.variant_file).read_text(encoding="utf-8")

    # 테스트 실행
    tester = PromptABTest(llm, portfolio, market_data)
    result = tester.run_test(agent_class, variant, args.rounds)

    # 출력
    output_json = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if args.output:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(f"결과 저장: {args.output}")
    else:
        print(output_json)

    # 요약
    a_score = result["variant_a"]["avg_quality"]
    print(f"\n{'='*50}")
    print(f"📊 {result['agent']} A/B 테스트 결과 ({args.rounds}회)")
    print(f"   Variant A (현재): 평균 {a_score}점, {result['variant_a']['avg_duration_s']}초")
    if "variant_b" in result:
        b_score = result["variant_b"]["avg_quality"]
        comp = result["comparison"]
        print(f"   Variant B (변형): 평균 {b_score}점, {result['variant_b']['avg_duration_s']}초")
        print(f"   차이: {comp['quality_diff']:+.1f}점 → {comp['recommendation']}")
    print(f"{'='*50}")


if __name__ == "__main__":
    main()
