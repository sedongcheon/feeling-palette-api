from pydantic import BaseModel, Field


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
