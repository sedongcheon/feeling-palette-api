---
slug: vertex-ai-migration
status: active
created: 2026-06-07
---

## Why

2026-06-06 분석 장애의 근본 원인은 Gemini Developer API 선불 크레딧 소진.
2026-03-23부터 신규 계정은 선불이 강제되고(잔액 0 = 즉시 전면 장애),
후불 전환은 Tier 3($1,000+) 조건 + 현재 전환 기능 중단 상태. 사용자가
선불 잔액 관리 리스크를 피하고자 **후불(표준 Cloud Billing)이 되는
Vertex AI**로 전환을 결정. 모델 단가는 Developer API와 동일
(2.5-flash-lite $0.10/$0.40 per 1M).

## What

- `requirements.txt` — `langchain-google-vertexai` 추가
  (`langchain-google-genai`는 검증 완료 후 제거).
- `domains/emotions/config/__init__.py` — `ChatGoogleGenerativeAI` 4개
  인스턴스를 `ChatVertexAI`로 교체. 모델/토큰/timeout/max_retries 동일
  유지. 인증: `GCP_SA_KEY_JSON` env(JSON 문자열) →
  `service_account.Credentials.from_service_account_info()` →
  `credentials=` 주입. `GCP_PROJECT`, `GCP_LOCATION`(기본 `global`) env.
- `template.yaml` — Lambda env에 `GCP_SA_KEY_JSON`(NoEcho 파라미터),
  `GCP_PROJECT`, `GCP_LOCATION` 추가, `GeminiApiKey` 제거. **(.yml/
  template 변경 — 사용자 확인 필수)**
- `.github/workflows/deploy.yml` — SSM에서
  `/feeling-palette/gcp-sa-key-json` 가져와 파라미터로 전달.
  **(사용자 확인 필수)**
- `docs/RELIABILITY.md` — Model pin 섹션에 provider 전환 기록.

## 사용자 측 사전 작업 (GCP)

1. GCP 프로젝트에 Vertex AI API(aiplatform.googleapis.com) 활성화.
2. 프로젝트가 후불 Cloud Billing 계정에 연결돼 있는지 확인.
3. 서비스 계정 생성 + `Vertex AI User` 롤 + JSON 키 다운로드.
4. JSON 키를 SSM SecureString `/feeling-palette/gcp-sa-key-json`에 저장.
5. 로컬 검증용으로 JSON 키 경로를 알려주거나 `.env`에 등록.

## Verification

- 로컬: ko/en `/api/diary/analyze` 호출 — 응답 정상 + comment 2~3문장.
- **structured output 검증**: 5개 엔드포인트 전부 1회씩 — Pydantic 스키마
  그대로 오는지 (3.1-flash-lite 때 깨졌던 지점).
- **1393 안전 룰 검증**: 자해 암시 ko 입력 → 1393 문구 포함, en → 미포함
  + generic helpline. Vertex 쪽 안전 필터가 응답을 차단/변형하는지 관찰.
- pytest 통과 (라우트 레벨 mock이라 영향 없음 예상).
- 배포 후 smoke test (deploy.yml 내장).

## Open questions / risks

- Vertex 안전 필터 기본값이 Developer API와 달라 자해 관련 일기에서
  응답이 차단될 수 있음 → 1393 검증에서 확인, 필요시 safety_settings 조정.
- `GCP_LOCATION=global` 기본. asia-northeast3(서울)로 좁히면 지연 개선
  가능하나 모델 가용성 확인 필요 — 후속 최적화.
- 로컬 venv py3.9 → langchain-google-vertexai ≤2.1.2, Lambda py3.11은
  더 최신 가능. requirements는 `>=2.0.0`으로 두고 양쪽 호환 확인.
- SA JSON이 Lambda env 평문으로 들어감(현 GeminiApiKey와 동일한 노출
  수준). 더 좋은 방식(런타임 SSM fetch)은 후속.

## Decision log

- 2026-06-07 — Vertex AI 전환 결정 (사용자). 선불 충전($10) 대안 제시했
  으나 후불 선호.
- 2026-06-07 — 인증은 SA JSON env 주입 방식. 이유: 기존 GeminiApiKey
  주입 패턴과 동일한 파이프라인 재사용, Lambda에서 ADC 파일 관리 불필요.
- 2026-06-07 — 모델도 gemini-3.1-flash-lite 로 동시 변경 (사용자 요청,
  비용 ~3배 고지함). 단 **검증 게이트 조건부**: 5개 엔드포인트 structured
  output + 1393/generic helpline 룰 통과 못 하면 2.5-flash-lite 롤백.
  지난 실패는 langchain-google-genai 경로였고 Vertex 는 structured output
  메커니즘이 달라 재시도 명분 있음. 1393 덮어쓰기(109)는 모델 성향이라
  잔존 리스크.
- 2026-06-07 — ChatVertexAI 에 생성자 timeout 필드 없음 확인 → 타임아웃
  예산은 service 레이어 asyncio.wait_for 헬퍼(_ainvoke)로 이전.
