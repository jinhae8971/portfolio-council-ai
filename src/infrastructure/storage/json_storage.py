"""JSON 파일 기반 저장소 — Stage 1 구현"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .base import ResultStorage

logger = logging.getLogger(__name__)


class JSONFileStorage(ResultStorage):
    """파일 시스템에 JSON으로 보고서 저장.

    구조:
        base_dir/
        ├── history/
        │   ├── 2026-04-13.json
        │   └── 2026-04-14.json
        └── latest_analysis.json  (대시보드용)
    """

    def __init__(self, base_dir: str = "data"):
        self.base_dir = Path(base_dir)
        self.history_dir = self.base_dir / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def save_report(self, report: dict, user_id: str = "default") -> str:
        date_str = report.get("date", datetime.now().strftime("%Y-%m-%d"))
        report_id = f"{user_id}_{date_str}"
        path = self.history_dir / f"{date_str}.json"

        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Storage] 보고서 저장: {path}")
        return report_id

    def load_report(self, report_id: str) -> Optional[dict]:
        # report_id = "default_2026-04-13" → 날짜 추출
        parts = report_id.split("_", 1)
        date_str = parts[-1] if len(parts) > 1 else parts[0]
        path = self.history_dir / f"{date_str}.json"

        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def list_reports(self, user_id: str = "default", limit: int = 10) -> List[dict]:
        files = sorted(self.history_dir.glob("*.json"), reverse=True)[:limit]
        result = []
        for f in files:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                result.append({
                    "report_id": f"{user_id}_{f.stem}",
                    "date": f.stem,
                    "consensus": data.get("verdict", {}).get("consensus_type", "unknown"),
                    "confidence": data.get("verdict", {}).get("confidence_score", 0),
                })
            except Exception:
                continue
        return result

    def save_latest(self, report: dict, user_id: str = "default") -> None:
        """대시보드용 최신 보고서 저장 (docs/data/)."""
        docs_data = self.base_dir.parent / "docs" / "data"
        docs_data.mkdir(parents=True, exist_ok=True)

        path = docs_data / "latest_analysis.json"
        path.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        logger.info(f"[Storage] 대시보드용 최신 보고서 저장: {path}")
