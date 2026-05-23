# CLAUDE.md — Feeling Palette API entry point

> **Mission.** A Korean emotion-analysis API. Diaries in, structured emotion
> data + warm Korean comment out. Four endpoints, one LLM provider (Gemini
> via LangChain). **Production = AWS Lambda (SAM).** NAS (Docker) exists
> as a local / auxiliary container path.
>
> **Operating principle.** Humans steer. Agents execute. Keep the surface
> small; keep the prompts honest.

This file is a **table of contents.** Detailed rules live under `docs/`.
Keep this file under ~120 lines.

## Top-3 invariants

1. **Layered architecture per domain.** `domains/<name>/` is split into
   `types → config → service → ui`. Cross-layer rule: `ui` may import
   `service`, `service` may import `config`/`types`, `types` and `config`
   never import upward. App wiring (`apps/api/`) only imports a domain's
   `ui` router and uses domain types at the boundary. See
   [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).
2. **Parse at the boundary.** Every endpoint accepts a Pydantic request
   model (`AnalyzeRequest` / `SummarizeRequest` / `WeeklyInsightRequest` /
   `JournalAnalyzeRequest`); every LLM call uses
   `llm.with_structured_output(...)` with a Pydantic response model and
   falls back to raw JSON parsing. No untyped dicts crossing the service
   boundary. See [docs/RELIABILITY.md](docs/RELIABILITY.md).
3. **Safety hotline is locale-gated.** `1393` may appear ONLY when
   `locale="ko"` AND a self-harm signal is detected. For `locale="en"` the
   override emits a generic "local crisis helpline" sentence. Never sprinkle
   either on generic sadness. See [docs/SECURITY.md](docs/SECURITY.md).

## Required loop (every change)

1. **Plan.** For non-trivial changes, drop a short plan in
   `docs/exec-plans/active/<slug>.md` (template:
   [docs/PLANS.md](docs/PLANS.md)). Trivial diffs can skip this.
2. **Execute.** Edit `.py` only inside `apps/` or `domains/`. For changes
   under `ops/`, `Dockerfile*`, `template.yaml`, or any `.md`/`.yml`,
   confirm with the user first.
3. **Verify by hitting the API.** Default is manual via `/docs` Swagger
   UI (`uvicorn apps.api.main:app --reload --port 8080`). The
   `/api/v1/journal/analyze` route has pytest coverage
   (`pip install -r requirements-dev.txt && pytest`); add tests there if
   you touch its types/service. The other three endpoints stay manual.
4. **Ship via `release/release` → GitHub PR.** Push to `github`, open PR
   `release/release → main`, `pytest`, merge commit, clean up. Sequence:
   [docs/RELEASE.md](docs/RELEASE.md). GitLab `main` is user-managed —
   **do not push to `main`**.

## Knowledge tree (source of truth)

| Topic                          | Source of truth                                                              |
|--------------------------------|------------------------------------------------------------------------------|
| Architecture & layering        | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                                 |
| Reliability (LLM, caps, fallbacks) | [docs/RELIABILITY.md](docs/RELIABILITY.md)                               |
| Security (safety hotline, prompt injection) | [docs/SECURITY.md](docs/SECURITY.md)                            |
| Exec-plan workflow             | [docs/PLANS.md](docs/PLANS.md)                                               |
| Release flow (PR → merge → cleanup) | [docs/RELEASE.md](docs/RELEASE.md)                                     |
| Active plans                   | [docs/exec-plans/active/](docs/exec-plans/active/)                           |
| Emotions domain spec           | [docs/product-specs/emotions.md](docs/product-specs/emotions.md)             |
| Feature/deploy guides (legacy) | [docs/](docs/) — files `01_*` ~ `09_*`                                       |

## Commands

```bash
# Local dev
source venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload --port 8080

# AWS Lambda (SAM) — production deploy. Run yourself; agent never executes.
sam build && sam deploy              # uses template.yaml

# Container (NAS / local-only)
docker compose up --build           # exposes :8100 → :8080
```

`GEMINI_API_KEY` must be set in `.env` (gitignored).

## Repository layout

```
apps/api/                  FastAPI app + Lambda adapter
domains/emotions/
  types/                   Pydantic request/response schemas
  config/                  Gemini LLM instances (llm, llm_summary, llm_journal)
  service/                 Korean system prompts + LLM orchestration
  ui/                      FastAPI router for the 4 endpoints
tests/                     pytest coverage for /api/v1/journal/analyze (only)
docs/                      ARCHITECTURE / RELIABILITY / SECURITY / PLANS,
                           plus exec-plans/ and product-specs/
Dockerfile, Dockerfile.lambda, docker-compose.yml, Jenkinsfile, template.yaml
```

## Non-obvious rules (quick reference; see docs for "why")

- **Output language follows `request.locale`** (`ko` default, `en` supported).
  Korean base prompts in `domains/emotions/service/__init__.py` are not
  translated; an `*_LOCALE_EN_OVERRIDE` block is appended for `en`. Extend
  the override, don't rewrite the base.
- **Emotion→color mapping is fixed** for `/api/diary/analyze` (6 emotions
  → 6 fixed HEX). The `/api/v1/journal/analyze` route intentionally uses a
  variable palette per the journal prompt's color guidance. Never invent
  new HEX values for the diary route.
- **No emojis** in any LLM output.
- **Input/sampling caps:** `/api/diary/analyze` rejects content >1000
  chars. `/api/v1/journal/analyze` rejects `anonymized_text` outside
  1~3000 chars (Pydantic 422). Month summary truncates at
  `MAX_ENTRIES=1000` (uniform-step sample) and `MAX_CONTENT_CHARS=400`
  per entry. Weekly caps at `WEEKLY_MAX_ENTRIES=60`.
- **LLM model pin.** All three instances use `gemini-2.5-flash-lite`.
  Don't bump without asking — `gemini-2.5-flash` was tried but its
  thinking tokens consume `max_output_tokens` and `with_structured_output`
  returns `None` (200 OK with `null` body). flash-lite avoids that.
- **Prompt-injection defense** lives inside each Korean system prompt —
  preserve it when editing.

## Workflow rules

- Push only to `release/release` on the `github` remote. `origin` (GitLab)
  is blocked by hookify; user syncs GitLab manually. **Never push to `main`.**
  Full release sequence: [docs/RELEASE.md](docs/RELEASE.md).
- AWS CLI / Console commands: **don't execute.** Provide the exact commands
  and let the user run them.
- Edit `.py` inside `apps/` or `domains/` primarily. For `.md`, `.yml`,
  `Dockerfile*`, `template.yaml` changes, confirm with the user first.

## Environment

- `GEMINI_API_KEY` (required) — Google AI Studio key.
- `API_AUTH_TOKEN` — currently unused on `/api/diary/analyze` (Bearer auth
  was reverted; see commit `be1952d`).

## When you (the agent) get stuck

The harness layout is light by design — there's no DB layer, no
provider package, no ESLint boundary enforcement yet. If the shape of a
task doesn't fit (e.g. cross-domain dependency, new external integration),
file the gap as an exec-plan rather than improvising. The structure is
meant to grow with intent, not by accretion.
