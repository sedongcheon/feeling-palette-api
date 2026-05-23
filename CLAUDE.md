# CLAUDE.md — Feeling Palette API entry point

> **Mission.** A Korean emotion-analysis API. Diaries in, structured emotion
> data + warm Korean comment out. Three endpoints, one LLM provider (Gemini
> via LangChain), deployed to NAS (Docker) and AWS Lambda (SAM).
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
   model (`AnalyzeRequest` / `SummarizeRequest` / `WeeklyInsightRequest`);
   every LLM call uses `llm.with_structured_output(...)` with a Pydantic
   response model and falls back to raw JSON parsing. No untyped dicts
   crossing the service boundary. See [docs/RELIABILITY.md](docs/RELIABILITY.md).
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
3. **Verify by hitting the API.** No test suite. Run
   `uvicorn apps.api.main:app --reload --port 8080` and hit `/docs`
   (Swagger UI) for each touched endpoint.
4. **Push to `release/release`.** The user merges to `main` via GitLab
   manually — **do not push to `main`**.

## Knowledge tree (source of truth)

| Topic                          | Source of truth                                                              |
|--------------------------------|------------------------------------------------------------------------------|
| Architecture & layering        | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)                                 |
| Reliability (LLM, caps, fallbacks) | [docs/RELIABILITY.md](docs/RELIABILITY.md)                               |
| Security (safety hotline, prompt injection) | [docs/SECURITY.md](docs/SECURITY.md)                            |
| Exec-plan workflow             | [docs/PLANS.md](docs/PLANS.md)                                               |
| Active plans                   | [docs/exec-plans/active/](docs/exec-plans/active/)                           |
| Emotions domain spec           | [docs/product-specs/emotions.md](docs/product-specs/emotions.md)             |
| Feature/deploy guides (legacy) | [docs/](docs/) — files `01_*` ~ `09_*`                                       |

## Commands

```bash
# Local dev
source venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload --port 8080

# Container (NAS deploy path)
docker compose up --build           # exposes :8100 → :8080

# AWS Lambda (SAM)
sam build && sam deploy              # uses template.yaml
```

`GEMINI_API_KEY` must be set in `.env` (gitignored).

## Repository layout

```
apps/api/                  FastAPI app + Lambda adapter
domains/emotions/
  types/                   Pydantic request/response schemas
  config/                  Gemini LLM instances (llm, llm_summary)
  service/                 Korean system prompts + LLM orchestration
  ui/                      FastAPI router for the 3 endpoints
docs/                      ARCHITECTURE / RELIABILITY / SECURITY / PLANS,
                           plus exec-plans/ and product-specs/
Dockerfile, Dockerfile.lambda, docker-compose.yml, Jenkinsfile, template.yaml
```

## Non-obvious rules (quick reference; see docs for "why")

- **Output language follows `request.locale`** (`ko` default, `en` supported).
  Korean base prompts in `domains/emotions/service/__init__.py` are not
  translated; an `*_LOCALE_EN_OVERRIDE` block is appended for `en`. Extend
  the override, don't rewrite the base.
- **Emotion→color mapping is fixed** in the analyze system prompt. Never
  invent new HEX values.
- **No emojis** in any LLM output.
- **Input/sampling caps:** `/analyze` rejects content >1000 chars. Month
  summary truncates at `MAX_ENTRIES=1000` (uniform-step sample) and
  `MAX_CONTENT_CHARS=400` per entry. Weekly caps at `WEEKLY_MAX_ENTRIES=60`.
- **LLM model pin.** Both LLMs use `gemini-2.5-flash-lite`. Don't bump
  without asking — chosen for cost.
- **Prompt-injection defense** lives inside each Korean system prompt —
  preserve it when editing.

## Workflow rules

- Push only to `release/release`. User merges to `main` via GitLab — **do
  not push to `main`**.
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
