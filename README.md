# STT Service

Amazon Nova Sonic을 사용한 Speech-to-Text 마이크로서비스

## 🚀 빠른 시작

### 로컬 실행

```bash
# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일 수정

# 서버 실행
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Docker 실행

```bash
# 이미지 빌드
docker build -t stt-service:latest .

# 컨테이너 실행
docker run -p 8000:8000 --env-file .env stt-service:latest
```

## 📡 API 엔드포인트

### 1. 실시간 STT (WebSocket)

```
ws://localhost:8000/stt/stream
```

**JavaScript 예시:**
```javascript
const ws = new WebSocket('ws://localhost:8000/stt/stream');

ws.onopen = () => {
  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      const mediaRecorder = new MediaRecorder(stream);
      mediaRecorder.ondataavailable = (event) => {
        ws.send(event.data);
      };
      mediaRecorder.start(100);
    });
};

ws.onmessage = (event) => {
  const result = JSON.parse(event.data);
  console.log('텍스트:', result.text);
  console.log('전체:', result.full_text);
};
```

### 2. 파일 업로드 STT

```bash
POST /stt/transcribe

curl -X POST "http://localhost:8000/stt/transcribe" \
  -F "audio=@voice.wav"
```

**응답:**
```json
{
  "text": "오늘 아침 7시에 기상했다",
  "language": "ko-KR"
}
```

### 3. Health Check

```bash
GET /health
GET /stt/health
```

## 🔧 환경변수

```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
ALLOWED_ORIGINS=*
```

## 📚 API 문서

서버 실행 후:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 🎯 지원 형식

- **파일**: WAV, MP3, OGG, FLAC, M4A
- **최대 크기**: 10MB
- **권장 설정**: 16kHz, 모노, 16bit

## 🚀 배포

### EKS 배포

```bash
# ECR에 푸시
docker tag stt-service:latest <ecr-url>/stt-service:latest
docker push <ecr-url>/stt-service:latest

# Kubernetes 배포
kubectl apply -f k8s-deployment.yaml
```

## 📝 라이선스

MIT
