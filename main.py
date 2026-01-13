from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import logging
import os

# 로깅 설정
logging.basicConfig(level=logging.INFO)

from routers import stt

# Rate Limiter 설정
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="STT Service",
    description="Speech-to-Text 마이크로서비스 (Amazon Nova Sonic)",
    version="1.0.0"
)

# Rate Limiter 등록
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

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
        "engine": "amazon-transcribe"
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
