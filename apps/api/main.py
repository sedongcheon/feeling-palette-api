import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from domains.emotions.ui.routes import router as emotions_router

logger = logging.getLogger(__name__)
# Lambda 런타임은 root 로거가 WARNING 이라 INFO 액세스 로그가 묻힌다.
logger.setLevel(logging.INFO)

app = FastAPI(title="Feeling Palette API")


@app.middleware("http")
async def access_log(request: Request, call_next):
    """CloudWatch 에서 라우트별 지연을 식별하기 위한 한 줄 액세스 로그.

    2026-06-06 timeout 장애 때 REPORT 로그만으로는 어느 엔드포인트가
    느렸는지 알 수 없었다 (exec-plan: llm-timeout-budget).
    """
    start = time.monotonic()
    response = await call_next(request)
    elapsed_ms = (time.monotonic() - start) * 1000
    logger.info(
        "%s %s -> %d %.0fms",
        request.method, request.url.path, response.status_code, elapsed_ms,
    )
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(emotions_router)
