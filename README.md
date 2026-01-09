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
uvicorn main:app --reload --host 0.0.0.0 --port 32100
```

### Docker 실행

```bash
# 이미지 빌드
docker build -t stt-service:latest .

# 컨테이너 실행
docker run -p 32100:32100 --env-file .env stt-service:latest
```

## 📡 API 엔드포인트

### 1. 실시간 STT (WebSocket)

```
ws://localhost:32100/stt/stream
```

**JavaScript 예시:**
```javascript
const ws = new WebSocket('ws://localhost:32100/stt/stream');

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

curl -X POST "http://localhost:32100/stt/transcribe" \
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
ALLOWED_ORIGINS=https://www.aws11.shop,https://aws11.shop,https://stt.aws11.shop
DEBUG=False
ENVIRONMENT=production
```

**로컬 개발:**
```env
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
ALLOWED_ORIGINS=*
DEBUG=True
```

**프로덕션 (EKS):**
- AWS 자격증명은 IAM Role (IRSA)로 자동 주입
- 환경변수는 k8s/k8s-deployment.yaml에서 관리

## 📚 API 문서

서버 실행 후:
- Swagger UI: http://localhost:32100/docs
- ReDoc: http://localhost:32100/redoc

**프로덕션:**
- Swagger UI: https://stt.aws11.shop/docs
- ReDoc: https://stt.aws11.shop/redoc

## 🎯 지원 형식

- **파일**: WAV, MP3, OGG, FLAC, M4A, WEBM
- **최대 크기**: 5MB
- **Rate Limit**: 10회/분
- **타임아웃**: 30초
- **권장 설정**: 16kHz, 모노, 16bit

## 🚀 배포

### GitHub Actions 자동 배포 (권장)

1. **GitHub Secrets 설정**
   - Settings > Secrets and variables > Actions
   - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` 추가

2. **자동 배포**
   ```bash
   # main 브랜치에 푸시하면 자동으로 ECR에 배포
   git push origin main
   
   # GitHub Actions가 자동으로:
   # - Docker 이미지 빌드
   # - ECR에 푸시
   # - k8s manifest 업데이트
   # - ArgoCD가 EKS에 자동 배포
   ```

3. **PR 테스트**
   ```bash
   # PR 생성 시 자동으로 테스트 이미지 빌드
   git checkout -b feature/new-feature
   git push origin feature/new-feature
   # PR 생성하면 자동으로 pr-{number} 태그로 빌드
   ```

### 수동 EKS 배포

```bash
# ECR에 푸시
docker tag stt-service:latest 324547056370.dkr.ecr.us-east-1.amazonaws.com/stt-api:latest
docker push 324547056370.dkr.ecr.us-east-1.amazonaws.com/stt-api:latest

# Kubernetes 배포
kubectl apply -f k8s/k8s-deployment.yaml
kubectl apply -f k8s/k8s-ingress.yaml
```

### 배포 상태 확인

```bash
# Pod 상태
kubectl get pods -l app=stt-api

# 서비스 확인
kubectl get svc stt-api-service

# Ingress 확인
kubectl get ingress stt-api-ingress

# 로그 확인
kubectl logs -f -l app=stt-api
```

**프로덕션 URL**: https://stt.aws11.shop

자세한 배포 가이드는 [DEPLOYMENT.md](DEPLOYMENT.md) 참고

## 📝 라이선스

MIT
