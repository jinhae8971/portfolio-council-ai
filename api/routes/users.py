"""사용자 프로필 API"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import Optional

from ..deps import get_current_user

router = APIRouter()


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    telegram_chat_id: Optional[str] = None


@router.get("/me")
async def get_profile(user: dict = Depends(get_current_user)):
    """내 프로필."""
    # TODO: profiles 테이블에서 조회
    return {
        "user_id": user["user_id"],
        "email": user.get("email"),
        "plan": "free",
    }


@router.put("/me")
async def update_profile(
    body: ProfileUpdate,
    user: dict = Depends(get_current_user),
):
    """프로필 수정."""
    # TODO: profiles 테이블 UPDATE
    return {"status": "updated"}


@router.get("/me/usage")
async def get_usage(user: dict = Depends(get_current_user)):
    """API 사용량."""
    # TODO: analyses 테이블에서 이번 주 분석 횟수, 토큰 사용량 집계
    return {
        "analyses_this_week": 0,
        "total_tokens": 0,
        "estimated_cost_usd": 0,
    }
