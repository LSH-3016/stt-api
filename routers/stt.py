from fastapi import APIRouter, UploadFile, File, HTTPException, WebSocket, WebSocketDisconnect, Request
from typing import Optional
import logging
import json
import tempfile
import os
import time
import asyncio

from slowapi import Limiter
from slowapi.util import get_remote_address

from schemas.stt import STTResponse
from services.stt import stt_service

router = APIRouter(prefix="/stt", tags=["STT (Speech-to-Text)"])
logger = logging.getLogger(__name__)

# Rate Limiter 설정 (1분에 10번)
limiter = Limiter(key_func=get_remote_address)

@router.websocket("/stream")
async def websocket_stt_stream(websocket: WebSocket):
    """
    실시간 음성 스트림을 텍스트로 변환합니다 (WebSocket).
    
    클라이언트는 음성 데이터를 바이너리로 전송하고,
    서버는 실시간으로 변환된 텍스트만 JSON으로 반환합니다.
    
    **메시지 형식:**
    - 클라이언트 → 서버: 바이너리 음성 데이터 (PCM 16kHz)
    - 서버 → 클라이언트: JSON {"text": "...", "full_text": "...", "is_final": false}
    
    **연결 예시 (JavaScript):**
    ```javascript
    const ws = new WebSocket('ws://localhost:8000/stt/stream');
    
    // 음성 데이터 전송
    navigator.mediaDevices.getUserMedia({ audio: true })
      .then(stream => {
        const mediaRecorder = new MediaRecorder(stream);
        mediaRecorder.ondataavailable = (event) => {
          ws.send(event.data);
        };
        mediaRecorder.start(100); // 100ms마다 전송
      });
    
    // 변환된 텍스트만 수신
    ws.onmessage = (event) => {
      const result = JSON.parse(event.data);
      console.log(result.text); // 변환된 텍스트
    };
    ```
    """
    await websocket.accept()
    logger.info("WebSocket STT 연결 시작")
    
    try:
        full_transcript = ""
        
        while True:
            # 클라이언트로부터 음성 데이터 수신
            audio_chunk = await websocket.receive_bytes()
            
            if len(audio_chunk) == 0:
                continue
            
            logger.debug(f"음성 청크 수신: {len(audio_chunk)} bytes")
            
            # 실시간 STT 변환만 수행
            try:
                result = await stt_service.transcribe_audio(audio_chunk, "audio/pcm")
                
                if result["text"]:
                    full_transcript += result["text"] + " "
                    
                    # 변환된 텍스트만 전송
                    await websocket.send_json({
                        "text": result["text"],
                        "full_text": full_transcript.strip(),
                        "is_final": False
                    })
                    
            except Exception as e:
                logger.error(f"STT 처리 오류: {e}")
                await websocket.send_json({
                    "error": str(e),
                    "text": "",
                    "is_final": False
                })
                
    except WebSocketDisconnect:
        logger.info("WebSocket STT 연결 종료")
        if full_transcript:
            logger.info(f"최종 변환 텍스트: {full_transcript}")
    except Exception as e:
        logger.error(f"WebSocket 오류: {e}")
        await websocket.close()

@router.post("/transcribe", response_model=STTResponse)
@limiter.limit("10/minute")
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(..., description="음성 파일 (wav, mp3, ogg 등)")
):
    """
    음성 파일을 텍스트로 변환합니다.
    
    - **audio**: 음성 파일 (최대 5MB)
    - **Rate Limit**: 1분에 10번
    
    지원 형식: WAV, MP3, OGG, FLAC, M4A, WEBM
    """
    # 파일 크기 제한 (5MB)
    MAX_FILE_SIZE = 5 * 1024 * 1024
    
    # 파일 확장자 검증
    allowed_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm'}
    file_ext = os.path.splitext(audio.filename or '.wav')[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 파일 형식입니다. 지원 형식: {', '.join(allowed_extensions)}"
        )
    
    # 임시 파일로 저장 (메모리 절약)
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        total_size = 0
        
        try:
            # 청크 단위로 읽어서 쓰기 (8KB씩)
            while chunk := await audio.read(8192):
                total_size += len(chunk)
                
                # 파일 크기 체크
                if total_size > MAX_FILE_SIZE:
                    os.unlink(temp_file.name)
                    raise HTTPException(
                        status_code=413,
                        detail=f"파일이 너무 큽니다. 최대 {MAX_FILE_SIZE / 1024 / 1024}MB까지 지원합니다."
                    )
                
                temp_file.write(chunk)
            
            if total_size == 0:
                os.unlink(temp_file.name)
                raise HTTPException(status_code=400, detail="빈 파일입니다.")
            
            temp_path = temp_file.name
        
        except HTTPException:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise
        except Exception as e:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            logger.error(f"파일 저장 오류: {e}")
            raise HTTPException(status_code=500, detail=f"파일 처리 중 오류가 발생했습니다: {str(e)}")
    
    try:
        # Content-Type 결정
        content_type = audio.content_type or "audio/wav"
        
        logger.info(f"STT 요청 시작: {audio.filename}, {total_size} bytes, {content_type}")
        
        # 임시 파일에서 읽어서 STT 변환
        with open(temp_path, 'rb') as f:
            audio_data = f.read()
            
            start_time = time.time()
            
            # 30초 타임아웃 설정
            try:
                result = await asyncio.wait_for(
                    stt_service.transcribe_audio(audio_data, content_type),
                    timeout=30.0
                )
            except asyncio.TimeoutError:
                logger.error(f"STT 변환 타임아웃: {audio.filename}")
                raise HTTPException(
                    status_code=504,
                    detail="음성 변환 시간이 초과되었습니다. 더 짧은 파일로 시도해주세요."
                )
            
            elapsed_time = time.time() - start_time
            logger.info(f"STT 변환 완료: {elapsed_time:.2f}초, 텍스트 길이: {len(result.get('text', ''))}")
        
        return STTResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"STT 변환 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # 임시 파일 삭제
        if os.path.exists(temp_path):
            os.unlink(temp_path)

@router.get("/health")
async def stt_health_check():
    """STT 서비스 상태 확인"""
    return {
        "status": "healthy",
        "service": "stt",
        "model": "amazon.nova-2-sonic-v1:0",
        "streaming": "enabled",
        "max_file_size_mb": 5,
        "rate_limit": "10/minute"
    }
