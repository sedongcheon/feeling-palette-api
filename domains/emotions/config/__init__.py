import os

from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    max_output_tokens=512,
    google_api_key=GEMINI_API_KEY,
    timeout=30,
)

# 월간 요약은 입력(한 달치 일기) + 출력(250자 한국어)이 길어서 별도 인스턴스로 관리.
llm_summary = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    max_output_tokens=2048,
    google_api_key=GEMINI_API_KEY,
    timeout=60,
)

# /api/v1/journal/analyze 용. 응답에 emotions[]+themes[]+empathy+reasoning 이 다 들어가
# 기본 llm(512) 으로는 빠듯해서 별도 인스턴스로 한도를 올려둠.
# 모델은 flash-lite 로 통일 — flash 는 thinking 토큰이 max_output_tokens 를
# 잡아먹어 with_structured_output 이 None 을 반환하는 회귀를 일으켰음.
llm_journal = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    max_output_tokens=1024,
    google_api_key=GEMINI_API_KEY,
    timeout=30,
)

# /api/diary/recommend 용. 위로 글(2~3문장) + 음악·책 각 1~3개(각 title+
# artist/author+reason) 가 다 들어가서 512 로는 부족. journal 과 같은 1024.
llm_recommend = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash-lite",
    max_output_tokens=1024,
    google_api_key=GEMINI_API_KEY,
    timeout=30,
)
