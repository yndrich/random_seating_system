"""FastAPI 앱 진입점."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import participants, rounds, session

app = FastAPI(
    title="랜덤 조 배정 시스템",
    description=(
        "참가자를 조별 테이블로 배정하는 API. 회사 분리·이전 동석 회피(하드 제약)와 "
        "성비·연령·MBTI 분산(소프트 제약)을 동시에 최적화한다."
    ),
    version="1.0.0",
)

# 개발용 CORS: Vite dev 서버에서 호출 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(session.router)
app.include_router(participants.router)
app.include_router(rounds.router)


@app.get("/api/health", tags=["health"])
def health() -> dict[str, str]:
    return {"status": "ok"}
