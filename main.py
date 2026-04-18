import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from models import AnalyzeRequest
from service import analyze_diary

logger = logging.getLogger(__name__)

app = FastAPI(title="Feeling Palette API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/diary/analyze")
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
