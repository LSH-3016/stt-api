from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)

from routers import stt

app = FastAPI(
    title="STT Service",
    description="Speech-to-Text 마이크로서비스 (Amazon Nova Sonic)",
    version="1.0.0"
)

# CORS 설정
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "service": "stt-service",
        "model": "amazon.nova-2-sonic-v1:0"
    }

@app.get("/")
async def root():
    return {
        "message": "STT Service is running",
        "docs": "/docs",
        "websocket": "/stt/stream"
    }

# 라우터 등록
app.include_router(stt.router)
