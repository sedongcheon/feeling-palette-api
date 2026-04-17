# 03. 로컬 개발 환경

## 요구사항

- Python 3.11+
- Docker Desktop (Lambda 이미지 테스트 시)
- Git
- Gemini API 키 ([02-gemini-api-setup.md](02-gemini-api-setup.md) 참조)

## 초기 세팅

### 1. 저장소 클론

```bash
git clone https://git.sedoli.cloud/sdchun/feeling-palette-api.git
cd feeling-palette-api
```

### 2. Python 가상환경

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. 환경변수

`.env` 파일 생성 (프로젝트 루트):
```
GEMINI_API_KEY=AIzaSy...실제키...
```

`.env`는 `.gitignore`에 포함되어 있어 커밋되지 않습니다.

## 개발 서버 실행

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8080
```

- `--reload`: 코드 변경 시 자동 재시작
- `--port 8080`: 포트 변경 가능

실행 후 접속:
- API: http://localhost:8080
- Swagger UI: http://localhost:8080/docs
- OpenAPI JSON: http://localhost:8080/openapi.json

## 로컬 테스트

### Swagger UI

http://localhost:8080/docs 에서 `POST /api/diary/analyze` 시도하기 → Execute

### curl

```bash
curl -X POST http://localhost:8080/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"오늘 기분이 좋았다"}'
```

### Python 테스트

```python
import httpx
r = httpx.post(
    "http://localhost:8080/api/diary/analyze",
    json={"content": "오늘 기분이 좋았다"},
)
print(r.json())
```

## Docker 로컬 실행

### Docker Desktop 설치

https://www.docker.com/products/docker-desktop/

Apple Silicon Mac: "Mac with Apple chip" 다운로드

설치 후 앱 실행 → 상단 메뉴바에 🐳 아이콘 확인.

### NAS용 이미지 (uvicorn)

```bash
docker compose up --build
```
포트 8100에서 서비스. 확인:
```bash
curl -X POST http://localhost:8100/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"테스트"}'
```

### Lambda용 이미지 (RIE 에뮬레이터)

```bash
docker buildx build --platform linux/amd64 --provenance=false -f Dockerfile.lambda -t feeling-palette-lambda:local .

docker run -d --name lambda-test -p 9000:8080 \
  -e GEMINI_API_KEY="$(grep GEMINI_API_KEY .env | cut -d= -f2)" \
  feeling-palette-lambda:local
```

Lambda 이벤트 형식으로 테스트:
```bash
curl -s -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{
    "version":"2.0",
    "routeKey":"POST /api/diary/analyze",
    "rawPath":"/api/diary/analyze",
    "requestContext":{
      "http":{
        "method":"POST",
        "path":"/api/diary/analyze",
        "sourceIp":"127.0.0.1",
        "userAgent":"curl",
        "protocol":"HTTP/1.1"
      },
      "requestId":"test",
      "stage":"$default",
      "time":"01/Jan/2026:00:00:00 +0000",
      "timeEpoch":1735689600
    },
    "body":"{\"content\":\"테스트\"}",
    "isBase64Encoded":false,
    "headers":{"content-type":"application/json"}
  }'
```

정리:
```bash
docker stop lambda-test && docker rm lambda-test
```

### 주의: Apple Silicon 빌드

Lambda는 기본 x86_64 아키텍처를 사용하므로 M1/M2/M3 Mac에서는 반드시 `--platform linux/amd64` 플래그 필요.

arm64 Lambda를 쓸 경우 `--platform linux/arm64` (20% 저렴하지만 base image 지원 확인 필요).

## Git 워크플로우

### 브랜치 전략

- `main`: 운영 배포 브랜치 (직접 push 금지)
- `release/release`: 개발 통합 브랜치 (여기에 push)

### 배포 순서

```bash
# 1. release/release 브랜치에서 작업
git checkout release/release
git pull

# 2. 변경사항 커밋
git add <files>
git commit -m "설명"
git push origin release/release

# 3. GitLab에서 Merge Request 생성 → main으로 머지
# 4. Jenkins webhook 자동 빌드 → NAS 배포
```

### 커밋 메시지 규칙

- 영문 or 한글 혼용 가능
- 동사 원형으로 시작 (Add/Fix/Update)
- 본문에 why 설명

예:
```
Switch to gemini-2.5-flash-lite

gemini-2.0-flash-lite is no longer available to new users.
Use the current generation flash-lite model instead.
```

## 코드 구조

```
feelingPaletteAgent/
├── main.py              # FastAPI 앱 + CORS + 라우팅
├── config.py            # LLM 인스턴스 생성 (Gemini)
├── service.py           # analyze_diary() 비즈니스 로직
├── models.py            # Pydantic 요청/응답 스키마
├── lambda_handler.py    # AWS Lambda Mangum 어댑터
├── requirements.txt
├── Dockerfile           # NAS용 (uvicorn)
├── Dockerfile.lambda    # Lambda용 (공식 base image)
├── docker-compose.yml   # 로컬 + NAS
├── Jenkinsfile          # CI/CD 파이프라인
├── .env                 # 로컬 환경변수 (gitignore)
└── docs/                # 이 폴더
```

### 주요 파일 역할

**main.py** — FastAPI 진입점:
- CORS 미들웨어 설정
- `POST /api/diary/analyze` 엔드포인트
- 요청 검증 (빈 문자열, 1000자 제한)
- 에러 핸들링

**config.py** — LLM 설정:
- `ChatGoogleGenerativeAI` 인스턴스 생성
- `GEMINI_API_KEY` 환경변수 로드
- `load_dotenv`를 try/except로 감싸 Lambda 호환

**service.py** — 비즈니스 로직:
- 시스템 프롬프트 정의 (한국어 감정 분석 전문가)
- `llm.with_structured_output()`로 Pydantic 파싱
- JSON 파싱 폴백 처리

**models.py** — Pydantic 스키마:
- `AnalyzeRequest`: `content: str`
- `EmotionScores`: 6개 감정 × 0~100
- `AnalyzeResponse`: 전체 응답 구조

**lambda_handler.py** — Lambda 어댑터:
```python
from mangum import Mangum
from main import app
handler = Mangum(app, lifespan="off")
```

## 디버깅 팁

### 로그 레벨 높이기

`main.py` 상단 추가:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### LangChain 호출 추적

`.env`에 추가:
```
LANGCHAIN_VERBOSE=true
```

### FastAPI 자동 reload 안 됨

`uvicorn --reload` 옵션이 빠지지 않았는지 확인.
또는 `.env` 수정 시는 서버 재시작 필요.
