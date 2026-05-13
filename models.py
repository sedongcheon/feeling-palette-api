from typing import List, Literal, Optional

from pydantic import BaseModel, Field

EmotionKey = Literal["joy", "sadness", "anger", "anxiety", "calm", "excitement"]
LocaleKey = Literal["ko", "en"]


class AnalyzeRequest(BaseModel):
    content: str
    locale: LocaleKey = Field(default="ko", description="응답 언어 (ko: 한국어, en: 영어)")


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
    locale: LocaleKey = Field(default="ko", description="응답 언어 (ko: 한국어, en: 영어)")


class SummarizeResponse(BaseModel):
    summary: str = Field(description="한국어 월간 요약 (2~4문장, 100~250자)")
    dominant_emotion: Optional[EmotionKey] = Field(
        default=None,
        description="월 전체를 통틀어 가장 두드러진 감정 (애매하면 null)",
    )


TrendKey = Literal["up", "down", "stable", "mixed"]
ConfidenceKey = Literal["low", "medium", "high"]


class WeeklyInsightRequest(BaseModel):
    anchor_date: str = Field(
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="기준 날짜 (YYYY-MM-DD). 보통 생성 시점의 오늘 날짜.",
    )
    entries: List[EntryIn] = Field(
        description="기준 날짜 이전 최근 30일(또는 그 이하)에 작성된 일기 목록",
    )
    locale: LocaleKey = Field(default="ko", description="응답 언어 (ko: 한국어, en: 영어)")


class WeeklyInsightResponse(BaseModel):
    insight_text: str = Field(
        description="사용자에게 보여줄 한국어 인사이트 (2~3문장, 공백 포함 80~180자)",
    )
    trend: TrendKey = Field(
        description="감정 흐름: up(상승), down(하강), stable(안정), mixed(혼재)",
    )
    keyword: Optional[str] = Field(
        default=None,
        description="인사이트의 핵심 키워드 1개 (회사, 가족 등). 딱히 없으면 null",
    )
    confidence: ConfidenceKey = Field(
        description="신뢰도: low(데이터 부족), medium, high(패턴 명확)",
    )
    care_flag: bool = Field(
        default=False,
        description="자해·극단적 선택 암시가 감지되면 true. insight_text에는 1393 안내가 포함되어 있어야 함.",
    )
