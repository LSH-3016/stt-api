import boto3
import json
import os
import logging
import asyncio
import uuid

logger = logging.getLogger(__name__)

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

    async def transcribe_file(self, audio_data: bytes, content_type: str = "audio/wav") -> dict:
        """파일 업로드용 배치 Transcribe"""
        job_name = f"stt-job-{uuid.uuid4().hex[:8]}"
        
        ext_map = {
            "audio/wav": "wav", "audio/x-wav": "wav",
            "audio/mp3": "mp3", "audio/mpeg": "mp3",
            "audio/ogg": "ogg", "audio/flac": "flac",
            "audio/m4a": "mp4", "audio/mp4": "mp4", "audio/webm": "webm"
        }
        media_format = ext_map.get(content_type, "wav")
        s3_key = f"audio/{job_name}.{media_format}"
        
        try:
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.s3_client.put_object(
                    Bucket=self.bucket_name, Key=s3_key,
                    Body=audio_data, ContentType=content_type
                )
            )
            
            s3_uri = f"s3://{self.bucket_name}/{s3_key}"
            
            await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: self.transcribe_client.start_transcription_job(
                    TranscriptionJobName=job_name,
                    Media={'MediaFileUri': s3_uri},
                    MediaFormat=media_format,
                    LanguageCode='ko-KR'
                )
            )
            
            transcript_text = await self._wait_for_transcription(job_name)
            return {"text": transcript_text, "language": "ko-KR"}
        finally:
            try:
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.s3_client.delete_object(Bucket=self.bucket_name, Key=s3_key)
                )
                await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.transcribe_client.delete_transcription_job(TranscriptionJobName=job_name)
                )
            except: pass

    async def _wait_for_transcription(self, job_name: str, max_wait: int = 60) -> str:
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

stt_service = STTService()
