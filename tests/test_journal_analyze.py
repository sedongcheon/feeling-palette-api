import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from domains.emotions.types import JournalAnalyzeResponse, JournalEmotionScore


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_journal_analyze_happy_path(monkeypatch):
    async def fake_analyze(text: str) -> JournalAnalyzeResponse:
        return JournalAnalyzeResponse(
            emotions=[JournalEmotionScore(label="불안", intensity=0.72)],
            themes=["업무 스트레스"],
            dominant_emotion="불안",
            intensity_score=0.68,
            empathy_response="오늘 마음이 무거우셨겠어요. 충분히 그럴 만한 하루였어요.",
            suggested_color_hex="#5B7C99",
            color_reasoning="차분한 청색은 가라앉은 마음을 비춰줘요.",
        )

    monkeypatch.setattr("domains.emotions.ui.routes.analyze_journal", fake_analyze)

    async with _client() as c:
        resp = await c.post(
            "/api/v1/journal/analyze",
            json={
                "anonymized_text": "오늘 회사에서 팀장님 피드백을 받았는데 마음이 좀 무거웠어.",
                "user_id_hash": "test-user-hash-001",
            },
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["dominant_emotion"] == "불안"
    assert body["suggested_color_hex"] == "#5B7C99"
    assert 0.0 <= body["intensity_score"] <= 1.0
    assert isinstance(body["emotions"], list) and len(body["emotions"]) >= 1
    assert isinstance(body["themes"], list) and len(body["themes"]) >= 1


@pytest.mark.asyncio
async def test_journal_analyze_rejects_text_too_long():
    async with _client() as c:
        resp = await c.post(
            "/api/v1/journal/analyze",
            json={"anonymized_text": "가" * 3001, "user_id_hash": "h"},
        )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_journal_analyze_rejects_whitespace_only_text():
    async with _client() as c:
        resp = await c.post(
            "/api/v1/journal/analyze",
            json={"anonymized_text": "   ", "user_id_hash": "h"},
        )
    assert resp.status_code == 400
    assert "anonymized_text" in resp.json()["error"]


@pytest.mark.asyncio
async def test_journal_analyze_returns_502_on_gemini_failure(monkeypatch):
    async def fake_fail(text: str):
        raise RuntimeError("Gemini upstream down")

    monkeypatch.setattr("domains.emotions.ui.routes.analyze_journal", fake_fail)

    async with _client() as c:
        resp = await c.post(
            "/api/v1/journal/analyze",
            json={
                "anonymized_text": "오늘은 그냥 그런 하루였어.",
                "user_id_hash": "test-user-hash-002",
            },
        )

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"] == "AI 분석 일시 실패"
    assert body["retryable"] is True


@pytest.mark.asyncio
async def test_journal_analyze_returns_502_when_service_returns_none(monkeypatch):
    # with_structured_output 이 토큰 한도 초과로 None 을 돌려주는 회귀
    # (gemini-2.5-flash thinking 이 토큰을 다 잡아먹은 케이스)를 가드.
    async def fake_none(text: str):
        return None

    monkeypatch.setattr("domains.emotions.ui.routes.analyze_journal", fake_none)

    async with _client() as c:
        resp = await c.post(
            "/api/v1/journal/analyze",
            json={
                "anonymized_text": "오늘은 그냥 그런 하루였어.",
                "user_id_hash": "test-user-hash-003",
            },
        )

    assert resp.status_code == 502
    body = resp.json()
    assert body["error"] == "AI 분석 일시 실패"
    assert body["retryable"] is True
