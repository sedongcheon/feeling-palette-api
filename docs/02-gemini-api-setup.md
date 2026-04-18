# 02. Gemini API 설정

Google의 Gemini API를 LangChain을 통해 호출합니다.
여기서는 API 키 발급과 활성화 절차를 설명합니다.

## 모델 선택

현재 사용 모델: **`gemini-2.5-flash-lite`**

| 항목 | 값 |
|------|------|
| 입력 가격 | $0.10 / 1M tokens |
| 출력 가격 | $0.40 / 1M tokens |
| 월 1,000건 예상 비용 | 약 $0.14 (약 200원) |
| 무료 티어 | 분당 15, 일 1,000 요청 |

> ⚠️ `gemini-2.0-flash-lite`는 신규 사용자에게 더 이상 제공되지 않습니다.
> 반드시 `2.5-flash-lite` 이상을 사용하세요.

## API 키 종류 이해하기

Gemini를 호출할 수 있는 API 키는 크게 2가지 종류가 있고, 접두사로 구분됩니다.

| 구분 | AI Studio 키 | Service Account Bound 키 |
|------|---------|---------|
| **형식** | `AIzaSy...` | `AQ.Ab8...` |
| **발급 경로** | aistudio.google.com/apikey | Google Cloud Console |
| **지원 API** | Gemini Developer API | Vertex AI + Gemini API |
| **소속 프로젝트** | AI Studio가 내부 관리 | **사용자의 Google Cloud 프로젝트에 명시적으로 소속** |
| **결제 단위** | AI Studio 계정 | **Google Cloud 프로젝트별** |
| **용도** | 개인 개발/테스트 | **실서비스/프로덕션** |
| **IAM 관리** | 불가 | **가능** (서비스 계정 바인딩) |

실서비스에는 **Service Account Bound 키**를 쓰는 것이 올바른 구조입니다. 현재 이 프로젝트는 후자를 사용합니다:
- 프로젝트 ID: `feeling-palette`
- 서비스 계정: `vertex-express@feeling-palette.iam.gserviceaccount.com`

## API 키 발급

### 방법 A: Google AI Studio (빠른 개발/테스트용)

1. https://aistudio.google.com/apikey 접속
2. Google 계정으로 로그인
3. **Create API key** 클릭
4. 프로젝트 선택:
   - **Create API key in new project**: 새 Google Cloud 프로젝트 자동 생성
   - Create API key in existing project: 기존 프로젝트 선택
5. 발급된 키 복사 (`AIzaSy...`로 시작)

### 방법 B: Google Cloud Console — Service Account Bound 키 (프로덕션 권장)

1. https://console.cloud.google.com 접속
2. 프로젝트 선택 (또는 신규 생성, 예: `feeling-palette`)
3. **APIs & Services → Library** → `Generative Language API` 검색 → **Enable**
4. **IAM & Admin → Service Accounts** → **Create Service Account**
   - 이름: `vertex-express` (예시)
   - Role: `Vertex AI User` 또는 적절한 권한
5. **APIs & Services → Credentials** → **Create credentials → API key**
6. 생성된 키 클릭 → **API 키 수정 화면**에서:
   - **Authenticate API calls through a service account** 옵션 선택
   - 방금 만든 service account 바인딩
7. 발급된 키 복사 (`AQ.Ab8...`로 시작)
8. (권장) **API restrictions → Restrict key** → `Generative Language API`만 체크

## 키 제약사항 설정 (권장)

API 키 유출 시 피해 최소화를 위해 제약을 걸어두세요.

1. Google Cloud Console → **Credentials** → 해당 API 키 클릭
2. **API restrictions**:
   - **Restrict key** 선택
   - **Generative Language API** 만 체크
3. **Application restrictions** (선택):
   - IP addresses 제한 가능 (서버 IP만 허용)
   - 단, Lambda처럼 IP가 바뀌는 환경에서는 제한 X
4. **Save**

## 프로젝트에서 API 활성화 확인

"**403 PERMISSION_DENIED**" 에러가 난다면 Gemini API가 비활성화 상태.

에러 메시지에서 제공하는 활성화 URL로 접속하여 Enable:
```
https://console.developers.google.com/apis/api/generativelanguage.googleapis.com/overview?project=<PROJECT_NUMBER>
```

활성화 후 **5~10분 대기** (전파 시간).

## 환경변수 설정

### 로컬 개발
`.env` 파일 (프로젝트 루트):
```
GEMINI_API_KEY=AQ.Ab8...      # Service Account Bound 키
# 또는
GEMINI_API_KEY=AIzaSy...      # AI Studio 키
```
LangChain은 둘 다 `google_api_key` 파라미터로 동일하게 받습니다.

### NAS (Jenkins)
Jenkins → **Manage Credentials** → **Add Credentials**:
- Kind: Secret text
- ID: `gemini-api-key`
- Secret: 발급받은 키

