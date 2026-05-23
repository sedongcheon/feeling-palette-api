# Architecture

Feeling Palette is a single-domain Python service. The directory layout
mirrors the [harness-engineering](https://github.com/) layered convention
adapted for FastAPI + Pydantic: each domain is sliced into layers, and an
app shell wires the domain's `ui` router into a runnable FastAPI app.

## Layout

```
apps/api/
  main.py            FastAPI app, CORS, includes domain routers
  lambda_handler.py  Mangum adapter (AWS Lambda)
domains/emotions/
  types/             Pydantic request + response models
  config/            Three LangChain LLM instances (Gemini)
  service/           Korean system prompts + LLM orchestration
                     (analyze_diary / summarize_month / weekly_insight /
                      analyze_journal)
  ui/
    routes.py        FastAPI APIRouter — 4 POST endpoints, input
                     validation, error envelopes
tests/               pytest coverage for /api/v1/journal/analyze (only)
```

Currently one domain (`emotions`), four endpoints all backed by the same
LLM provider. A second domain would live under `domains/<name>/` with the
same layer split.

## Layering rules

Inside a domain, imports may only flow **down** the layer stack:

| Layer    | May import from                                |
|----------|------------------------------------------------|
| `types`  | (none — only stdlib + `pydantic`)              |
| `config` | `types` (rare; usually none)                   |
| `service`| `types`, `config`                              |
| `ui`     | `types`, `service`                             |

`ui` must never import `config` directly — the LLM instances are an
implementation detail of `service`. `service` must never import `ui`.

`apps/api/` may import a domain's `ui` router and request/response
`types`. It must never reach into `service` or `config` directly.

These rules are **not yet enforced by lint.** They are enforced by code
review and by this document. If a violation is needed for a real reason,
update this file in the same PR.

## Why this shape

- **Parse at the boundary.** Every endpoint's request and the LLM's
  response are Pydantic models. Untyped dicts never cross into `service`.
  See [RELIABILITY.md](RELIABILITY.md).
- **Prompts are part of the domain, not the app.** The Korean system
  prompts live in `domains/emotions/service/__init__.py` alongside the
  code that uses them — they are the dominant source of behavior, not a
  config detail.
- **One domain, one router.** Adding a new feature inside emotions
  (e.g. yearly insight) extends `service` + `ui/routes.py`. Adding a
  fundamentally different concern (e.g. user accounts) creates a new
  domain folder.

## What's intentionally absent

- **No `repo/` layer.** The service has no database. State lives in the
  caller (the diary app). If persistence is added later, add `repo/`
  per-domain and treat it as the lowest layer.
- **No `runtime/` layer.** Harness uses `runtime/` to wire
  service+repo+effects. Here `apps/api/main.py` does the only wiring
  needed: `include_router(emotions_router)`.
- **No `providers/`, `packages/`, `ops/` top-level dirs yet.** Add them
  when there's real content to put in them — empty scaffolding is a
  smell.
- **Tests are scoped to one endpoint.** Only `/api/v1/journal/analyze`
  has pytest coverage (`tests/test_journal_analyze.py`, mocking the LLM).
  Other endpoints are verified manually via `/docs` Swagger UI. See
  [RELIABILITY.md](RELIABILITY.md) for what to verify after a change.

## Deployment shape

- **NAS / Docker (`Dockerfile`, `docker-compose.yml`, `Jenkinsfile`).**
  Container CMD is `uvicorn apps.api.main:app --host 0.0.0.0 --port 8080`,
  exposed on host port 8100.
- **AWS Lambda (`Dockerfile.lambda`, `template.yaml`).** Image-based
  Lambda; CMD is `apps.api.lambda_handler.handler`. HttpApi fronts it
  with throttling 10rps / 20 burst.

Both targets use the same domain code; only the adapter differs.
