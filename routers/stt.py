from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
import logging
import os
import asyncio
import boto3

from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

router = APIRouter(prefix="/stt", tags=["STT (Speech-to-Text)"])
logger = logging.getLogger(__name__)

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
    
    region = os.getenv('AWS_REGION', 'ap-northeast-2')
    
    try:
        # Transcribe Streaming 클라이언트 생성 (boto3가 자동으로 IRSA credential 사용)
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



@router.get("/health")
async def stt_health_check():
    return {
        "status": "healthy",
        "service": "stt",
        "engine": "amazon-transcribe-streaming",
        "streaming": "enabled"
    }