### AWS Lambda
Lambda 콘솔 → **Configuration → Environment variables**:
- Key: `GEMINI_API_KEY`
- Value: 발급받은 키

또는 SSM Parameter Store (권장, Phase 2 적용됨):
```bash
aws ssm put-parameter \
  --name /feeling-palette/gemini-api-key \
  --value "AQ.Ab8..." \
  --type SecureString \
  --region ap-northeast-2
```
SAM + GitHub Actions 배포 시 이 파라미터를 자동으로 읽어 Lambda 환경변수에 주입.

## 무료 티어 vs 유료 티어

| 티어 | 학습 데이터 사용 | 비용 | 분당 요청 | 일 요청 |
|------|--------|------|-----------|---------|
| Free | ✅ **사용됨** | $0 | 15 | 1,000 |
| Paid (Billing 연동) | ❌ **사용 안 함** | 사용량만큼 | 수천 | 제한 없음 |

**감정일기는 매우 개인적인 내용**이므로 실서비스는 반드시 Paid 전환 권장.
Google 정책: *"We don't use prompts or responses from paid services to improve our products."*
참조: https://ai.google.dev/gemini-api/terms

### Paid 전환 절차 (실제 진행한 예시)

현재 이 프로젝트(`feeling-palette`)에서 진행한 실제 단계:

#### 1. 프로젝트 ID 확인

API 키가 속한 Google Cloud 프로젝트 확인:
- Google Cloud Console → **API 및 서비스 → Credentials** → 해당 API 키 클릭
- 상단 프로젝트 이름, 또는 URL의 `?project=<id>` 확인 (예: `project=feeling-palette`)
- Service Account Bound 키라면 "바인딩된 계정"에 `@<project-id>.iam.gserviceaccount.com` 형식으로 표시됨

#### 2. Billing 계정 연결

바로 가기 URL: `https://console.cloud.google.com/billing?project=<PROJECT_ID>`

**결제 계정이 없을 경우**:
1. **Manage billing accounts** → **Add billing account**
2. 결제 프로필 생성:
   - 계정 유형: **개인 (Individual)**
   - 이름, 주소
   - **신용/체크카드** 등록 (해외결제 가능한 카드)
3. 생성 완료 후 **Link to project** → 해당 프로젝트 선택

**이미 결제 계정이 있을 경우**:
- 해당 계정 선택 → **Set account**

#### 3. Billing 활성화 확인

`https://console.cloud.google.com/home/dashboard?project=<PROJECT_ID>` 접속하여 **결제 (Billing) 카드** 확인:
- ✅ 결제 기간, 예상 요금 (예: ₩1)이 표시됨 → **Billing 정상 연결**
- ❌ "Billing is disabled" 표시 → 연결 필요

#### 4. 예산 알람 설정 (권장)

`https://console.cloud.google.com/billing/budgets`
- **Create budget**
- 예산: $5/월 (소규모 프로젝트 기준)
- 알림: 50%, 90%, 100%
- 수신 이메일

#### 5. Free Trial 크레딧

신규 Google Cloud 계정은 **$300 × 90일 trial** 자동 부여:
- `https://console.cloud.google.com/billing` → **크레딧** 섹션 확인
- 감정일기 월 1,000건 기준 → 크레딧만으로 수년 사용 가능 수준

## LangChain 사용

### 설치
```
langchain-google-genai>=2.0.0
```

### 코드 (config.py)
```python
from langchain_google_genai import ChatGoogleGenerativeAI

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    max_output_tokens=512,
    google_api_key=os.getenv("GEMINI_API_KEY"),
    timeout=30,
)
```

### Structured Output
```python
structured_llm = llm.with_structured_output(AnalyzeResponse)
result = await structured_llm.ainvoke(messages)
```

LangChain이 Gemini의 JSON mode를 활용하여 Pydantic 모델로 직접 파싱합니다.

## 트러블슈팅

| 에러 | 원인 | 해결 |
|------|------|------|
| `403 PERMISSION_DENIED` | Gemini API 비활성화 | 해당 프로젝트에서 API Enable |
| `404 NOT_FOUND: ... no longer available` | 구버전 모델 사용 | `gemini-2.5-flash-lite`로 변경 |
| `401 UNAUTHORIZED` | API 키 잘못됨 | 키 재발급 또는 복사 오류 확인 |
| `429 RESOURCE_EXHAUSTED` | 무료 티어 rate limit | Paid 전환 또는 요청 빈도 조절 |

## 참고 링크

- Google AI Studio: https://aistudio.google.com/apikey
- Gemini API 문서: https://ai.google.dev/gemini-api/docs
- 모델 가격: https://ai.google.dev/pricing
- LangChain Google GenAI: https://python.langchain.com/docs/integrations/chat/google_generative_ai/
