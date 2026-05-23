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
    color: str = Field(description="대표 감정에 해당하는 HEX 컬러코드 (palette[0] 와 동일, backward compat)")
    palette: List[str] = Field(
        default_factory=list,
        description="대표 감정 기반 5색 HEX 팔레트 (anchor=color, 그라데이션·악센트용)",
    )


class EntryIn(BaseModel):
    date: str = Field(description="일기 날짜 (YYYY-MM-DD)")
    content: str = Field(description="일기 본문")
    primary_emotion: Optional[EmotionKey] = Field(default=None, description="이미 분석된 대표 감정 (힌트용)")


class SummarizeRequest(BaseModel):
    year_month: str = Field(pattern=r"^\d{4}-\d{2}$", description="요약 대상 월 (YYYY-MM)")
    entries: List[EntryIn] = Field(description="해당 월에 작성된 일기 목록")
    locale: LocaleKey = Field(default="ko", description="응답 언어 (ko: 한국어, en: 영어)")


class SummarizeResponse(BaseModel):
    summary: str = Field(description="월간 요약 (2~4문장, 100~250자). 출력 언어는 system prompt의 locale 규칙을 따름.")
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
        description="사용자에게 보여줄 인사이트 (2~3문장, 공백 포함 80~180자). 출력 언어는 system prompt의 locale 규칙을 따름.",
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


class JournalEmotionScore(BaseModel):
    label: str = Field(description="감정 라벨 (Plutchik 1차 또는 한국어 세밀 감정명)")
    intensity: float = Field(ge=0.0, le=1.0, description="감정 강도 0.0~1.0")


class JournalAnalyzeRequest(BaseModel):
    anonymized_text: str = Field(
        min_length=1,
        max_length=3000,
        description="익명화된 일기 본문 (1~3000자)",
    )
    user_id_hash: str = Field(min_length=1, description="사용자 식별 해시 (로깅용)")


class JournalAnalyzeResponse(BaseModel):
    emotions: List[JournalEmotionScore] = Field(
        min_length=1, max_length=3, description="추출된 감정 1~3개"
    )
    themes: List[str] = Field(
        min_length=1, max_length=3, description="핵심 주제 1~3개 (한국어 명사구)"
    )
    dominant_emotion: str = Field(description="지배적 감정 1개")
    intensity_score: float = Field(ge=0.0, le=1.0, description="전체 감정 강도 0.0~1.0")
    empathy_response: str = Field(description="공감 응답 (2~4문장)")
    suggested_color_hex: str = Field(
        pattern=r"^#[0-9A-Fa-f]{6}$", description="감정에 어울리는 #RRGGBB"
    )
    color_reasoning: str = Field(description="색상 선택 이유 (1문장)")
