"""분석 실행/조회 API"""

from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from ..deps import get_current_user, check_plan_limit

router = APIRouter()


class AnalysisRequest(BaseModel):
    portfolio_id: str


@router.post("/analyses", status_code=202)
async def request_analysis(
    body: AnalysisRequest,
    background_tasks: BackgroundTasks,
    plan_info: dict = Depends(check_plan_limit),
):
    """분석 실행 요청 (비동기).

    1. analyses 테이블에 status="pending" 생성
    2. Background worker가 실행
    3. 클라이언트는 GET /analyses/{id}로 폴링
    """
    user = plan_info["user"]
    limits = plan_info["limits"]

    # TODO: 주간 분석 횟수 체크
    # TODO: analyses 테이블에 pending 레코드 생성
    analysis_id = "new-analysis-uuid"

    # Background에서 PortfolioService.run() 실행
    background_tasks.add_task(_run_analysis, analysis_id, body.portfolio_id, user["user_id"])

    return {
        "analysis_id": analysis_id,
        "status": "pending",
        "message": "분석이 시작되었습니다. GET /api/v1/analyses/{id}로 결과를 확인하세요.",
    }


@router.get("/analyses")
async def list_analyses(
    limit: int = 10,
    user: dict = Depends(get_current_user),
):
    """내 분석 히스토리."""
    # TODO: Supabase에서 user_id로 조회
    return {"analyses": [], "count": 0}


@router.get("/analyses/latest")
async def get_latest_analysis(user: dict = Depends(get_current_user)):
    """최신 분석 결과."""
    # TODO: Supabase에서 가장 최근 completed 분석 조회
    return {"analysis": None, "message": "아직 분석 결과가 없습니다"}


@router.get("/analyses/{analysis_id}")
async def get_analysis(
    analysis_id: str,
    user: dict = Depends(get_current_user),
):
    """분석 결과 상세."""
    # TODO: Supabase에서 조회
    return {"id": analysis_id, "status": "TODO"}


async def _run_analysis(analysis_id: str, portfolio_id: str, user_id: str):
    """Background worker: 실제 분석 실행.

    Stage 1의 PortfolioService.run()을 그대로 호출.
    """
    try:
        # TODO: 구현
        # 1. portfolio_id로 포트폴리오 로드
        # 2. config.create_agents(stage="beta") 로 에이전트 생성
        # 3. PortfolioService.run(portfolio, user_id) 실행
        # 4. analyses 테이블 status="completed" 업데이트
        pass
    except Exception as e:
        # analyses 테이블 status="failed", error_message 업데이트
        pass
