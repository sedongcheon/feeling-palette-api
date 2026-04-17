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
