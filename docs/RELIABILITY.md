# Reliability

This service is one LLM call away from a 500. Most reliability work here is
about being deliberate at the boundaries: caps on input, structured output
with a fallback, and mostly-manual verification (the journal route has
pytest coverage; the rest do not).

## Input caps

| Endpoint                       | Cap                                                                              | Where                                    |
|--------------------------------|----------------------------------------------------------------------------------|------------------------------------------|
| `POST /api/diary/analyze`      | `content` ≤ 1000 chars (rejects with 400)                                        | `domains/emotions/ui/routes.py`          |
| `POST /api/month/summarize`    | `MAX_ENTRIES = 1000` (uniform-step sampled), `MAX_CONTENT_CHARS = 400` per entry | `domains/emotions/service/__init__.py`   |
| `POST /api/insights/weekly`    | `WEEKLY_MAX_ENTRIES = 60` (most recent by date)                                  | `domains/emotions/service/__init__.py`   |
| `POST /api/v1/journal/analyze` | `anonymized_text` 1~3000 chars (Pydantic 422); whitespace-only → 400             | `domains/emotions/types/__init__.py` + `routes.py` |
| `POST /api/diary/recommend`    | `content` ≤ 1000 chars (rejects with 400); whitespace-only → 400                 | `domains/emotions/ui/routes.py`          |

These caps exist to keep cost and latency bounded under adversarial input.
Don't bump them without considering p99 latency and Gemini token cost.

## LLM provider

- **Provider: Vertex AI** (`langchain-google-vertexai` / `ChatVertexAI`),
  switched from the Gemini Developer API on 2026-06-07. Reason: the
  Developer API forces prepaid billing for new accounts (2026-03-23
  policy); the prepaid balance hitting $0 caused the 2026-06-06 full
  outage (429 retry storm → Lambda timeouts). Vertex bills postpaid via
  the `feeling-palette` GCP project's Cloud Billing account. Auth: SA
  JSON via `GCP_SA_KEY_JSON` env (Lambda, base64-injected at deploy) or
  ADC `GOOGLE_APPLICATION_CREDENTIALS` (local). See
  docs/exec-plans/ `vertex-ai-migration` for the full decision log.
- **Model pin:** `gemini-3.1-flash-lite` for all four instances
  (adopted 2026-06-07 on Vertex, ~3× cost of 2.5-flash-lite, accepted by
  user). The earlier 3.1 failure (attempt 2 below) was specific to the
  `langchain-google-genai` Developer-API path; on Vertex the full
  verification gate passed: structured output schema compliance on all
  5 endpoints, `1393` rule for ko self-harm, generic-helpline rule for
  en, fixed diary palette mapping. **Do not bump without asking**, and
  re-run that same gate when evaluating any model change. Two earlier
  upgrade attempts on the Developer API were reverted:
  1. `gemini-2.5-flash` (2026-05-22): its thinking tokens consume the
     entire `max_output_tokens` budget, so `with_structured_output(...)`
     returns `None` instead of raising, which the routers used to forward
     as `200 OK` with body `null`. Existing Flutter clients then crash on
     deserialization. The router None-guards (below) cover the failure
     mode, but flash-lite is the actual fix. Adding `thinking_budget=0`
     fixes the silent-None but yields no measurable quality gain over
     flash-lite at ~3.3× cost (see [[feedback-gemini-flash-experiment]]).
  2. `gemini-3.1-flash-lite` (2026-05-24, GA model 2026-05-07):
     `with_structured_output(Pydantic)` is silently broken — the current
     pinned `langchain-google-genai>=2.0.0` cannot constrain the schema
     for the 3.1 family, and the model returns its own freeform JSON
     shape (e.g. `{message, suggestions, support_hotline}`). The service
     fallback path didn't trigger because the existing `try/except`
     catches exceptions only, not silent `None`. Additionally, 3.1 has
     its own safety overlay that overrode our `1393` hotline rule with
     `109` in at least one observation. Until langchain integration
     catches up, 3.1 is not usable.

  Treat "Gemini X.Y is GA" and "we can use it in production" as
  independent statements. Always re-verify Korean-specific safety prompts
  (1393 hotline rule) and `with_structured_output` schema compliance
  when evaluating a new model.
