"""포트폴리오 CRUD API"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from ..deps import get_current_user

router = APIRouter()


class PortfolioCreate(BaseModel):
    name: str = "My Portfolio"
    base_currency: str = "KRW"
    cash_weight: float = 10
    holdings: list = []
    constraints: dict = {}
    agent_weights: dict = {}


class PortfolioUpdate(BaseModel):
    name: Optional[str] = None
    cash_weight: Optional[float] = None
    holdings: Optional[list] = None
    constraints: Optional[dict] = None
    agent_weights: Optional[dict] = None


@router.get("/portfolios")
async def list_portfolios(user: dict = Depends(get_current_user)):
    """내 포트폴리오 목록."""
    # TODO: Supabase에서 user_id로 조회
    return {"portfolios": [], "count": 0}


@router.post("/portfolios", status_code=201)
async def create_portfolio(
    body: PortfolioCreate,
    user: dict = Depends(get_current_user),
):
    """포트폴리오 생성."""
    # TODO: Plan 제한 체크 (free는 1개)
    # TODO: Supabase에 INSERT
    return {"id": "new-uuid", "name": body.name, "status": "created"}


@router.get("/portfolios/{portfolio_id}")
async def get_portfolio(
    portfolio_id: str,
    user: dict = Depends(get_current_user),
):
    """포트폴리오 상세."""
    # TODO: Supabase에서 조회 + user_id 확인
    return {"id": portfolio_id, "name": "TODO"}


@router.put("/portfolios/{portfolio_id}")
async def update_portfolio(
    portfolio_id: str,
    body: PortfolioUpdate,
    user: dict = Depends(get_current_user),
):
    """포트폴리오 수정."""
    # TODO: Supabase에서 UPDATE
    return {"id": portfolio_id, "status": "updated"}


@router.delete("/portfolios/{portfolio_id}", status_code=204)
async def delete_portfolio(
    portfolio_id: str,
    user: dict = Depends(get_current_user),
):
    """포트폴리오 삭제."""
    # TODO: Supabase에서 DELETE
    return None
