---
slug: harness-style-restructure
status: done
created: 2026-05-23
---

## Why

The project grew from a single-file prototype to three endpoints sharing
a Gemini LLM + Korean prompts, deployed on two targets (NAS + Lambda).
Flat layout (`main.py`, `service.py`, `models.py`, `config.py`) was fine
at three files but didn't give a place to add a second domain or a clear
layer rule for new contributors (human or agent). Modeled on
harness-engineering's domain-layered layout.

## What

Directory-only restructure. No code logic changes.

- Move `models.py` → `domains/emotions/types/__init__.py`
- Move `config.py` → `domains/emotions/config/__init__.py`
- Move `service.py` → `domains/emotions/service/__init__.py`
- Split `main.py`:
  - FastAPI app + CORS → `apps/api/main.py`
  - 3 routes → `domains/emotions/ui/routes.py` (as APIRouter)
- Move `lambda_handler.py` → `apps/api/lambda_handler.py`
- Update import paths to new dotted module locations.
- Update `Dockerfile` CMD to `uvicorn apps.api.main:app ...`.
- Update `Dockerfile.lambda` CMD to `apps.api.lambda_handler.handler`.
- Rewrite `CLAUDE.md` as a table of contents (invariants + knowledge
  tree). Move detailed rules to `docs/ARCHITECTURE.md`,
  `docs/RELIABILITY.md`, `docs/SECURITY.md`, `docs/PLANS.md`.
- Add `docs/product-specs/emotions.md`.

## Verification

- `python -c "import ast; [ast.parse(open(f).read()) for f in [...]]"`
  for syntax check across all moved files.
- `python -c "from apps.api.main import app; print(app.routes)"` with a
  stub `GEMINI_API_KEY` — confirms imports resolve and the 3 endpoints
  register.
- Manual: `uvicorn apps.api.main:app --reload --port 8080` and hit each
  endpoint via `/docs` once after merge.

## Decision log

- 2026-05-23 — Kept `Dockerfile`, `docker-compose.yml`, `Jenkinsfile`,
  `template.yaml` at repo root rather than moving to `ops/`. Reason:
  CI/CD on NAS Jenkins references repo root; deferring the `ops/` move
  to a follow-up plan with zero deploy risk.
- 2026-05-23 — Did **not** add a `runtime/` layer per harness convention.
  Reason: `apps/api/main.py` does the only wiring needed
  (`include_router`); adding `runtime/` now is empty scaffolding.
- 2026-05-23 — Did **not** introduce `eslint-plugin-boundaries`-equivalent
  lint enforcement (e.g. `import-linter`). Reason: out of scope for the
  step-1 restructure; tracked as a follow-up if the project grows past
  one domain.
