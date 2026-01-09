import boto3
import json
import os
import logging
from typing import Optional, AsyncIterator
import asyncio

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        self.client = boto3.client(
            'bedrock-runtime',
            region_name=os.getenv('AWS_REGION', 'us-east-1')
        )
        self.model_id = "amazon.nova-2-sonic-v1:0"
    
    async def transcribe_stream(self, audio_stream: AsyncIterator[bytes]) -> AsyncIterator[dict]:
        """
        실시간 음성 스트림을 텍스트로 변환합니다.
        
        Args:
            audio_stream: 음성 데이터 스트림
            
        Yields:
            dict: {
                "text": "변환된 텍스트",
                "is_final": False
            }
        """
        try:
            # 스트리밍 요청 준비
            request_body = {
                "audioStream": audio_stream,
                "languageCode": "ko-KR",
                "sampleRate": 16000,
                "encoding": "pcm"
            }
            
            # Bedrock 스트리밍 호출
            response = self.client.invoke_model_with_response_stream(
                modelId=self.model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(request_body)
            )
            
            # 스트림 응답 처리
            event_stream = response.get('body')
            if event_stream:
                for event in event_stream:
                    chunk = event.get('chunk')
                    if chunk:
                        chunk_data = json.loads(chunk.get('bytes').decode())
                        
                        yield {
                            "text": chunk_data.get("transcript", ""),
                            "is_final": chunk_data.get("isFinal", False)
                        }
                        
        except Exception as e:
            logger.error(f"스트리밍 STT 오류: {e}")
            raise Exception(f"실시간 음성 변환 중 오류가 발생했습니다: {str(e)}")
    
    async def transcribe_audio(self, audio_data: bytes, content_type: str = "audio/wav") -> dict:
        """
        음성 파일을 텍스트로 변환합니다 (파일 업로드용).
        
        Args:
            audio_data: 음성 파일 바이트 데이터
            content_type: 오디오 파일 타입
            
        Returns:
            dict: {
                "text": "변환된 텍스트",
                "language": "ko-KR"
            }
        """
        try:
            # Nova Sonic 모델 호출
            response = self.client.invoke_model(
                modelId=self.model_id,
                contentType=content_type,
                accept="application/json",
                body=audio_data
            )
            
            # 응답 파싱
            response_body = json.loads(response['body'].read())
            
            logger.info(f"STT 변환 성공: {len(audio_data)} bytes")
            
            return {
                "text": response_body.get("transcript", ""),
                "language": response_body.get("language", "ko-KR")
            }
            
        except Exception as e:
            logger.error(f"STT 변환 실패: {e}")
            raise Exception(f"음성 변환 중 오류가 발생했습니다: {str(e)}")

# 싱글톤 인스턴스
stt_service = STTService()
