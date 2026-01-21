# STT Service EKS 배포 가이드

## 사전 준비

### 1. GitHub Secrets 설정

GitHub 저장소의 Settings > Secrets and variables > Actions에서 다음 Secrets를 추가:

```
AWS_ACCESS_KEY_ID: <AWS Access Key>
AWS_SECRET_ACCESS_KEY: <AWS Secret Key>
```

**권한 요구사항:**
- ECR: `ecr:GetAuthorizationToken`, `ecr:BatchCheckLayerAvailability`, `ecr:PutImage`, `ecr:InitiateLayerUpload`, `ecr:UploadLayerPart`, `ecr:CompleteLayerUpload`
- 또는 간단하게: `AmazonEC2ContainerRegistryPowerUser` 정책 연결

### 2. AWS 리소스 생성

#### IAM Role 생성 (stt-api-secrets-role)
```bash
# Trust Policy 생성
cat > trust-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {
        "Federated": "arn:aws:iam::324547056370:oidc-provider/oidc.eks.ap-northeast-2.amazonaws.com/id/YOUR_OIDC_ID"
      },
      "Action": "sts:AssumeRoleWithWebIdentity",
      "Condition": {
        "StringEquals": {
          "oidc.eks.ap-northeast-2.amazonaws.com/id/YOUR_OIDC_ID:sub": "system:serviceaccount:default:stt-api-sa"
        }
      }
    }
  ]
}
EOF

# IAM Role 생성
aws iam create-role \
  --role-name stt-api-secrets-role \
  --assume-role-policy-document file://trust-policy.json

# Transcribe 및 S3 권한 정책 생성
cat > stt-api-policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "transcribe:StartStreamTranscription",
        "transcribe:StartTranscriptionJob",
        "transcribe:GetTranscriptionJob",
        "transcribe:DeleteTranscriptionJob"
      ],
      "Resource": "*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject"
      ],
      "Resource": "arn:aws:s3:::stt-audio-324547056370/*"
    },
    {
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": "arn:aws:s3:::stt-audio-324547056370"
    }
  ]
}
EOF

# 정책 생성 및 Role에 연결
aws iam create-policy \
  --policy-name stt-api-policy \
  --policy-document file://stt-api-policy.json

aws iam attach-role-policy \
  --role-name stt-api-secrets-role \
  --policy-arn arn:aws:iam::324547056370:policy/stt-api-policy
```

#### ECR 저장소 생성
```bash
aws ecr create-repository \
  --repository-name stt-api \
  --region ap-northeast-2
```

### 2. Docker 이미지 빌드 및 푸시

#### 자동 배포 (GitHub Actions - 권장)

```bash
# main 브랜치에 푸시하면 자동으로 ECR에 배포됨
git add .
git commit -m "feat: add new feature"
git push origin main

# GitHub Actions에서 자동으로:
# 1. Docker 이미지 빌드
# 2. ECR에 푸시 (v{run_number}, latest 태그)
# 3. k8s/k8s-deployment.yaml 이미지 태그 업데이트
# 4. ArgoCD가 자동으로 EKS에 배포
```

#### 수동 배포 (로컬)

```bash
# ECR 로그인
aws ecr get-login-password --region ap-northeast-2 | docker login --username AWS --password-stdin 324547056370.dkr.ecr.ap-northeast-2.amazonaws.com

# 이미지 빌드
docker build -t stt-api:latest .

# 이미지 태그
docker tag stt-api:latest 324547056370.dkr.ecr.ap-northeast-2.amazonaws.com/stt-api:latest

# 이미지 푸시
docker push 324547056370.dkr.ecr.ap-northeast-2.amazonaws.com/stt-api:latest
```

### 3. Route53 DNS 설정

```bash
# api.aws11.shop 도메인을 ALB에 연결
# Route53 콘솔에서 A 레코드 생성:
# - 이름: api.aws11.shop
# - 타입: A - IPv4 address
# - 별칭: Yes
# - 별칭 대상: one-api-alb (통합 ALB)
```

## 배포 방법

### 방법 1: ArgoCD 사용 (권장)

1. **GitHub 저장소 설정**
   ```bash
   # argocd-application.yaml에서 repoURL 수정
   # repoURL: https://github.com/YOUR_USERNAME/stt-service.git
   ```

2. **ArgoCD Application 생성**
   ```bash
   kubectl apply -f argocd-application.yaml
   ```

3. **ArgoCD UI에서 확인**
   ```bash
   # ArgoCD UI 접속
   # https://argocd.your-domain.com
   
   # 또는 CLI로 확인
   argocd app get stt-api
   argocd app sync stt-api
   ```

### 방법 2: kubectl 직접 배포

```bash
# Deployment, Service, ServiceAccount 배포
kubectl apply -f k8s/k8s-deployment.yaml

# Ingress 배포
kubectl apply -f k8s/k8s-ingress.yaml

# 배포 상태 확인
kubectl get pods -l app=stt-api
kubectl get svc stt-api-service
kubectl get ingress stt-api-ingress
```

## 배포 확인

### 1. Pod 상태 확인
```bash
kubectl get pods -l app=stt-api
kubectl logs -l app=stt-api --tail=100
```

