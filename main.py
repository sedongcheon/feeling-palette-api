import logging
import os

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from models import AnalyzeRequest
from service import analyze_diary

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Feeling Palette API",
    description="AI 감정일기 분석 API. 인증 필요 — Swagger UI의 Authorize 버튼에서 Bearer 토큰 입력.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

bearer_scheme = HTTPBearer(description="서버에 설정된 API_AUTH_TOKEN 값")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> None:
    expected = os.getenv("API_AUTH_TOKEN")
    if not expected:
        logger.error("API_AUTH_TOKEN is not configured on the server")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="인증이 서버에 설정되지 않았습니다.",
        )
    if credentials.credentials != expected:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="유효하지 않은 토큰입니다.",
        )


@app.post("/api/diary/analyze", dependencies=[Depends(verify_token)])
async def analyze(request: AnalyzeRequest):
    content = request.content.strip()

    if not content:
        return JSONResponse(status_code=400, content={"error": "일기 내용이 비어있습니다."})

    if len(content) > 1000:
        return JSONResponse(status_code=400, content={"error": "일기 내용은 1000자 이하로 작성해주세요."})

    try:
        result = await analyze_diary(content)
        return result
    except Exception:
        logger.exception("Diary analysis request failed")
        return JSONResponse(status_code=500, content={"error": "감정 분석 중 오류가 발생했습니다."})
