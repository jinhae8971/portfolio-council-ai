"""적중률 조회 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ..deps import get_current_user

router = APIRouter()


@router.get("/accuracy")
async def get_accuracy_summary(user: dict = Depends(get_current_user)):
    """내 적중률 요약."""
    # TODO: accuracy_records 테이블에서 집계
    return {
        "overall": {"correct": 0, "total": 0, "accuracy_pct": None},
        "eval_days": 7,
    }


@router.get("/accuracy/agents")
async def get_agent_accuracy(user: dict = Depends(get_current_user)):
    """에이전트별 적중률."""
    # TODO: accuracy_records에서 supporters별 집계
    return {"by_agent": {}}
