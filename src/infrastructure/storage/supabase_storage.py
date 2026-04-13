"""Supabase PostgreSQL 기반 저장소 — Stage 2 구현

ResultStorage 인터페이스를 구현하여 Stage 1의 JSONFileStorage와 교체 가능.
Supabase Python 클라이언트를 사용하며, RLS(Row Level Security)를 통해
사용자별 데이터 격리를 보장.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import List, Optional

from .base import ResultStorage

logger = logging.getLogger(__name__)


class SupabaseStorage(ResultStorage):
    """Supabase PostgreSQL에 분석 보고서 저장.

    Stage 1의 JSONFileStorage와 동일한 인터페이스.
    PortfolioService 코드 변경 없이 교체 가능.
    """

    def __init__(self, url: str, key: str, service_role_key: Optional[str] = None):
        """
        Args:
            url: Supabase 프로젝트 URL
            key: Supabase anon key (RLS 적용)
            service_role_key: 관리자용 키 (RLS 우회, 백그라운드 작업용)
        """
        try:
            from supabase import create_client, Client
        except ImportError:
            raise ImportError("supabase 패키지가 필요합니다: pip install supabase")

        self.client: Client = create_client(url, key)
        self._service_client: Optional[Client] = None
        if service_role_key:
            self._service_client = create_client(url, service_role_key)

    def save_report(self, report: dict, user_id: str = "default") -> str:
        """분석 보고서를 analyses 테이블에 저장."""
        verdict = report.get("verdict", {})

        record = {
            "user_id": user_id,
            "portfolio_id": report.get("portfolio", {}).get("id"),
            "phase1_reports": report.get("debate", {}).get("phase1_reports", []),
            "phase2_critiques": report.get("debate", {}).get("phase2_critiques", []),
            "verdict": verdict,
            "consensus_type": verdict.get("consensus_type"),
            "confidence_score": verdict.get("confidence_score"),
            "market_data": report.get("domain_data"),
            "status": "completed",
        }

        try:
            result = self._get_client(user_id).table("analyses").insert(record).execute()
            analysis_id = result.data[0]["id"] if result.data else None
            logger.info(f"[Supabase] 보고서 저장: analysis_id={analysis_id}")

            # 적중률 추적 레코드 생성
            self._create_accuracy_records(analysis_id, verdict)

            return str(analysis_id)

        except Exception as e:
            logger.error(f"[Supabase] 보고서 저장 실패: {e}")
            raise

    def load_report(self, report_id: str) -> Optional[dict]:
        """분석 보고서 로드."""
        try:
            result = (
                self.client.table("analyses")
                .select("*")
                .eq("id", report_id)
                .single()
                .execute()
            )
            if result.data:
                return self._to_report_format(result.data)
            return None

        except Exception as e:
            logger.error(f"[Supabase] 보고서 로드 실패: {e}")
            return None

    def list_reports(self, user_id: str = "default", limit: int = 10) -> List[dict]:
        """보고서 목록 (최신순)."""
        try:
            result = (
                self._get_client(user_id)
                .table("analyses")
                .select("id, created_at, consensus_type, confidence_score, status")
                .eq("user_id", user_id)
                .order("created_at", desc=True)
                .limit(limit)
                .execute()
            )

            return [
                {
                    "report_id": str(r["id"]),
                    "date": r["created_at"][:10],
                    "consensus": r.get("consensus_type", "unknown"),
                    "confidence": r.get("confidence_score", 0),
                    "status": r.get("status", "unknown"),
                }
                for r in (result.data or [])
            ]

        except Exception as e:
            logger.error(f"[Supabase] 보고서 목록 실패: {e}")
            return []

    def save_latest(self, report: dict, user_id: str = "default") -> None:
        """Stage 2에서는 save_report와 동일 (DB에 이미 저장됨).

        Stage 1 호환성을 위해 빈 구현 유지.
        프론트엔드는 API를 통해 최신 보고서를 조회.
        """
        pass

    # ── 헬퍼 메서드 ─────────────────────────────────────────────

    def _get_client(self, user_id: str):
        """사용자 컨텍스트에 맞는 클라이언트 반환.

        백그라운드 작업(worker)에서는 service_role_key가 필요.
        """
        if user_id == "system" and self._service_client:
            return self._service_client
        return self.client

    def _create_accuracy_records(self, analysis_id: str, verdict: dict) -> None:
        """적중률 추적 레코드를 미리 생성 (실제 수익률은 나중에 채움)."""
        changes = verdict.get("portfolio_changes", [])
        if not changes or not analysis_id:
            return

        records = []
        for c in changes:
            records.append({
                "analysis_id": analysis_id,
                "ticker": c.get("ticker", ""),
                "recommended_action": c.get("action", ""),
                "recommended_weight": c.get("to_weight"),
                "supporters": c.get("supporters", []),
            })

        try:
            if records:
                self.client.table("accuracy_records").insert(records).execute()
                logger.info(f"[Supabase] 적중률 레코드 {len(records)}개 생성")
        except Exception as e:
            logger.warning(f"[Supabase] 적중률 레코드 생성 실패: {e}")

    @staticmethod
    def _to_report_format(row: dict) -> dict:
        """DB 행을 Stage 1 호환 보고서 형식으로 변환."""
        return {
            "date": row["created_at"][:10],
            "generated_at": row["created_at"],
            "user_id": row.get("user_id", "default"),
            "domain_data": row.get("market_data", {}),
            "debate": {
                "phase1_reports": row.get("phase1_reports", []),
                "phase2_critiques": row.get("phase2_critiques", []),
            },
            "verdict": row.get("verdict", {}),
        }
