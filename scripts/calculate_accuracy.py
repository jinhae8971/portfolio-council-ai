#!/usr/bin/env python3
"""추천 적중률 계산 스크립트

과거 분석 보고서의 포트폴리오 변경 제안 vs 실제 가격 변동을 비교하여
에이전트별·전체 적중률을 산출한다.

Usage:
    python scripts/calculate_accuracy.py
    python scripts/calculate_accuracy.py --days 14  # 14일 후 기준
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)

HISTORY_DIR = project_root / "data" / "history"
ACCURACY_OUTPUT = project_root / "docs" / "data" / "accuracy.json"


def load_history_reports(min_age_days: int = 7) -> list:
    """평가 가능한 (N일 이상 경과한) 과거 보고서 로드."""
    cutoff = datetime.now() - timedelta(days=min_age_days)
    reports = []

    for f in sorted(HISTORY_DIR.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            report_date = datetime.strptime(data["date"], "%Y-%m-%d")
            if report_date <= cutoff:
                reports.append(data)
        except Exception as e:
            logger.warning(f"보고서 로드 실패: {f.name} — {e}")

    return reports


def fetch_current_prices(tickers: list) -> dict:
    """현재 가격 조회."""
    try:
        import yfinance as yf
        prices = {}
        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                hist = stock.history(period="5d")
                if not hist.empty:
                    prices[ticker] = float(hist["Close"].iloc[-1])
            except Exception:
                pass
        return prices
    except ImportError:
        logger.error("yfinance가 설치되지 않았습니다")
        return {}


def evaluate_report(report: dict, current_prices: dict, eval_days: int) -> dict:
    """단일 보고서의 추천 적중률 평가."""
    verdict = report.get("verdict", {})
    changes = verdict.get("portfolio_changes", [])
    report_date = report["date"]

    evaluations = []
    correct = 0
    total = 0

    for change in changes:
        ticker = change.get("ticker", "")
        action = change.get("action", "")

        # 보고서 당시 가격 (portfolio에서)
        holdings = report.get("portfolio", {}).get("holdings", [])
        orig_price = None
        for h in holdings:
            if h["ticker"] == ticker:
                orig_price = h.get("avg_price")
                break

        current_price = current_prices.get(ticker)

        if orig_price and current_price and orig_price > 0:
            actual_return = (current_price - orig_price) / orig_price * 100

            # 적중 판정
            is_correct = False
            if action in ("increase", "add_new") and actual_return > 0:
                is_correct = True
            elif action in ("reduce", "remove") and actual_return < 0:
                is_correct = True
            elif action == "reduce" and actual_return > 0:
                is_correct = False  # 줄이라고 했는데 올랐음

            evaluations.append({
                "ticker": ticker,
                "action": action,
                "report_date": report_date,
                "actual_return_pct": round(actual_return, 2),
                "is_correct": is_correct,
                "supporters": change.get("supporters", []),
            })

            total += 1
            if is_correct:
                correct += 1

    return {
        "report_date": report_date,
        "consensus_type": verdict.get("consensus_type", "unknown"),
        "evaluations": evaluations,
        "correct": correct,
        "total": total,
        "accuracy_pct": round(correct / total * 100, 1) if total > 0 else None,
    }


def calculate_agent_accuracy(all_evaluations: list) -> dict:
    """에이전트별 적중률 집계."""
    agent_stats = {}

    for eval_report in all_evaluations:
        for e in eval_report.get("evaluations", []):
            for agent in e.get("supporters", []):
                if agent not in agent_stats:
                    agent_stats[agent] = {"correct": 0, "total": 0}
                agent_stats[agent]["total"] += 1
                if e["is_correct"]:
                    agent_stats[agent]["correct"] += 1

    for agent, stats in agent_stats.items():
        stats["accuracy_pct"] = (
            round(stats["correct"] / stats["total"] * 100, 1)
            if stats["total"] > 0 else None
        )

    return agent_stats


def main():
    parser = argparse.ArgumentParser(description="추천 적중률 계산")
    parser.add_argument("--days", type=int, default=7, help="평가 기준 일수 (기본: 7일)")
    args = parser.parse_args()

    setup_logging("INFO")

    if not HISTORY_DIR.exists():
        logger.info("히스토리 디렉토리가 없습니다. 아직 분석이 실행되지 않았을 수 있어요.")
        return

    # 과거 보고서 로드
    reports = load_history_reports(min_age_days=args.days)
    if not reports:
        logger.info(f"{args.days}일 이상 경과한 보고서가 없습니다.")
        return

    logger.info(f"평가 대상 보고서: {len(reports)}개 ({args.days}일 기준)")

    # 관련 티커 수집
    all_tickers = set()
    for r in reports:
        for c in r.get("verdict", {}).get("portfolio_changes", []):
            all_tickers.add(c.get("ticker", ""))
    all_tickers.discard("")

    # 현재 가격 조회
    current_prices = fetch_current_prices(list(all_tickers))
    logger.info(f"가격 조회 완료: {len(current_prices)}/{len(all_tickers)}개 종목")

    # 각 보고서 평가
    all_evals = []
    for r in reports:
        eval_result = evaluate_report(r, current_prices, args.days)
        all_evals.append(eval_result)
        if eval_result["accuracy_pct"] is not None:
            logger.info(
                f"  {eval_result['report_date']}: "
                f"{eval_result['correct']}/{eval_result['total']} "
                f"({eval_result['accuracy_pct']}%)"
            )

    # 에이전트별 적중률
    agent_accuracy = calculate_agent_accuracy(all_evals)

    # 전체 적중률
    total_correct = sum(e["correct"] for e in all_evals)
    total_count = sum(e["total"] for e in all_evals)
    overall_accuracy = round(total_correct / total_count * 100, 1) if total_count > 0 else None

    # 결과 저장
    accuracy_report = {
        "generated_at": datetime.now().isoformat(),
        "eval_days": args.days,
        "reports_evaluated": len(all_evals),
        "overall": {
            "correct": total_correct,
            "total": total_count,
            "accuracy_pct": overall_accuracy,
        },
        "by_agent": agent_accuracy,
        "by_report": all_evals,
    }

    ACCURACY_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    ACCURACY_OUTPUT.write_text(
        json.dumps(accuracy_report, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"\n{'='*50}")
    print(f"📊 적중률 리포트 ({args.days}일 기준)")
    print(f"   전체: {total_correct}/{total_count} ({overall_accuracy}%)")
    for agent, stats in sorted(agent_accuracy.items()):
        print(f"   {agent}: {stats['correct']}/{stats['total']} ({stats['accuracy_pct']}%)")
    print(f"{'='*50}")
    print(f"저장: {ACCURACY_OUTPUT}")


if __name__ == "__main__":
    main()
