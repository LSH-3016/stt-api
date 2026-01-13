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

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

from schemas.stt import STTResponse
from services.stt import stt_service

router = APIRouter(prefix="", tags=["STT (Speech-to-Text)"])
logger = logging.getLogger(__name__)

limiter = Limiter(key_func=get_remote_address)

class WebSocketTranscriptHandler(TranscriptResultStreamHandler):
    """Transcribe 결과를 WebSocket으로 실시간 전송하는 핸들러"""
    def __init__(self, stream, websocket: WebSocket):
        super().__init__(stream)
        self.websocket = websocket
        self.full_transcript = ""
    
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            for alt in result.alternatives:
                if result.is_partial:
                    # 중간 결과 - 바로 전송 (딜레이 최소화)
                    await self.websocket.send_json({
                        "text": alt.transcript,
                        "full_text": self.full_transcript + alt.transcript,
                        "is_final": False
                    })
                else:
                    # 최종 결과
                    self.full_transcript += alt.transcript + " "
                    await self.websocket.send_json({
                        "text": alt.transcript,
                        "full_text": self.full_transcript.strip(),
                        "is_final": True
                    })

@router.websocket("/stream")
async def websocket_stt_stream(websocket: WebSocket):
    """실시간 음성 스트림을 텍스트로 변환 (WebSocket + Transcribe Streaming)"""
    await websocket.accept()
    logger.info("WebSocket STT 연결 시작")
    
    region = os.getenv('AWS_REGION', 'us-east-1')
    
    try:
        # Transcribe Streaming 클라이언트 생성
        client = TranscribeStreamingClient(region=region)
        
        # 스트림 시작
        stream = await client.start_stream_transcription(
            language_code="ko-KR",
            media_sample_rate_hz=16000,
            media_encoding="pcm",
        )
        
        handler = WebSocketTranscriptHandler(stream.output_stream, websocket)
        
        # 결과 처리 태스크 시작
        handler_task = asyncio.create_task(handler.handle_events())
        
        try:
            while True:
                # 클라이언트로부터 오디오 청크 수신
                audio_chunk = await websocket.receive_bytes()
                
                if len(audio_chunk) > 0:
                    # Transcribe로 오디오 전송
                    await stream.input_stream.send_audio_event(audio_chunk=audio_chunk)
                    
        except WebSocketDisconnect:
            logger.info("WebSocket 연결 종료")
        finally:
            # 스트림 종료
            await stream.input_stream.end_stream()
            await handler_task
            
            if handler.full_transcript:
                logger.info(f"최종 변환: {handler.full_transcript}")
                
    except Exception as e:
        logger.error(f"STT 스트리밍 오류: {e}")
        try:
            await websocket.send_json({"error": str(e), "text": "", "is_final": False})
        except:
            pass
        await websocket.close()

@router.post("/transcribe", response_model=STTResponse)
@limiter.limit("10/minute")
async def transcribe_audio(
    request: Request,
    audio: UploadFile = File(..., description="음성 파일 (wav, mp3, ogg 등)")
):
    """음성 파일을 텍스트로 변환"""
    MAX_FILE_SIZE = 5 * 1024 * 1024
    allowed_extensions = {'.wav', '.mp3', '.ogg', '.flac', '.m4a', '.webm'}
    file_ext = os.path.splitext(audio.filename or '.wav')[1].lower()
    
    if file_ext not in allowed_extensions:
        raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다.")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
        total_size = 0
        try:
            while chunk := await audio.read(8192):
                total_size += len(chunk)
                if total_size > MAX_FILE_SIZE:
                    os.unlink(temp_file.name)
                    raise HTTPException(status_code=413, detail="파일이 너무 큽니다.")
                temp_file.write(chunk)
            
            if total_size == 0:
                os.unlink(temp_file.name)
                raise HTTPException(status_code=400, detail="빈 파일입니다.")
            
            temp_path = temp_file.name
        except HTTPException:
            raise
        except Exception as e:
            if os.path.exists(temp_file.name):
                os.unlink(temp_file.name)
            raise HTTPException(status_code=500, detail=str(e))
    
    try:
        content_type = audio.content_type or "audio/wav"
        logger.info(f"STT 요청: {audio.filename}, {total_size} bytes")
        
        with open(temp_path, 'rb') as f:
            audio_data = f.read()
            result = await asyncio.wait_for(
                stt_service.transcribe_file(audio_data, content_type),
                timeout=30.0
            )
        
        return STTResponse(**result)
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="변환 시간 초과")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)

@router.get("/health")
async def stt_health_check():
    return {
        "status": "healthy",
        "service": "stt",
        "engine": "amazon-transcribe-streaming",
        "streaming": "enabled"
    }
