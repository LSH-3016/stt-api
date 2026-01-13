# STT Service - Project Overview

## 프로젝트 개요

실시간 음성-텍스트 변환(Speech-to-Text) 마이크로서비스입니다. 사용자가 마이크로 말하면 실시간으로 텍스트로 변환되어 화면에 표시됩니다.

## 아키텍처

```
┌─────────────┐     WebSocket      ┌─────────────┐     Streaming     ┌─────────────────────┐
│  Frontend   │ ◄───────────────► │  STT API    │ ◄───────────────► │ Amazon Transcribe   │
│  (React)    │   PCM 16kHz       │  (FastAPI)  │                   │ Streaming           │
└─────────────┘                   └─────────────┘                   └─────────────────────┘
                                        │
                                        │ 파일 업로드
                                        ▼
                                  ┌─────────────┐
                                  │     S3      │
                                  └─────────────┘
```

## 기술 스택

| 구분 | 기술 |
|------|------|
| Backend | FastAPI, Python 3.11 |
| STT Engine | Amazon Transcribe Streaming |
| Storage | Amazon S3 (파일 업로드용) |
| Container | Docker |
| Orchestration | Amazon EKS |
| CI/CD | GitHub Actions + ArgoCD |
| Infrastructure | AWS (EKS, ECR, S3, IAM) |

## 프로젝트 구조

```
stt-api/
├── main.py                 # FastAPI 앱 진입점
├── routers/
│   └── stt.py              # STT 라우터 (WebSocket, REST)
├── services/
│   └── stt.py              # Transcribe 서비스 로직
├── schemas/
│   └── stt.py              # Pydantic 스키마
├── k8s/
│   ├── k8s-deployment.yaml # K8s Deployment, Service, ServiceAccount
│   └── k8s-ingress.yaml    # Ingress 설정
├── .github/workflows/
│   └── deploy.yml          # GitHub Actions CI/CD
├── Dockerfile              # 컨테이너 이미지
├── requirements.txt        # Python 의존성
└── argocd-application.yaml # ArgoCD 앱 설정
```

## 핵심 기능

### 1. 실시간 STT (WebSocket)
- 브라우저에서 마이크 입력을 실시간으로 텍스트 변환
- Partial results로 말하는 중에도 텍스트 표시
- 16kHz PCM 오디오 스트리밍

### 2. 파일 업로드 STT
- WAV, MP3 등 오디오 파일 업로드
- S3 임시 저장 후 Transcribe 배치 처리
- 최대 5MB, 30초 타임아웃

## 데이터 흐름

### 실시간 STT
1. 프론트엔드에서 마이크 캡처 (16kHz, 모노, PCM)
2. WebSocket으로 오디오 청크 전송 (128ms 간격)
3. 백엔드에서 Transcribe Streaming으로 전달
4. Partial/Final 결과를 WebSocket으로 실시간 응답
5. 프론트엔드에서 텍스트 표시 (partial은 덮어쓰기)

### 파일 업로드 STT
1. 프론트엔드에서 파일 업로드
2. 백엔드에서 S3에 임시 저장
3. Transcribe 배치 작업 시작
4. 완료 대기 후 결과 반환
5. S3 파일 및 작업 정리

## 배포 파이프라인

```
Git Push → GitHub Actions → ECR Push → ArgoCD Sync → EKS Deploy
```

1. `main` 브랜치에 push
2. GitHub Actions가 Docker 이미지 빌드 및 ECR push
3. k8s manifest의 이미지 태그 자동 업데이트
4. ArgoCD가 변경 감지 후 EKS에 자동 배포

## AWS 리소스

| 리소스 | 이름/ARN |
|--------|----------|
| EKS Cluster | fproject-dev-eks |
| ECR Repository | stt-api |
| S3 Bucket | stt-audio-324547056370 |
| IAM Role (IRSA) | stt-api-secrets-role |
| IAM Role (Node) | fproject-dev-eks-node-role |

## IAM 권한

### stt-api-secrets-role (IRSA)
- `transcribe:StartStreamTranscription`
- `transcribe:StartTranscriptionJob`
- `transcribe:GetTranscriptionJob`
- `transcribe:DeleteTranscriptionJob`
- `s3:PutObject`, `s3:GetObject`, `s3:DeleteObject`

## 환경별 설정

| 환경 | URL | 인증 |
|------|-----|------|
| Local | http://localhost:32100 | AWS 환경변수 |
| Production | https://stt.aws11.shop | IRSA |

## 관련 문서

- [API.md](API.md) - API 상세 문서
- [DEPLOYMENT.md](DEPLOYMENT.md) - 배포 가이드
- [README.md](README.md) - 빠른 시작
