# backend/app/main.py
"""
FastAPI 앱 진입점.

실행 방법:
    cd backend
    uvicorn app.main:app --reload --port 8000
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers.chat import router as chat_router

app = FastAPI(
    title="Lodi",
    description="한국 노동법 RAG 챗봇 API — 공식 문서 기반, 할루시네이션 차단",
)

# CORS 설정: 프론트엔드(Vite 기본 5173)에서 백엔드(8000)로 요청 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 라우터 등록
app.include_router(chat_router)


@app.get("/health")
async def health():
    """서버 상태 확인용 엔드포인트."""
    return {"status": "ok"}
