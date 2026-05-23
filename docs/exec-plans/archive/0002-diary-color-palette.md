---
slug: diary-color-palette
status: done
created: 2026-05-23
---

## Why

`/api/diary/analyze` 현재 응답은 단일 `color` HEX 1개. Flutter 가 카드
배경 그라데이션·악센트·아이콘 등 다양한 자리에서 감정을 시각적으로
다루려면 같은 감정 계열의 색 여러 개가 필요. 이미지 생성은 비용 곡선이
가팔라 보류 결정 — 우선 비용 0, 응답시간 변화 0 의 변화로 retention
신호를 본다.

## What

- `domains/emotions/types/__init__.py` — `AnalyzeResponse` 에
  `palette: List[str]` 필드 추가 (5개 HEX, `color` 가 첫 번째 요소).
  기존 `color: str` 은 backward compat 으로 유지.
- `domains/emotions/service/__init__.py` — 모듈 상단에 `EMOTION_PALETTES`
  상수 추가 (`dict[EmotionKey, list[str]]`). `analyze_diary` 가 LLM 결과
  받은 뒤 `primary_emotion` 키로 팔레트를 조회해 응답에 attach.
  엣지 케이스(LLM 이 6 감정 외 라벨을 반환) 시 `calm` 팔레트로 fallback.
- `CLAUDE.md` — "Emotion→color mapping is fixed" 항목 갱신 (단일 HEX →
  HEX + 5색 팔레트).
- `tests/test_diary_palette.py` (신규) — 결정론적 매핑이라 LLM mock 으로
  6 감정 × palette 길이/anchor 일치/HEX 패턴 검증. backward compat 확인
  (`color` == `palette[0]`).
- `docs/product-specs/emotions.md` — 팔레트 스펙 한 문단 추가.

## Verification

- pytest 통과 (기존 5 + 신규 6+)
- 로컬 dev 서버:
  - `{"content":"오늘 너무 신나!"}` → primary `excitement`, palette
    핑크 계열 5개, palette[0] == color == `#FF69B4`
  - `{"content":"기분이 우울해"}` → primary `sadness`, palette 파랑 계열
  - `{"content":"ㅎㅎㅎㅎ"}` → 어떤 감정이든 정상 응답 + palette 5개
- 응답 schema 확인: `palette` 가 항상 5개, 각각 `^#[0-9A-Fa-f]{6}$`

## Open questions / risks

- **Flutter 미반영 영향:** 기존 클라이언트는 `palette` 키를 모르므로
  무시. JSON 디시리얼라이저가 unknown field 를 깨뜨리지 않게 만들어
  있어야 함 (대체로 그렇지만 Flutter 모델 정의에 따라 다름). 출시 전
  확인 필요.
- **팔레트 색 톤:** 5색을 anchor + 라이트·딥·페일·뮤트 패턴으로 손으로
  골랐음. 실제 Flutter 카드에서 어떻게 보일지는 시각 검증 단계 필요.
  필요하면 추후 색 보정 PR.
- **3 vs 5:** 5 선택 (Flutter 가 부분집합을 쓸 수 있어 유연). 실사용
  관찰 후 줄일 수 있음.
- **LLM 이 6감정 외 값 반환:** 현재 prompt 가 강제하지만 회귀 가능성.
  `calm` fallback 으로 일단 방어, 회귀 시 로그 남김.

## Decision log

- 2026-05-23 — 결정론적 매핑 (vs LLM 생성). 이유: 비용·지연 0,
  테스트 단순, CLAUDE.md 의 "fixed mapping" 원칙 유지.
- 2026-05-23 — 5색 (vs 3). 이유: Flutter 가 그라데이션·악센트·텍스트
  대비 등 다양한 용도로 쓸 수 있게 여유.
- 2026-05-23 — `/api/diary/analyze` 만. 이유: 현 운영 트래픽이 여기로만
  옴. `/api/v1/journal/analyze` 는 미출시 + 이미 variable palette
  컨셉이라 별도 작업으로 분리.
