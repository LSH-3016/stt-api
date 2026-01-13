# STT Service

Amazon Transcribe Streaming을 사용한 실시간 Speech-to-Text 마이크로서비스

## 빠른 시작

### 로컬 실행

```bash
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker 실행

```bash
docker build -t stt-service:latest .
docker run -p 8000:8000 --env-file .env stt-service:latest
```

## API 엔드포인트

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/stt/stream` | WebSocket | 실시간 음성 스트리밍 STT |
| `/stt/transcribe` | POST | 파일 업로드 STT |
| `/health` | GET | 서비스 상태 확인 |

자세한 API 문서는 [API.md](API.md) 참고

## 실시간 STT 사용 예시

```javascript
const ws = new WebSocket('wss://api.aws11.shop/stt/stream');

ws.onmessage = (event) => {
  const { text, is_final } = JSON.parse(event.data);
  if (is_final) {
    console.log('최종:', text);
  } else {
    console.log('중간:', text);
  }
};

// 16kHz PCM 오디오 전송
ws.send(audioChunk);
```

## 환경변수

```env
AWS_REGION=us-east-1
S3_BUCKET_NAME=stt-audio-324547056370
ALLOWED_ORIGINS=*
```

프로덕션(EKS)에서는 IRSA로 AWS 자격증명 자동 주입

## 배포

```bash
# main 브랜치 push → GitHub Actions → ECR → ArgoCD → EKS
git push origin main
```

프로덕션 URL: https://api.aws11.shop/stt

자세한 배포 가이드는 [DEPLOYMENT.md](DEPLOYMENT.md) 참고

## 기술 스택

- FastAPI + WebSocket
- Amazon Transcribe Streaming
- EKS + ArgoCD
- GitHub Actions CI/CD
