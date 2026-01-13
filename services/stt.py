import boto3
import json
import os
import logging
import asyncio
import uuid
from typing import AsyncIterator

logger = logging.getLogger(__name__)

class STTService:
    def __init__(self):
        self._transcribe_client = None
        self._s3_client = None
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'stt-audio-324547056370')
        self.region = os.getenv('AWS_REGION', 'us-east-1')
    
    @property
    def transcribe_client(self):
        """Lazy initialization of Transcribe client"""
        if self._transcribe_client is None:
            try:
                self._transcribe_client = boto3.client(
                    'transcribe',
                    region_name=self.region
                )
                logger.info("Transcribe client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Transcribe client: {e}")
                raise
        return self._transcribe_client
    
    @property
    def s3_client(self):
        """Lazy initialization of S3 client"""
        if self._s3_client is None:
            try:
                self._s3_client = boto3.client(
                    's3',
                    region_name=self.region
                )
                logger.info("S3 client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {e}")
                raise
        return self._s3_client

    async def transcribe_audio(self, audio_data: bytes, content_type: str = "audio/wav") -> dict:
        """
        음성 파일을 텍스트로 변환합니다 (Amazon Transcribe 사용).
        
        Args:
            audio_data: 음성 파일 바이트 데이터
            content_type: 오디오 파일 타입
            
        Returns:
            dict: {"text": "변환된 텍스트", "language": "ko-KR"}
        """
        job_name = f"stt-job-{uuid.uuid4().hex[:8]}"
        
        # content_type에서 확장자 결정
        ext_map = {
            "audio/wav": "wav",
            "audio/x-wav": "wav",
            "audio/mp3": "mp3",
            "audio/mpeg": "mp3",
            "audio/ogg": "ogg",
            "audio/flac": "flac",
            "audio/m4a": "mp4",
            "audio/mp4": "mp4",
            "audio/webm": "webm",
            "audio/pcm": "wav"
        }
        media_format = ext_map.get(content_type, "wav")
        s3_key = f"audio/{job_name}.{media_format}"
        
        try:
            # S3에 오디오 파일 업로드
            logger.info(f"S3 업로드 시작: {s3_key}")
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name,
                    Key=s3_key,
                    Body=audio_data,
                    ContentType=content_type
                )
            )
            
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            logger.info(f"S3 업로드 완료: {s3_uri}")
            
            # Transcribe 작업 시작
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.transcribe_client.start_transcription_job(
                    TranscriptionJobName=job_name,
                    Media={'MediaFileUri': s3_uri},
                    MediaFormat=media_format if media_format != "wav" else "wav",
                    LanguageCode='ko-KR',
                    Settings={
                        'ShowSpeakerLabels': False,
                        'ChannelIdentification': False
                    }
                )
            )
            
            logger.info(f"Transcribe 작업 시작: {job_name}")
            
            # 작업 완료 대기
            transcript_text = await self._wait_for_transcription(job_name)
            
            return {
                "text": transcript_text,
                "language": "ko-KR"
            }
            
        except Exception as e:
            logger.error(f"STT 변환 실패: {e}")
            raise Exception(f"음성 변환 중 오류가 발생했습니다: {str(e)}")
        finally:
            # 정리: S3 파일 삭제
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                )
            except Exception as e:
                logger.warning(f"S3 파일 삭제 실패: {e}")
            
            # 정리: Transcribe 작업 삭제
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None,
                    lambda: self.transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                )
            except Exception as e:
                logger.warning(f"Transcribe 작업 삭제 실패: {e}")

    async def _wait_for_transcription(self, job_name: str, max_wait: int = 60) -> str:
        """Transcribe 작업 완료 대기"""
        for _ in range(max_wait):
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            )
            
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                
                # 결과 파일 다운로드
                import urllib.request
                with urllib.request.urlopen(transcript_uri) as resp:
                    result = json.loads(resp.read().decode())
                    transcripts = result.get('results', {}).get('transcripts', [])
                    if transcripts:
                        return transcripts[0].get('transcript', '')
                    return ''
                    
            elif status == 'FAILED':
                failure_reason = response['TranscriptionJob'].get('FailureReason', 'Unknown')
                raise Exception(f"Transcribe 작업 실패: {failure_reason}")
            
            await asyncio.sleep(1)
        
        raise Exception("Transcribe 작업 타임아웃")

# 싱글톤 인스턴스
stt_service = STTService()
