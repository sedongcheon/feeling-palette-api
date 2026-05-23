import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from domains.emotions.service import (
    analyze_diary,
    analyze_journal,
    summarize_month,
    weekly_insight,
)
from domains.emotions.types import (
    AnalyzeRequest,
    JournalAnalyzeRequest,
    SummarizeRequest,
    WeeklyInsightRequest,
)

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/diary/analyze")
async def analyze(request: AnalyzeRequest):
    content = request.content.strip()

    if not content:
        return JSONResponse(status_code=400, content={"error": "일기 내용이 비어있습니다."})

    if len(content) > 1000:
        return JSONResponse(status_code=400, content={"error": "일기 내용은 1000자 이하로 작성해주세요."})

    try:
        result = await analyze_diary(content, request.locale)
    except Exception:
        logger.exception("Diary analysis request failed")
        return JSONResponse(status_code=500, content={"error": "감정 분석 중 오류가 발생했습니다."})

    if result is None:
        logger.error("Diary analysis returned None (likely truncated LLM output)")
        return JSONResponse(status_code=500, content={"error": "감정 분석 중 오류가 발생했습니다."})
    return result


@router.post("/api/month/summarize")
async def summarize(request: SummarizeRequest):
    if not request.entries:
        return JSONResponse(status_code=400, content={"error": "entries가 비어있습니다."})

    try:
        result = await summarize_month(request.year_month, request.entries, request.locale)
    except Exception:
        logger.exception("Month summarize request failed")
        return JSONResponse(status_code=500, content={"error": "월간 요약 중 오류가 발생했습니다."})

    if result is None:
        logger.error("Month summary returned None (likely truncated LLM output)")
        return JSONResponse(status_code=500, content={"error": "월간 요약 중 오류가 발생했습니다."})
    return result


@router.post("/api/insights/weekly")
async def insights_weekly(request: WeeklyInsightRequest):
    if not request.entries:
        return JSONResponse(status_code=400, content={"error": "entries가 비어있습니다."})

    try:
        result = await weekly_insight(request.anchor_date, request.entries, request.locale)
    except Exception:
        logger.exception("Weekly insight request failed")
        return JSONResponse(status_code=500, content={"error": "주간 인사이트 생성 중 오류가 발생했습니다."})

    if result is None:
        logger.error("Weekly insight returned None (likely truncated LLM output)")
        return JSONResponse(status_code=500, content={"error": "주간 인사이트 생성 중 오류가 발생했습니다."})
    return result


@router.post("/api/v1/journal/analyze")
async def journal_analyze(request: JournalAnalyzeRequest):
    text = request.anonymized_text.strip()
    if not text:
        return JSONResponse(status_code=400, content={"error": "anonymized_text가 비어있습니다."})
    if not request.user_id_hash.strip():
        return JSONResponse(status_code=400, content={"error": "user_id_hash가 비어있습니다."})

    user_hash_short = request.user_id_hash[:8]
    logger.info("journal.analyze.start user_hash=%s len=%d", user_hash_short, len(text))

    try:
        result = await analyze_journal(text)
    except Exception:
        logger.exception("journal.analyze.failed user_hash=%s", user_hash_short)
        return JSONResponse(
            status_code=502,
            content={"error": "AI 분석 일시 실패", "retryable": True},
        )

    if result is None:
        logger.error("journal.analyze.empty user_hash=%s (likely truncated LLM output)", user_hash_short)
        return JSONResponse(
            status_code=502,
            content={"error": "AI 분석 일시 실패", "retryable": True},
        )

    logger.info(
        "journal.analyze.done user_hash=%s emotions=%d intensity=%.2f",
        user_hash_short, len(result.emotions), result.intensity_score,
    )
    return result
