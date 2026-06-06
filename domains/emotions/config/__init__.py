import json
import os

from langchain_google_vertexai import ChatVertexAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Vertex AI (후불 Cloud Billing) — Gemini Developer API 선불 크레딧 소진
# 장애(2026-06-06) 후 provider 전환 (exec-plan: vertex-ai-migration).
# 인증 우선순위:
#   1. GCP_SA_KEY_JSON — SA 키 JSON 문자열 (Lambda: SSM → env 주입)
#   2. ADC — GOOGLE_APPLICATION_CREDENTIALS 파일 경로 (로컬 개발)
GCP_PROJECT = os.getenv("GCP_PROJECT")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")

_sa_key_json = os.getenv("GCP_SA_KEY_JSON")
if _sa_key_json:
    import base64

    from google.oauth2 import service_account

    # CloudFormation 파라미터로 전달할 때 개행·따옴표 이슈를 피하기 위해
    # base64 인코딩 값도 허용 (deploy.yml 에서 인코딩해 주입).
    if not _sa_key_json.lstrip().startswith("{"):
        _sa_key_json = base64.b64decode(_sa_key_json).decode("utf-8")

    _sa_info = json.loads(_sa_key_json)
    _credentials = service_account.Credentials.from_service_account_info(
        _sa_info,
        scopes=["https://www.googleapis.com/auth/cloud-platform"],
    )
    GCP_PROJECT = GCP_PROJECT or _sa_info.get("project_id")
else:
    _credentials = None  # ADC 폴백

# 타임아웃 예산 (2026-06-06 timeout 장애 후속, exec-plan: llm-timeout-budget):
# Lambda 30s 안에 1차 호출 + fallback 호출이 모두 끝나야 하므로 호출당
# 10s(요약은 18s)로 제한. ChatVertexAI 는 생성자 timeout 필드가 없어
# service 레이어에서 asyncio.wait_for 로 적용한다 (아래 상수 참조).
# max_retries 는 재시도 폭주 방지를 위해 전 인스턴스 1로 고정.
LLM_TIMEOUT_S = 10
LLM_SUMMARY_TIMEOUT_S = 18

# 3.1-flash-lite: Developer API + langchain-google-genai 조합에서는 실패
# (structured output 무시 + 1393→109 덮어씀, docs/RELIABILITY.md). Vertex
# 전환으로 structured output 경로가 달라져 재시도 — 릴리즈 전 5개 엔드포인트
# 스키마 + 1393 룰 검증 통과가 조건. 실패 시 gemini-2.5-flash-lite 로 롤백.
_COMMON = dict(
    model_name="gemini-3.1-flash-lite",
    project=GCP_PROJECT,
    location=GCP_LOCATION,
    credentials=_credentials,
    max_retries=1,
)

llm = ChatVertexAI(
    max_output_tokens=512,
    **_COMMON,
)

# 월간 요약은 입력(한 달치 일기) + 출력(250자 한국어)이 길어서 별도 인스턴스로 관리.
llm_summary = ChatVertexAI(
    max_output_tokens=2048,
    **_COMMON,
)

# /api/v1/journal/analyze 용. 응답에 emotions[]+themes[]+empathy+reasoning 이 다 들어가
# 기본 llm(512) 으로는 빠듯해서 별도 인스턴스로 한도를 올려둠.
# 모델은 flash-lite 로 통일 — flash 는 thinking 토큰이 max_output_tokens 를
# 잡아먹어 with_structured_output 이 None 을 반환하는 회귀를 일으켰음.
llm_journal = ChatVertexAI(
    max_output_tokens=1024,
    **_COMMON,
)

# /api/diary/recommend 용. 위로 글(2~3문장) + 음악·책 각 1~3개(각 title+
# artist/author+reason) 가 다 들어가서 512 로는 부족. journal 과 같은 1024.
llm_recommend = ChatVertexAI(
    max_output_tokens=1024,
    **_COMMON,
)
