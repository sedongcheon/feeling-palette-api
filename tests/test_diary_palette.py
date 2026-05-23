import re

import pytest

from domains.emotions.service import EMOTION_PALETTES, palette_for
from domains.emotions.types import AnalyzeResponse, EmotionScores


HEX_PATTERN = re.compile(r"^#[0-9A-Fa-f]{6}$")


def test_emotion_palettes_have_5_valid_hex_each():
    expected_emotions = {"joy", "sadness", "anger", "anxiety", "calm", "excitement"}
    assert set(EMOTION_PALETTES.keys()) == expected_emotions
    for emotion, palette in EMOTION_PALETTES.items():
        assert len(palette) == 5, f"{emotion} should have 5 colors"
        for hex_code in palette:
            assert HEX_PATTERN.match(hex_code), f"{emotion}: {hex_code} not valid hex"


def test_palette_for_known_emotion_returns_full_palette():
    palette = palette_for("excitement")
    assert palette == EMOTION_PALETTES["excitement"]
    # 반환값은 복사본이어야 함 — 호출자가 mutate 해도 원본 영향 X
    palette.append("#000000")
    assert len(EMOTION_PALETTES["excitement"]) == 5


def test_palette_for_unknown_emotion_falls_back_to_calm():
    palette = palette_for("nostalgia")
    assert palette == EMOTION_PALETTES["calm"]


def test_analyze_response_palette_defaults_empty():
    # palette 필드가 optional 이라 기존 클라이언트가 안 보내도 디시리얼라이즈 가능
    resp = AnalyzeResponse(
        primary_emotion="joy",
        emotions=EmotionScores(joy=80, sadness=0, anger=0, anxiety=0, calm=20, excitement=0),
        comment="좋은 하루였네요.",
        color="#FFD700",
    )
    assert resp.palette == []


def test_analyze_response_carries_palette():
    resp = AnalyzeResponse(
        primary_emotion="joy",
        emotions=EmotionScores(joy=80, sadness=0, anger=0, anxiety=0, calm=20, excitement=0),
        comment="좋은 하루였네요.",
        color="#FFD700",
        palette=EMOTION_PALETTES["joy"],
    )
    assert resp.palette[0] == resp.color == "#FFD700"
    assert len(resp.palette) == 5


@pytest.mark.parametrize("emotion", list(EMOTION_PALETTES.keys()))
def test_palette_anchor_is_first_color(emotion):
    # CLAUDE.md 의 "Emotion→color mapping is fixed" 보존: anchor(palette[0])
    # 가 종래 사용되던 단일 HEX 와 동일해야 함.
    expected_anchors = {
        "joy": "#FFD700",
        "sadness": "#4A90D9",
        "anger": "#E74C3C",
        "anxiety": "#9B59B6",
        "calm": "#2ECC71",
        "excitement": "#FF69B4",
    }
    assert EMOTION_PALETTES[emotion][0] == expected_anchors[emotion]
