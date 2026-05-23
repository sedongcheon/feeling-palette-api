import os

from langchain_google_genai import ChatGoogleGenerativeAI

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    max_output_tokens=512,
    google_api_key=GEMINI_API_KEY,
    timeout=30,
)

# 월간 요약은 입력(한 달치 일기) + 출력(250자 한국어)이 길어서 별도 인스턴스로 관리.
llm_summary = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    max_output_tokens=2048,
    google_api_key=GEMINI_API_KEY,
    timeout=60,
)

# /api/v1/journal/analyze 용. 응답에 emotions[]+themes[]+empathy+reasoning 이 다 들어가
# 기본 llm(512) 으로는 빠듯해서 별도 인스턴스로 한도를 올려둠.
llm_journal = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    max_output_tokens=1024,
    google_api_key=GEMINI_API_KEY,
    timeout=30,
)
