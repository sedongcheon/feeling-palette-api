# Feeling Palette API - 문서 가이드

React Native 감정일기 앱 "Feeling Palette"의 백엔드 API 서버 문서입니다.
FastAPI + LangChain + Gemini 기반으로 일기 텍스트를 감정 분석합니다.

## 문서 목차

| # | 문서 | 내용 |
|---|------|------|
| 01 | [API 명세](01-api-specification.md) | 엔드포인트, 요청/응답 스키마, 감정-컬러 매핑 |
| 02 | [Gemini API 설정](02-gemini-api-setup.md) | Google AI Studio 키 발급, 프로젝트에서 API 활성화 |
| 03 | [로컬 개발 환경](03-local-development.md) | 가상환경, Docker Desktop, 로컬 실행/테스트 |
| 04 | [NAS 배포 (현재 운영)](04-nas-deployment.md) | Synology NAS + Docker + Jenkins + GitLab CI/CD |
| 05 | [AWS 계정 설정](05-aws-setup.md) | 계정 생성, IAM, MFA, CLI, Budget 알람 |
| 06 | [AWS Lambda 마이그레이션](06-aws-lambda-migration.md) | ECR, Lambda 컨테이너, API Gateway, 커스텀 도메인 |

## 빠른 시작

**로컬에서 API 서버 실행**:
```bash
cd feelingPaletteAgent
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
echo "GEMINI_API_KEY=AIza..." > .env
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

| 환경 | URL | 상태 |
|------|-----|------|
| 로컬 개발 | http://localhost:8080 | - |
| NAS (운영) | https://feeling-api.sedoli.cloud | ✅ 운영 중 |
| AWS Lambda (검증용) | https://feeling-api-aws.sedoli.co.kr | ✅ 병행 운영 |

## 기여자

- sdchun (sedong1000@gmail.com)
