---
slug: analyze-comment-length
status: active
created: 2026-06-07
---

## Why

사용자 피드백: `/api/diary/analyze`의 comment(감정 분석 코멘트)가 너무
짧다. 기존 프롬프트가 "한 줄, 공백 포함 30~60자"로 제한하고 있었음.
모델 변경 없이 프롬프트 길이 가이드만으로 해결 가능.

## What

- `domains/emotions/service/__init__.py` — SYSTEM_PROMPT comment 규칙
  30~60자 → **2~3문장, 80~150자** + 일기 속 구체적 경험 1회 언급 요구.
  엣지 케이스(짧은 기록)는 80자 하한 예외. 1393 안전 문구 예외의 상한
  언급 60→150자로 동기화. EN 오버라이드는 150~300 chars (영문은 글자당
  정보량이 낮아 2배 환산).
- `domains/emotions/types/__init__.py` — `AnalyzeResponse.comment` 필드
  description "한 줄" → "2~3문장".

## Verification

- pytest 통과 (palette 매핑 등 기존 커버리지 회귀 없음).
- 새 Gemini 키 적용 후 로컬 uvicorn 으로 ko/en 각 1건 호출, comment 가
  2~3문장·길이 범위 내인지 + 1393 미발화(일반 일기) 확인.
- max_output_tokens=512 유지 — 한국어 150자 ≈ 200토큰 미만으로 여유.

## Open questions / risks

- Flutter 카드 UI가 60자 기준으로 잡혀 있으면 레이아웃 깨질 수 있음 —
  FE(Flutter 통합 대기 중)에 길이 변경 공지 필요.

## Decision log

- 2026-06-07 — 80~150자(2~3문장) 채택, 150~250자 안은 기각. 이유: 카드
  UI 과길이 위험. 사용자 선택.
- 2026-06-07 — 모델 변경과 분리. 길이는 프롬프트 소관이며, 모델
  재검증(structured output + 1393)은 새 키 적용 후 별도 진행.
