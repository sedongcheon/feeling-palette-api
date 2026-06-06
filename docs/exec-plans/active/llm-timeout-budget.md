---
slug: llm-timeout-budget
status: active
created: 2026-06-07
---

## Why

2026-06-06 16:21~16:33 UTC, `feeling-palette-duration` 알람 발화. CloudWatch
Logs Insights 확인 결과 8건의 호출이 전부 `Status: timeout`(Duration 정확히
30000ms)으로 죽었고, `Structured ... failed` 애플리케이션 로그는 0건 —
즉 1차 LLM 호출이 예외를 던지기 전에 Lambda가 먼저 강제 종료되어
서비스 레이어의 fallback이 한 번도 실행되지 못했다. 원인은 설정 3중 결함:

1. `ChatGoogleGenerativeAI` 기본 `max_retries=6`을 오버라이드하지 않음 —
   Gemini 일시 장애 시 내부 재시도만으로 30초 소진.
2. per-call `timeout=30`(summary는 60)이 Lambda `Timeout: 30`과 같거나 큼 —
   클라이언트 타임아웃이 먼저 발동할 수 없어 fallback이 데드 코드.
   API Gateway HTTP API 통합 타임아웃 상한이 ~29s라 Lambda 한도 증설은 해법이 아님.
3. 요청 경로를 남기는 로그가 전무 — REPORT만으로는 어느 엔드포인트가
   느렸는지 식별 불가.

## What

- `domains/emotions/config/__init__.py` — 4개 인스턴스 모두
  `max_retries=1` 명시; `timeout` 30→10 (`llm`, `llm_journal`,
  `llm_recommend`), 60→18 (`llm_summary`). 예산: 1차(10s) + fallback(10s)
  + 콜드스타트(~2s) + 오버헤드 ≤ ~25s < Lambda 30s. summary는 입력이
  길어 18s + fallback은 Lambda 데드라인 전 발동 보장 수준만.
- `apps/api/main.py` — HTTP 미들웨어 1개 추가: `METHOD /path → status
  elapsed_ms` 한 줄 로깅. 다음 장애 때 라우트 식별용.

## Verification

- 로컬 uvicorn 기동 → `/api/diary/analyze` 정상 케이스 1건 호출, 응답 +
  액세스 로그 1줄 확인.
- `pytest` (journal 라우트 + recommend + palette 커버리지) 통과.
- 배포 후: 다음 Gemini 슬로우 이벤트에서 timeout 대신
  `Structured ... failed` → fallback 성공 또는 504 미만 응답 확인.

## Open questions / risks

- 10s가 정상 트래픽의 p99보다 빠듯할 가능성 — flash-lite 정상 응답은
  수 초 내라 여유 있다고 판단하나, 배포 후 duration 메트릭으로 재확인.
- summary 18s × (1+1 retry) + fallback 18s 최악 케이스는 여전히 30s 초과
  가능 → `max_retries=1`이라 재시도 1회 포함 최악 36s. 실제로는 1차가
  18s에서 끊기면 fallback이 ~20s 시점에 시작, 데드라인까지 ~8s. fallback
  까지 완주 못 할 수 있으나 현재(0% 작동)보다 개선. 필요 시 summary 전용
  asyncio.wait_for 데드라인은 후속 플랜으로.

## Decision log

- 2026-06-07 — Lambda Timeout 증설 대신 앱 내 예산 재조정 채택. 이유:
  API Gateway HTTP API 상한(~29s) 때문에 Lambda 한도만 늘려도 무의미.
- 2026-06-07 — max_retries=1 (0 아님). 이유: 진짜 일시 오류(단발 429)
  복구 기회는 남기되 폭주는 차단.
- 2026-06-07 — 로컬 검증 중 **트리거 확인**: Gemini 가
  `429 ResourceExhausted: Your prepayment credits are depleted` 반환.
  06-06 타임아웃의 정체 = 429 + 기본 6회 재시도(지수 백오프)가 30s 소진.
  코드 수정과 별개로 AI Studio 크레딧 충전 필요 (사용자 액션).
