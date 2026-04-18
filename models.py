from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EmotionKey = Literal["joy", "sadness", "anger", "anxiety", "calm", "excitement"]


class AnalyzeRequest(BaseModel):
    content: str


class EmotionScores(BaseModel):
    joy: int = Field(ge=0, le=100, description="기쁨 강도 0~100")
    sadness: int = Field(ge=0, le=100, description="슬픔 강도 0~100")
    anger: int = Field(ge=0, le=100, description="분노 강도 0~100")
    anxiety: int = Field(ge=0, le=100, description="불안 강도 0~100")
    calm: int = Field(ge=0, le=100, description="평온 강도 0~100")
    excitement: int = Field(ge=0, le=100, description="설렘 강도 0~100")


class AnalyzeResponse(BaseModel):
    primary_emotion: str = Field(description="대표 감정: joy, sadness, anger, anxiety, calm, excitement 중 1개")
    emotions: EmotionScores = Field(description="각 감정의 강도 점수")
    comment: str = Field(description="사용자에게 전하는 따뜻한 한 줄 공감 메시지")
    color: str = Field(description="대표 감정에 해당하는 HEX 컬러코드")


class EntryIn(BaseModel):
    date: str = Field(description="일기 날짜 (YYYY-MM-DD)")
    content: str = Field(description="일기 본문")
    primary_emotion: Optional[EmotionKey] = Field(default=None, description="이미 분석된 대표 감정 (힌트용)")


class SummarizeRequest(BaseModel):
    year_month: str = Field(pattern=r"^\d{4}-\d{2}$", description="요약 대상 월 (YYYY-MM)")
    entries: List[EntryIn] = Field(description="해당 월에 작성된 일기 목록")


class SummarizeResponse(BaseModel):
    summary: str = Field(description="한국어 월간 요약 (2~4문장, 100~250자)")
    dominant_emotion: Optional[EmotionKey] = Field(
        default=None,
        description="월 전체를 통틀어 가장 두드러진 감정 (애매하면 null)",
    )
