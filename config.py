import os

from dotenv import load_dotenv
from langchain_anthropic import ChatAnthropic

load_dotenv()

CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")

llm = ChatAnthropic(
    model="claude-sonnet-4-20250514",
    max_tokens=512,
    api_key=CLAUDE_API_KEY,
    timeout=30,
)
