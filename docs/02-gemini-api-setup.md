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

## API 키 발급 (추천)

### 방법 A: Google AI Studio (가장 간단)

1. https://aistudio.google.com/apikey 접속
2. Google 계정으로 로그인
3. **Create API key** 클릭
4. 프로젝트 선택:
   - **Create API key in new project**: 새 Google Cloud 프로젝트 자동 생성, Gemini API 자동 활성화 ← **추천**
   - Create API key in existing project: 기존 프로젝트 선택 (아래 활성화 필요)
5. 발급된 키 복사 (`AIzaSy...`로 시작)

### 방법 B: Google Cloud Console

기존 Google Cloud 프로젝트가 있거나 IAM 권한 관리를 세밀히 하고 싶을 때.

1. https://console.cloud.google.com 접속
2. 프로젝트 선택 (또는 신규 생성)
3. **APIs & Services → Library** 이동
4. `Generative Language API` 검색 → **Enable (사용 설정)**
5. **APIs & Services → Credentials** 이동
6. **Create credentials → API key** 클릭
7. 생성된 키 복사
8. (선택) **Restrict key** 클릭 → 사용 가능 API를 `Generative Language API`로 제한

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
GEMINI_API_KEY=AIzaSy...
```

### NAS (Jenkins)
Jenkins → **Manage Credentials** → **Add Credentials**:
- Kind: Secret text
- ID: `gemini-api-key`
- Secret: 발급받은 키

### AWS Lambda
Lambda 콘솔 → **Configuration → Environment variables**:
- Key: `GEMINI_API_KEY`
- Value: 발급받은 키

또는 SSM Parameter Store (권장, Phase 2):
```bash
aws ssm put-parameter \
  --name /feeling-palette/gemini-api-key \
  --value "AIzaSy..." \
  --type SecureString \
  --region ap-northeast-2
```

## 무료 티어 사용 시 주의

**무료 티어는 사용자 데이터가 Google 모델 학습에 사용됩니다.**

| 티어 | 학습 데이터 사용 | 비용 |
|------|--------|------|
| Free | ✅ 사용됨 | $0 |
| Paid (Billing 연동) | ❌ 사용 안 함 | 사용량 과금 |

감정일기는 매우 개인적인 내용이므로 **실서비스는 Paid 전환 권장**.

### Paid 전환 방법
1. Google Cloud Console → 프로젝트 선택
2. **Billing** 메뉴 → 결제 계정 연결 (신용카드)
3. 자동으로 Paid 티어 전환 (사용한 만큼만 과금)

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
