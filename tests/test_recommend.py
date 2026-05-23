import pytest
from httpx import ASGITransport, AsyncClient

from apps.api.main import app
from domains.emotions.service import RECOMMEND_DISCLAIMER_EN, RECOMMEND_DISCLAIMER_KO
from domains.emotions.types import (
    BookRecommendation,
    MusicRecommendation,
    RecommendResponse,
)


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


def _sample_response() -> RecommendResponse:
    return RecommendResponse(
        primary_emotion="sadness",
        comfort_message="오늘 마음이 무거우셨겠어요. 충분히 그럴 만한 하루였어요. 잠시 쉬어가도 괜찮아요.",
        music=[
            MusicRecommendation(
                title="잔잔한 빗속에서",
                artist="아이유",
                reason="잔잔한 멜로디가 마음을 편안하게 해줘요.",
            ),
        ],
        books=[
            BookRecommendation(
                title="아몬드",
                author="손원평",
                reason="감정을 들여다보는 데 도움이 되는 책이에요.",
            ),
        ],
    )


@pytest.mark.asyncio
async def test_recommend_happy_path_ko(monkeypatch):
    async def fake_recommend(content: str, locale: str = "ko") -> RecommendResponse:
        assert locale == "ko"
        resp = _sample_response()
        resp.disclaimer = RECOMMEND_DISCLAIMER_KO
        return resp

    monkeypatch.setattr("domains.emotions.ui.routes.recommend_content", fake_recommend)

    async with _client() as c:
        resp = await c.post(
            "/api/diary/recommend",
            json={"content": "오늘 기분이 우울했어요.", "locale": "ko"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["primary_emotion"] == "sadness"
    assert body["disclaimer"] == RECOMMEND_DISCLAIMER_KO
    assert len(body["music"]) == 1
    assert body["music"][0]["title"] and body["music"][0]["artist"]
    assert len(body["books"]) == 1
    assert body["books"][0]["title"] and body["books"][0]["author"]


@pytest.mark.asyncio
async def test_recommend_happy_path_en_uses_en_disclaimer(monkeypatch):
    async def fake_recommend(content: str, locale: str = "ko") -> RecommendResponse:
        assert locale == "en"
        resp = _sample_response()
        resp.disclaimer = RECOMMEND_DISCLAIMER_EN
        return resp

    monkeypatch.setattr("domains.emotions.ui.routes.recommend_content", fake_recommend)

    async with _client() as c:
        resp = await c.post(
            "/api/diary/recommend",
            json={"content": "I felt down today.", "locale": "en"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["disclaimer"] == RECOMMEND_DISCLAIMER_EN


@pytest.mark.asyncio
async def test_recommend_rejects_empty():
    async with _client() as c:
        resp = await c.post("/api/diary/recommend", json={"content": "   "})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_recommend_rejects_over_cap():
    async with _client() as c:
        resp = await c.post("/api/diary/recommend", json={"content": "가" * 1001})
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_recommend_returns_500_on_failure(monkeypatch):
    async def fake_fail(content: str, locale: str = "ko"):
        raise RuntimeError("Gemini upstream down")

    monkeypatch.setattr("domains.emotions.ui.routes.recommend_content", fake_fail)

    async with _client() as c:
        resp = await c.post("/api/diary/recommend", json={"content": "오늘은 그저 그랬어요."})

    assert resp.status_code == 500


@pytest.mark.asyncio
async def test_recommend_returns_500_when_service_returns_none(monkeypatch):
    # truncated LLM output 시 None 가드 회귀 방지
    async def fake_none(content: str, locale: str = "ko"):
        return None

    monkeypatch.setattr("domains.emotions.ui.routes.recommend_content", fake_none)

    async with _client() as c:
        resp = await c.post("/api/diary/recommend", json={"content": "오늘은 그저 그랬어요."})

    assert resp.status_code == 500