- **Four instances** in `domains/emotions/config/__init__.py`, all with
  `max_retries=1` (the langchain default of 6 turned a single Gemini
  429/slow call into a Lambda-killing retry storm on 2026-06-06):
  - `llm` — 512 max output tokens. Used by `/api/diary/analyze`.
  - `llm_summary` — 2048 max output tokens. Used by month summary and
    weekly insight (longer Korean output).
  - `llm_journal` — 1024 max output tokens. Used by
    `/api/v1/journal/analyze` (response carries emotions[], themes[],
    empathy_response, color_reasoning — bigger than `llm`'s 512).
  - `llm_recommend` — 1024 max output tokens. Used by
    `/api/diary/recommend` (comfort_message + music/books × up to 3 with
    title/artist/author/reason fields each).
- **Timeout budget:** `ChatVertexAI` has no constructor timeout, so the
  service layer wraps every call in `asyncio.wait_for` via `_ainvoke()`
  — 10s per call (`LLM_TIMEOUT_S`), 18s for summary/weekly
  (`LLM_SUMMARY_TIMEOUT_S`). Budget: primary(10s) + fallback(10s) +
  cold start(~2s) must fit Lambda's 30s / API Gateway's ~29s hard cap.
  Raising the Lambda timeout does NOT help — API Gateway HTTP API caps
  integration at ~29s.
- **Credentials:** `GCP_SA_KEY_JSON` (JSON string or base64) takes
  priority; falls back to ADC. `GCP_PROJECT` derives from the SA JSON's
  `project_id` when unset. `GCP_LOCATION` defaults to `global`.

## Structured output + JSON fallback

Every LLM call in `domains/emotions/service/__init__.py` follows the same
pattern:

```python
structured_llm = llm.with_structured_output(ResponseModel)
try:
    return await structured_llm.ainvoke(messages)
except Exception:
    logger.exception("Structured ... failed; fallback")
    # Re-invoke with an explicit "JSON only" instruction and parse manually
    response = await llm.ainvoke(fallback_messages)
    data = json.loads(response.content)
    return ResponseModel(**data)
```

**Preserve both paths when editing.** The structured path is the primary;
the fallback exists because Gemini occasionally returns malformed
structured output, especially under unusual locale conditions.

## Hard caps on output

`/api/month/summarize` enforces a 250-character hard cap on `summary`
after the LLM returns (`_enforce_summary_cap` in service). The clipper
breaks at the last sentence boundary, then word boundary, then mid-word
with `…`. The cap is **waived** if the output contains a `1393` or
`crisis helpline` marker — those sentences must survive the cap.

If a future endpoint also needs a hard cap, copy the `_clip_to_sentence` +
`_enforce_summary_cap` pattern; do not write a new clipper.

## Error envelope

Each endpoint in `domains/emotions/ui/routes.py`:

- 400 with `{"error": "..."}` for empty content / empty entries / empty
  `user_id_hash` / over-cap (where over-cap isn't already a Pydantic 422)
- 422 (FastAPI default) for Pydantic validation failures —
  `/api/v1/journal/analyze` relies on this for the 1~3000 char bound and
  the hex color pattern on the response
- 500 with `{"error": "..."}` for LLM failures on the three original
  endpoints (after both structured and fallback paths raise, **or** the
  service silently returns `None` — see None-guards below)
- 502 with `{"error": "AI 분석 일시 실패", "retryable": true}` for LLM
  failures on `/api/v1/journal/analyze` — the contract calls out
  retryability explicitly so the diary client can back off and retry.
  Applies to both raised exceptions and silent `None` returns.

**Why the None-guard exists.** `with_structured_output(...)` can return
`None` instead of raising when the model truncates / emits no parseable
JSON (observed with `gemini-2.5-flash` consuming all tokens on thinking).
Without the guard, the route returns `200 OK` with body `null`, which
Flutter clients deserialize as a crash. Every route MUST check
`if result is None` before returning the service result.

`logger.exception(...)` is called inside each failure branch so the
stack trace lands in CloudWatch / Docker logs.

## Verification

The `/api/v1/journal/analyze` route has pytest coverage in
`tests/test_journal_analyze.py` (happy path with mocked LLM, text-too-long
422, whitespace-only 400, Gemini-failure 502). Run with:

```bash
pip install -r requirements-dev.txt
pytest
```

For everything else, manually verify:

1. Start `uvicorn apps.api.main:app --reload --port 8080`.
2. Open `http://localhost:8080/docs`.
3. For each touched endpoint, run a happy-path request with both
   `locale="ko"` and `locale="en"`.
4. For `/api/diary/analyze`: try empty content (expect 400) and a
   1001-char string (expect 400).
5. For month/weekly: try `entries=[]` (expect 400) and a realistic
   payload.

If a change can't be verified through the API (e.g. tweaking only a
prompt internal), say so explicitly in the PR — don't claim verification
you didn't do.
