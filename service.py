import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage

from config import llm
from models import AnalyzeResponse

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """당신은 한국어 감정 분석 전문가입니다.
사용자의 일기 텍스트를 읽고 감정을 분석하세요.

분석 규칙:
- primary_emotion: 6가지 중 대표 감정 1개 선택 (joy, sadness, anger, anxiety, calm, excitement)
- emotions: 각 감정의 강도를 0~100 점수로 부여 (합이 100일 필요 없음, 복합 감정 표현)
- comment: 사용자에게 전하는 따뜻한 한 줄 공감 메시지 (부드럽고 따뜻한 존댓말 톤)
- color: 대표 감정에 해당하는 HEX 컬러코드

감정-컬러 매핑:
- joy(기쁨): #FFD700
- sadness(슬픔): #4A90D9
- anger(분노): #E74C3C
- anxiety(불안): #9B59B6
- calm(평온): #2ECC71
- excitement(설렘): #FF69B4

한국어 특화 규칙:
- 한국어 뉘앙스를 정확히 파악할 것 (예: "그냥 그래" = 무기력/슬픔 경향)
- 한국 문화적 맥락 반영 (예: "회식" 관련 = 복합 감정 가능)"""


async def analyze_diary(content: str) -> AnalyzeResponse:
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=f"다음 일기를 분석해주세요:\n\n{content}"),
    ]

    structured_llm = llm.with_structured_output(AnalyzeResponse)

    try:
        result = await structured_llm.ainvoke(messages)
        return result
    except Exception:
        logger.exception("Structured diary analysis failed; attempting fallback response parsing")
        # 구조화 출력 실패 시 일반 호출 후 JSON 파싱으로 폴백
        fallback_prompt = SYSTEM_PROMPT + "\n\nJSON 형식으로만 응답하세요: {\"primary_emotion\": \"...\", \"emotions\": {\"joy\": 0, \"sadness\": 0, \"anger\": 0, \"anxiety\": 0, \"calm\": 0, \"excitement\": 0}, \"comment\": \"...\", \"color\": \"#...\"}"
        messages[0] = SystemMessage(content=fallback_prompt)
        try:
            response = await llm.ainvoke(messages)
            data = json.loads(response.content)
            return AnalyzeResponse(**data)
        except Exception:
            logger.exception("Fallback diary analysis failed")
            raise
