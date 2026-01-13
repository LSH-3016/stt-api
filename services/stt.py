import boto3
import json
import os
import logging
import asyncio
import uuid
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent

logger = logging.getLogger(__name__)

class TranscriptHandler(TranscriptResultStreamHandler):
    """Transcribe 스트리밍 결과 핸들러"""
    def __init__(self, stream):
        super().__init__(stream)
        self.transcript_text = ""
    
    async def handle_transcript_event(self, transcript_event: TranscriptEvent):
        results = transcript_event.transcript.results
        for result in results:
            if not result.is_partial:
                for alt in result.alternatives:
                    self.transcript_text += alt.transcript + " "

class STTService:
    def __init__(self):
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self._s3_client = None
        self._transcribe_client = None
        self.bucket_name = os.getenv('S3_BUCKET_NAME', 'stt-audio-324547056370')
    
    @property
    def s3_client(self):
        if self._s3_client is None:
            self._s3_client = boto3.client('s3', region_name=self.region)
        return self._s3_client
    
    @property
    def transcribe_client(self):
        if self._transcribe_client is None:
            self._transcribe_client = boto3.client('transcribe', region_name=self.region)
        return self._transcribe_client

    async def transcribe_audio(self, audio_data: bytes, content_type: str = "audio/wav") -> dict:
        """
        음성 데이터를 텍스트로 변환 (Transcribe Streaming 사용)
        """
        try:
            client = TranscribeStreamingClient(region=self.region)
            
            stream = await client.start_stream_transcription(
                language_code="ko-KR",
                media_sample_rate_hz=16000,
                media_encoding="pcm",
            )
            
            handler = TranscriptHandler(stream.output_stream)
            
            # 오디오 데이터 전송
            await stream.input_stream.send_audio_event(audio_chunk=audio_data)
            await stream.input_stream.end_stream()
            
            # 결과 처리
            await handler.handle_events()
            
            return {
                "text": handler.transcript_text.strip(),
                "language": "ko-KR"
            }
            
        except Exception as e:
            logger.error(f"STT 변환 실패: {e}")
            raise Exception(f"음성 변환 중 오류가 발생했습니다: {str(e)}")

    async def transcribe_file(self, audio_data: bytes, content_type: str = "audio/wav") -> dict:
        """
        음성 파일을 텍스트로 변환 (배치 Transcribe - 파일 업로드용)
        """
        job_name = f"stt-job-{uuid.uuid4().hex[:8]}"
        
        ext_map = {
            "audio/wav": "wav", "audio/x-wav": "wav",
            "audio/mp3": "mp3", "audio/mpeg": "mp3",
            "audio/ogg": "ogg", "audio/flac": "flac",
            "audio/m4a": "mp4", "audio/mp4": "mp4",
            "audio/webm": "webm"
        }
        media_format = ext_map.get(content_type, "wav")
        s3_key = f"audio/{job_name}.{media_format}"
        
        try:
            # S3 업로드
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name, Key=s3_key,
                    Body=audio_data, ContentType=content_type
                )
            )
            
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            
            # Transcribe 작업 시작
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.transcribe_client.start_transcription_job(
                    TranscriptionJobName=job_name,
                    Media={'MediaFileUri': s3_uri},
                    MediaFormat=media_format,
                    LanguageCode='ko-KR'
                )
            )
            
            # 완료 대기
            transcript_text = await self._wait_for_transcription(job_name)
            
            return {"text": transcript_text, "language": "ko-KR"}
            
        finally:
            # 정리
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                )
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                )
            except: pass

    async def _wait_for_transcription(self, job_name: str, max_wait: int = 60) -> str:
        """Transcribe 작업 완료 대기"""
        import urllib.request
        
        for _ in range(max_wait):
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.transcribe_client.get_transcription_job(TranscriptionJobName=job_name)
            )
            
            status = response['TranscriptionJob']['TranscriptionJobStatus']
            
            if status == 'COMPLETED':
                transcript_uri = response['TranscriptionJob']['Transcript']['TranscriptFileUri']
                with urllib.request.urlopen(transcript_uri) as resp:
                    result = json.loads(resp.read().decode())
                    transcripts = result.get('results', {}).get('transcripts', [])
                    return transcripts[0].get('transcript', '') if transcripts else ''
                    
            elif status == 'FAILED':
                raise Exception(f"Transcribe 실패: {response['TranscriptionJob'].get('FailureReason')}")
            
            await asyncio.sleep(1)
        
        raise Exception("Transcribe 타임아웃")

# 싱글톤 인스턴스
stt_service = STTService()
