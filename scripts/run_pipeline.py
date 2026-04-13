#!/usr/bin/env python3
"""Portfolio Council AI — CLI 진입점

Usage:
    python scripts/run_pipeline.py                          # 기본 포트폴리오로 실행
    python scripts/run_pipeline.py --portfolio data/portfolio.json  # 지정 포트폴리오
    python scripts/run_pipeline.py --no-notify              # 알림 없이 실행
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# 프로젝트 루트를 sys.path에 추가
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.application.config import create_agents
from src.application.portfolio_service import PortfolioService
from src.utils.logging import setup_logging

logger = logging.getLogger(__name__)


def load_portfolio(path: str) -> dict:
    """포트폴리오 JSON 로드."""
    p = Path(path)
    if not p.exists():
        logger.error(f"포트폴리오 파일 없음: {path}")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser(description="Portfolio Council AI — 멀티에이전트 투자 분석")
    parser.add_argument("--portfolio", default="data/portfolio.json", help="포트폴리오 JSON 경로")
    parser.add_argument("--user-id", default="default", help="사용자 ID")
    parser.add_argument("--no-notify", action="store_true", help="Telegram 알림 비활성화")
    parser.add_argument("--dashboard-url", default="", help="대시보드 URL (알림에 포함)")
    parser.add_argument("--stage", default="personal", help="실행 스테이지 (personal/beta/commercial)")
    parser.add_argument("--log-level", default="INFO", help="로그 레벨")
    args = parser.parse_args()

    setup_logging(args.log_level)

    # 포트폴리오 로드
    portfolio = load_portfolio(args.portfolio)
    logger.info(f"포트폴리오 로드 완료: {portfolio.get('name', 'unknown')}")

    # 앱 구성
    agents, llm, storage = create_agents(args.stage)
    service = PortfolioService(agents=agents, llm=llm, storage=storage)

    # 파이프라인 실행
    report = service.run(
        portfolio=portfolio,
        user_id=args.user_id,
        notify=not args.no_notify,
        dashboard_url=args.dashboard_url,
    )

    # 결과 출력
    verdict = report["verdict"]
    print(f"\n{'='*60}")
    print(f"✅ 분석 완료 — {report['date']}")
    print(f"   합의: {verdict['consensus_type']} (확신도: {verdict['confidence_score']}%)")
    print(f"   요약: {verdict['summary'][:200]}")
    if verdict.get("portfolio_changes"):
        print(f"   변경 제안: {len(verdict['portfolio_changes'])}건")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
