# Feeling Palette API - 배포 가이드

## 개요

Feeling Palette AI 감정일기 앱의 백엔드 API 서버.
React Native 앱에서 일기 텍스트를 보내면, LangChain + Gemini를 통해 감정 분석 결과를 반환한다.

## 기술 스택

- Python 3.11+ / FastAPI / Uvicorn
- LangChain + langchain-google-genai (Gemini 2.0 Flash-Lite)
- Pydantic v2
- Docker / Jenkins CI/CD
- Synology NAS 배포

## 아키텍처

```
[React Native 앱]
    ↓ POST /api/diary/analyze
[feeling-api.sedoli.cloud] (HTTPS, 443)
    ↓ Synology 역방향 프록시
[localhost:8100] (Docker 컨테이너)
    ↓ 컨테이너 내부 8080
[FastAPI + LangChain]
    ↓ ChatGoogleGenerativeAI
[Gemini API]
```

## 프로젝트 구조

```
feelingPaletteAgent/
├── main.py                # FastAPI 앱 (엔트리포인트)
├── config.py              # 환경변수 로드, ChatGoogleGenerativeAI 설정
├── models.py              # Pydantic 요청/응답 모델
├── service.py             # LangChain 감정 분석 로직
├── requirements.txt       # Python 의존성
├── Dockerfile             # Docker 이미지 빌드
├── docker-compose.yml     # Docker Compose 설정 (포트 8100:8080)
├── Jenkinsfile            # Jenkins CI/CD 파이프라인
├── .env                   # Gemini API 키 (git 제외)
├── .gitignore
└── docs/
    └── deployment-guide.md
```

## API 엔드포인트

### POST /api/diary/analyze

**Request:**
```json
{
  "content": "오늘 하루도 힘들었어. 회사에서 야근하고 집에 오니까 너무 지쳤다."
}
```
- content: 일기 텍스트 (1~1000자, 빈 문자열 불가)

**Response (200):**
```json
{
  "primary_emotion": "sadness",
  "emotions": {
    "joy": 5,
    "sadness": 75,
    "anger": 15,
    "anxiety": 30,
    "calm": 5,
    "excitement": 0
  },
  "comment": "힘든 하루를 보내셨군요. 오늘 하루 고생한 자신을 토닥여주세요.",
  "color": "#4A90D9"
}
```

**감정-컬러 매핑:**
| 감정 | 영문 | 컬러 |
|------|------|-------|
| 기쁨 | joy | #FFD700 |
| 슬픔 | sadness | #4A90D9 |
| 분노 | anger | #E74C3C |
| 불안 | anxiety | #9B59B6 |
| 평온 | calm | #2ECC71 |
| 설렘 | excitement | #FF69B4 |

**Error Response (400):**
```json
{ "error": "일기 내용이 비어있습니다." }
```

**Error Response (500):**
```json
{ "error": "감정 분석 중 오류가 발생했습니다." }
```

---

## 배포 환경

- **GitLab**: https://git.sedoli.cloud/sdchun/feeling-palette-api.git
- **API 도메인**: https://feeling-api.sedoli.cloud
- **Docker 포트**: 8100 (호스트) → 8080 (컨테이너)
- **CI/CD**: GitLab → Webhook → Jenkins → Docker Build → 배포

## 배포 설정 절차

### 1. Jenkins 설정

#### Credential 등록 (Gemini API Key)
1. https://aistudio.google.com/apikey 에서 API 키 발급
2. Jenkins → **Manage Jenkins** → **Credentials** → **(global)** → **Add Credentials**
3. Kind: **Secret text**
4. Secret: Gemini API 키
5. ID: `gemini-api-key`

#### Credential 등록 (GitLab Access Token)
1. GitLab → 프로필 → **Edit Profile** → **Access Tokens**
2. Token name: `jenkins`, Scopes: `read_repository`
3. Jenkins → **Add Credentials**
4. Kind: **Username with password**
5. Username: `sdchun`, Password: 위 토큰
6. ID: `gitlab-credentials`

#### Pipeline 생성
1. **새로운 Item** → 이름: `feeling-palette-api` → **Pipeline**
2. **Build Triggers**: **Build when a change is pushed to GitLab** 체크 → webhook URL 메모
3. **Pipeline**:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://git.sedoli.cloud/sdchun/feeling-palette-api.git`
   - Credentials: `gitlab-credentials`
   - Branch: `*/main`
   - Script Path: `Jenkinsfile`

### 2. GitLab Webhook 설정

1. GitLab 프로젝트 → **Settings** → **Webhooks**
2. URL: Jenkins webhook URL (1단계에서 메모한 것)
3. Trigger: **Push events** (Branch: `main`)
4. SSL verification: 비활성화 (내부망)

### 3. Synology 역방향 프록시

**제어판** → **로그인 포털** → **고급** → **역방향 프록시** → **생성**:

| 항목 | 값 |
|------|------|
| 설명 | `feeling-palette-api` |
| 소스 프로토콜 | HTTPS |
| 소스 호스트 | `feeling-api.sedoli.cloud` |
| 소스 포트 | 443 |
| 대상 프로토콜 | HTTP |
| 대상 호스트 | `localhost` |
| 대상 포트 | `8100` |

### 4. DNS 설정

`feeling-api.sedoli.cloud` → NAS 외부 IP (A 레코드 또는 CNAME)

### 5. SSL 인증서

**제어판** → **보안** → **인증서**에서 `feeling-api.sedoli.cloud` 도메인용 Let's Encrypt 인증서 발급

### 6. React Native 앱 연동

앱 설정 화면에서 서버 URL을 `https://feeling-api.sedoli.cloud`로 변경

---

## CI/CD 파이프라인 흐름

```
git push → GitLab → Webhook → Jenkins Pipeline
  1. Checkout (코드 체크아웃)
  2. Build (docker compose build --no-cache)
  3. Deploy (docker compose down → up -d)
  4. Health Check (curl /docs 엔드포인트)
  5. Cleanup (미사용 이미지 정리)
```

## 로컬 개발

```bash
# 가상환경
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# .env 파일에 API 키 설정
echo "GEMINI_API_KEY=AIza..." > .env

# 서버 실행
uvicorn main:app --host 0.0.0.0 --port 8080 --reload

# 테스트
curl -X POST http://localhost:8080/api/diary/analyze \
  -H "Content-Type: application/json" \
  -d '{"content": "오늘 날씨가 좋아서 기분이 좋았다."}'
  
curl -X POST https://feeling-api.sedoli.cloud/api/diary/analyze \
  -H "Content-Type: application/json" \
  -d '{"content": "오늘 날씨가 좋아서 기분이 좋았다."}'  

```