### 2. Service 확인
```bash
kubectl get svc stt-api-service
kubectl describe svc stt-api-service
```

### 3. Ingress 확인
```bash
kubectl get ingress stt-api-ingress
kubectl describe ingress stt-api-ingress
```

### 4. Health Check
```bash
# 로컬 테스트
curl https://api.aws11.shop/stt/health

# 예상 응답:
# {
#   "status": "healthy",
#   "service": "stt",
#   "model": "amazon.nova-2-sonic-v1:0",
#   "streaming": "enabled",
#   "max_file_size_mb": 5,
#   "rate_limit": "10/minute"
# }
```

### 5. API 테스트
```bash
# STT API 테스트
curl -X POST "https://api.aws11.shop/stt/transcribe" \
  -H "Content-Type: multipart/form-data" \
  -F "audio=@test.wav"
```

## 업데이트 배포

### 새 버전 배포
```bash
# 1. 새 이미지 빌드 및 푸시
docker build -t stt-api:v2 .
docker tag stt-api:v2 324547056370.dkr.ecr.ap-northeast-2.amazonaws.com/stt-api:v2
docker push 324547056370.dkr.ecr.ap-northeast-2.amazonaws.com/stt-api:v2

# 2. Deployment 이미지 업데이트
kubectl set image deployment/stt-api stt-api=324547056370.dkr.ecr.ap-northeast-2.amazonaws.com/stt-api:v2

# 3. 롤아웃 상태 확인
kubectl rollout status deployment/stt-api

# 4. 롤백 (필요시)
kubectl rollout undo deployment/stt-api
```

## 스케일링

### 수동 스케일링
```bash
# Pod 개수 조정
kubectl scale deployment stt-api --replicas=3
```

### 자동 스케일링 (HPA)
```bash
# HPA 생성
kubectl autoscale deployment stt-api \
  --cpu-percent=70 \
  --min=2 \
  --max=10

# HPA 상태 확인
kubectl get hpa
```

## 모니터링

### 로그 확인
```bash
# 실시간 로그
kubectl logs -f -l app=stt-api

# 특정 Pod 로그
kubectl logs <pod-name>

# 이전 컨테이너 로그
kubectl logs <pod-name> --previous
```

### 리소스 사용량
```bash
# Pod 리소스 사용량
kubectl top pods -l app=stt-api

# Node 리소스 사용량
kubectl top nodes
```

## 트러블슈팅

### CrashLoopBackOff 오류 (Exit Code 1)
```bash
# 1. Pod 로그 확인
kubectl logs -l app=stt-api --tail=100
kubectl logs <pod-name> --previous  # 이전 컨테이너 로그

# 2. IAM Role 권한 확인
aws iam get-role --role-name stt-api-secrets-role
aws iam list-attached-role-policies --role-name stt-api-secrets-role

# 3. ServiceAccount 확인
kubectl describe sa stt-api-sa
# annotations에 eks.amazonaws.com/role-arn이 올바른지 확인

# 4. OIDC Provider 확인
aws eks describe-cluster --name <cluster-name> --query "cluster.identity.oidc.issuer"

# 5. Transcribe 권한 테스트 (Pod 내부에서)
kubectl exec -it <pod-name> -- python3 -c "
import boto3
client = boto3.client('transcribe', region_name='ap-northeast-2')
print('Transcribe client initialized successfully')
"

# 일반적인 원인:
# - IAM Role의 Trust Policy가 잘못됨 (OIDC Provider ID 불일치)
# - Transcribe Streaming 권한이 없음
# - ServiceAccount annotation이 잘못됨
```

### Pod가 시작되지 않을 때
```bash
# Pod 상태 확인
kubectl describe pod <pod-name>

# 이벤트 확인
kubectl get events --sort-by='.lastTimestamp'

# ServiceAccount 권한 확인
kubectl describe sa stt-api-sa
```

### Ingress가 작동하지 않을 때
```bash
# Ingress 상태 확인
kubectl describe ingress stt-api-ingress

# ALB Controller 로그 확인
kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller

# ALB 생성 확인
aws elbv2 describe-load-balancers --region ap-northeast-2
```

### 503 에러 발생 시
```bash
# Target Group 상태 확인
aws elbv2 describe-target-health \
  --target-group-arn <target-group-arn>

# Pod Health Check 확인
kubectl get pods -l app=stt-api
kubectl logs -l app=stt-api --tail=50
```

## 주요 설정

- **도메인**: api.aws11.shop/stt
- **포트**: 8000
- **Replicas**: 2
- **리소스**:
  - Requests: 256Mi / 100m
  - Limits: 512Mi / 500m
- **Rate Limit**: 10/minute
- **Max File Size**: 5MB
- **Health Check**: /health
- **ALB Group**: one-api-alb (다른 API와 공유)

## 참고사항

1. **ALB 공유**: journal-api와 동일한 ALB(one-api-alb)를 사용하여 비용 절감
2. **HTTPS**: ACM 인증서를 통한 자동 HTTPS 적용
3. **Auto Scaling**: CPU 70% 기준으로 2-10개 Pod 자동 조정 가능
4. **Rolling Update**: 무중단 배포 지원
5. **Health Check**: Liveness/Readiness Probe로 자동 복구
