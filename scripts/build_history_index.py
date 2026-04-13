#!/usr/bin/env python3
"""히스토리 인덱스 생성기

data/history/ 디렉토리의 JSON 파일들을 스캔하여
docs/data/history_index.json을 생성한다.
GitHub Pages 대시보드의 history.html이 이 인덱스를 읽어 렌더링.

GitHub Actions의 portfolio-review 워크플로우 끝에 실행.

Usage:
    python scripts/build_history_index.py
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

logger = logging.getLogger(__name__)

HISTORY_DIR = project_root / "data" / "history"
OUTPUT_PATH = project_root / "docs" / "data" / "history_index.json"


def build_index() -> list:
    """히스토리 파일들을 스캔하여 요약 인덱스 생성."""
    entries = []

    if not HISTORY_DIR.exists():
        logger.info("data/history/ 디렉토리 없음")
        return entries

    for f in sorted(HISTORY_DIR.glob("*.json"), reverse=True):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            verdict = data.get("verdict", {})

            entry = {
                "date": data.get("date", f.stem),
                "consensus": verdict.get("consensus_type", "unknown"),
                "confidence": verdict.get("confidence_score", 0),
                "changes": len(verdict.get("portfolio_changes", [])),
                "risks": len(verdict.get("risk_warnings", [])),
                "summary": (verdict.get("summary", ""))[:200],
                "stances": verdict.get("stance_votes", {}),
                "cash_target": None,
            }

            cash_rec = verdict.get("cash_recommendation")
            if isinstance(cash_rec, dict):
                entry["cash_target"] = cash_rec.get("target")

            entries.append(entry)
        except Exception as e:
            logger.warning(f"파일 파싱 실패: {f.name} — {e}")

    return entries


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    entries = build_index()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(
        json.dumps({
            "generated_at": datetime.now().isoformat(),
            "count": len(entries),
            "reports": entries,
        }, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print(f"✅ 히스토리 인덱스 생성: {len(entries)}개 보고서 → {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
