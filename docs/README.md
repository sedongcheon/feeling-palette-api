# Feeling Palette API - 문서 가이드

React Native 감정일기 앱 "Feeling Palette"의 백엔드 API 서버 문서입니다.
FastAPI + LangChain + Gemini 기반으로 일기 텍스트를 감정 분석합니다.

## 문서 목차

| # | 문서 | 내용 |
|---|------|------|
| 01 | [API 명세](01-api-specification.md) | 엔드포인트, 요청/응답 스키마, 감정-컬러 매핑 |
| 02 | [Gemini API 설정](02-gemini-api-setup.md) | 키 종류 비교(AI Studio vs Service Account), 발급, Billing/유료 전환 |
| 03 | [로컬 개발 환경](03-local-development.md) | 가상환경, Docker Desktop, 로컬 실행/테스트 |
| 04 | [NAS 배포 (현재 운영)](04-nas-deployment.md) | Synology NAS + Docker + Jenkins + GitLab CI/CD |
| 05 | [AWS 계정 설정](05-aws-setup.md) | 계정 생성, IAM, MFA, CLI, Budget 알람 |
| 06 | [AWS Lambda 마이그레이션](06-aws-lambda-migration.md) | ECR, Lambda(arm64), API Gateway, 커스텀 도메인, SAM IaC, GitHub Actions CI/CD |
| 07 | [CloudWatch 알람](07-cloudwatch-alarms.md) | SNS + CloudWatch 알람을 SAM으로 관리, 에러율/응답시간 모니터링 |

## 빠른 시작

**로컬에서 API 서버 실행**:
```bash
cd feelingPaletteAgent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=AQ.Ab8..." > .env   # Service Account Bound 키 권장
uvicorn main:app --reload --port 8080
```

**API 호출**:
```bash
curl -X POST http://localhost:8080/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"오늘 기분이 좋았다"}'
```

## 프로젝트 구조

```
feelingPaletteAgent/
├── main.py                # FastAPI 엔트리포인트
├── config.py              # LLM 설정 (Gemini)
├── service.py             # LangChain 감정 분석 로직
├── models.py              # Pydantic 스키마
├── lambda_handler.py      # AWS Lambda Mangum 어댑터
├── requirements.txt
├── Dockerfile             # NAS용 (uvicorn)
├── Dockerfile.lambda      # AWS Lambda용
├── docker-compose.yml
├── Jenkinsfile            # NAS CI/CD
└── docs/                  # 이 디렉토리
```

## 배포 환경

| 환경 | URL | 배포 방식 | 아키텍처 |
|------|-----|---------|---------|
| 로컬 개발 | http://localhost:8080 | uvicorn | Host |
| NAS (기존 운영) | https://feeling-api.sedoli.cloud | Jenkins + GitLab | x86_64 (NAS) |
| **AWS Lambda (신규)** | https://feeling-api-aws.sedoli.co.kr | **GitHub Actions + SAM** | **arm64 (Graviton2)** |

## Gemini 설정

- 모델: `gemini-2.5-flash-lite`
- API 키 종류: **Service Account Bound** (`AQ.Ab8...`), 프로젝트: `feeling-palette`
- 티어: **유료 (Paid)** — 사용자 일기가 학습에 사용되지 않음

## 기여자

- sdchun (sedong1000@gmail.com)
