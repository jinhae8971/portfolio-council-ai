"""API 의존성 — Auth, DB 세션, Plan 체크"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Depends, HTTPException, Header


async def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    """Supabase JWT에서 사용자 정보 추출.

    Authorization: Bearer <jwt> 헤더에서 JWT를 파싱.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="인증이 필요합니다")

    token = authorization[7:]

    try:
        # Supabase JWT 검증 (실제 구현 시 python-jose 또는 supabase-py 사용)
        # 여기서는 스켈레톤이므로 기본 구조만 제공
        import jwt as pyjwt

        supabase_jwt_secret = os.environ.get("SUPABASE_JWT_SECRET", "")
        payload = pyjwt.decode(token, supabase_jwt_secret, algorithms=["HS256"],
                               audience="authenticated")

        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated"),
        }

    except Exception as e:
        raise HTTPException(status_code=401, detail=f"유효하지 않은 토큰: {str(e)}")


# Plan 체크 의존성
PLAN_LIMITS = {
    "free":    {"max_portfolios": 1, "max_analyses_per_week": 1, "agents": 4},
    "pro":     {"max_portfolios": 5, "max_analyses_per_week": 7, "agents": 6},
    "premium": {"max_portfolios": -1, "max_analyses_per_week": -1, "agents": 6},
}


async def check_plan_limit(user: dict = Depends(get_current_user)):
    """사용자 플랜 제한 확인.

    실제 구현 시 profiles 테이블에서 plan 조회.
    """
    # TODO: DB에서 사용자 plan 조회
    plan = "free"  # 기본값
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
    return {"user": user, "plan": plan, "limits": limits}
