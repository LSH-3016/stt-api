# IAM 정책 설정 가이드

이 디렉토리에는 STT API 서비스가 AWS 리소스에 접근하기 위한 IAM 정책 파일들이 포함되어 있습니다.

> **참고**: 이 서비스는 실시간 스트리밍만 사용하므로 S3 권한이 필요하지 않습니다.

## 파일 설명

- `trust-policy.json`: EKS IRSA(IAM Roles for Service Accounts)를 위한 Trust Policy
- `stt-api-policy.json`: Transcribe Streaming 접근 권한 정책

## 설정 방법

### 1. OIDC Provider ID 확인

```bash
# EKS 클러스터의 OIDC Provider ID 확인
aws eks describe-cluster --name fproject-dev-eks --region ap-northeast-2 \
  --query "cluster.identity.oidc.issuer" --output text

# 출력 예시: https://oidc.eks.ap-northeast-2.amazonaws.com/id/EXAMPLED539D4633E53DE1B71EXAMPLE
# 마지막 부분(EXAMPLED539D4633E53DE1B71EXAMPLE)이 OIDC ID입니다
```

### 2. Trust Policy 수정

`trust-policy.json` 파일에서 `YOUR_OIDC_ID`를 실제 OIDC ID로 변경:

```bash
# 자동으로 변경하려면:
OIDC_ID=$(aws eks describe-cluster --name fproject-dev-eks --region ap-northeast-2 \
  --query "cluster.identity.oidc.issuer" --output text | cut -d '/' -f 5)

sed -i "s/YOUR_OIDC_ID/$OIDC_ID/g" iam/trust-policy.json
```

### 3. IAM Role 생성

```bash
# IAM Role 생성
aws iam create-role \
  --role-name stt-api-secrets-role \
  --assume-role-policy-document file://iam/trust-policy.json \
  --description "STT API 서비스를 위한 IRSA Role (실시간 스트리밍 전용)"

# 정책 생성
aws iam create-policy \
  --policy-name stt-api-policy \
  --policy-document file://iam/stt-api-policy.json \
  --description "STT API의 Transcribe Streaming 접근 권한"

# 정책을 Role에 연결
aws iam attach-role-policy \
  --role-name stt-api-secrets-role \
  --policy-arn arn:aws:iam::324547056370:policy/stt-api-policy
```

### 4. 권한 확인

```bash
# Role 정보 확인
aws iam get-role --role-name stt-api-secrets-role

# 연결된 정책 확인
aws iam list-attached-role-policies --role-name stt-api-secrets-role

# 정책 내용 확인
aws iam get-policy-version \
  --policy-arn arn:aws:iam::324547056370:policy/stt-api-policy \
  --version-id v1
```

## 필요한 권한 설명

### Transcribe 권한
- `transcribe:StartStreamTranscription`: 실시간 음성 스트리밍 변환

> 이 서비스는 실시간 스트리밍만 사용하므로 S3 권한이나 배치 Transcribe 권한은 필요하지 않습니다.

## 트러블슈팅

### AccessDenied 오류
```bash
# Pod에서 권한 테스트
kubectl exec -it <pod-name> -- python3 -c "
from amazon_transcribe.client import TranscribeStreamingClient

# Transcribe Streaming 클라이언트 생성 테스트
client = TranscribeStreamingClient(region='ap-northeast-2')
print('Transcribe Streaming client OK')
"
```

### ServiceAccount 확인
```bash
# ServiceAccount에 Role ARN이 올바르게 설정되었는지 확인
kubectl describe sa stt-api-sa

# 출력에서 다음 annotation 확인:
# eks.amazonaws.com/role-arn: arn:aws:iam::324547056370:role/stt-api-secrets-role
```

## 보안 권장사항

1. **최소 권한 원칙**: 실시간 스트리밍에 필요한 권한만 부여
2. **정기 검토**: 사용하지 않는 권한 제거
3. **CloudTrail 활성화**: API 호출 모니터링
4. **네트워크 보안**: WebSocket 연결에 TLS 사용 (wss://)

## 참고

- 실시간 스트리밍은 메모리에서만 처리되며 파일 저장이 필요하지 않습니다
- 따라서 S3 버킷이나 관련 권한이 필요하지 않습니다
- 더 간단하고 안전한 권한 구조를 유지할 수 있습니다
