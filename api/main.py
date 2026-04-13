"""Portfolio Council AI — FastAPI REST API

Stage 2 백엔드 API 서버.
Supabase Auth JWT 검증 + PortfolioService 호출.

Usage:
    uvicorn api.main:app --reload --port 8000
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes import portfolios, analyses, accuracy, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    """서버 시작/종료 시 실행."""
    # Startup
    print("🚀 Portfolio Council API starting...")
    yield
    # Shutdown
    print("👋 Portfolio Council API shutting down...")


app = FastAPI(
    title="Portfolio Council AI",
    description="멀티에이전트 투자자문 시스템 API",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS (프론트엔드 도메인 허용)
ALLOWED_ORIGINS = os.environ.get("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우트 등록
app.include_router(portfolios.router, prefix="/api/v1", tags=["Portfolios"])
app.include_router(analyses.router, prefix="/api/v1", tags=["Analyses"])
app.include_router(accuracy.router, prefix="/api/v1", tags=["Accuracy"])
app.include_router(users.router, prefix="/api/v1", tags=["Users"])


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "2.0.0"}
