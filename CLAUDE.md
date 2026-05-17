# Feeling Palette API

Korean emotion-analysis FastAPI backend powered by Google Gemini (LangChain).
Three endpoints: per-diary analysis, monthly summary, weekly insight card.

## Commands

```bash
# Local dev
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080

# Container (NAS deploy path)
docker compose up --build           # exposes :8100 → :8080

# AWS Lambda (SAM)
sam build && sam deploy              # uses template.yaml
```

Requires `GEMINI_API_KEY` in `.env` (gitignored).

No test suite — verify changes by hitting endpoints directly (e.g. via `/docs` Swagger UI).

## Architecture

- Endpoints (all `POST`): `/api/diary/analyze`, `/api/month/summarize`, `/api/insights/weekly`
- `main.py` — FastAPI app, 3 POST routes, input validation, error envelope
- `service.py` — LLM orchestration + **all Korean system prompts** (analyze / month summary / weekly insight)
- `models.py` — Pydantic schemas; `EmotionKey` enum is the source of truth for the 6 emotions
- `config.py` — two LLM instances on `gemini-2.5-flash-lite`: `llm` (512 tok, /analyze) and `llm_summary` (2048 tok, month + weekly). The flash-lite variant is intentional (cost) — don't bump without asking.
- `lambda_handler.py` — Mangum adapter for Lambda
- `template.yaml` — SAM stack: HttpApi + Lambda(arm64, 512MB, 30s) + CloudWatch alarms + SNS
- `Jenkinsfile` — NAS deploy: build → docker run on port 8100 → health check `/docs`
- `docs/01–09` — detailed feature/deploy guides (read these for deep context)

## Non-obvious rules

- **Output language follows `request.locale`** (`ko` default, `en` supported). Korean base system prompts in `service.py` interpret diaries; when `locale="en"`, a `*_LOCALE_EN_OVERRIDE` block is appended that flips only the final output language. Don't translate the Korean base prompts — extend the override block instead.
- **Emotion→color mapping is fixed** in `service.py` SYSTEM_PROMPT. Never invent new HEX values.
- **Safety hotline depends on locale**: `1393` is Korea-only — emit it only when `locale="ko"` AND self-harm signals are detected (`care_flag=true` in weekly). For `locale="en"`, the override block emits a generic "local crisis helpline" sentence instead. Don't sprinkle either on generic sadness.
- **No emojis** in any LLM output.
- **Structured output + JSON fallback**: every LLM call uses `llm.with_structured_output(...)` and falls back to raw JSON parsing on failure. Preserve both paths when editing.
- **Input/sampling caps**: `/analyze` rejects content >1000 chars (`main.py`). Month summary truncates at `MAX_ENTRIES=1000` (uniform-step sample) and `MAX_CONTENT_CHARS=400` per entry. Weekly caps at `WEEKLY_MAX_ENTRIES=60`.
- **Prompt-injection defense** lives inside each system prompt — keep it when editing prompts.

## Workflow

- Push only to `release/release`. The user merges to `main` via GitLab manually — **do not push to `main`**.
- AWS CLI / Console commands: **don't execute**. Provide the exact commands and let the user run them.
- Edit `.py` source files primarily. For `.md`, `.yml`, `template.yaml` changes, confirm with the user first.

## Environment

- `GEMINI_API_KEY` (required) — Google AI Studio key
- `API_AUTH_TOKEN` — currently unused on `/api/diary/analyze` (Bearer auth was reverted; see commit `be1952d`)
