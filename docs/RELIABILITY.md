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

- **Model pin:** `gemini-2.5-flash-lite` for all four instances. **Do
  not bump without asking** — `gemini-2.5-flash` was tried and reverted:
  its thinking tokens consume the entire `max_output_tokens` budget, so
  `with_structured_output(...)` returns `None` instead of raising, which
  the routers used to forward as `200 OK` with body `null`. Existing
  Flutter clients then crash on deserialization. The router None-guards
  (below) cover the failure mode, but flash-lite is the actual fix.
- **Four instances** in `domains/emotions/config/__init__.py`:
  - `llm` — 512 max output tokens, 30s timeout. Used by `/api/diary/analyze`.
  - `llm_summary` — 2048 max output tokens, 60s timeout. Used by month
    summary and weekly insight (longer Korean output).
  - `llm_journal` — 1024 max output tokens, 30s timeout. Used by
    `/api/v1/journal/analyze` (response carries emotions[], themes[],
    empathy_response, color_reasoning — bigger than `llm`'s 512).
  - `llm_recommend` — 1024 max output tokens, 30s timeout. Used by
    `/api/diary/recommend` (comfort_message + music/books × up to 3 with
    title/artist/author/reason fields each).
- **API key:** `GEMINI_API_KEY` env var, loaded via `python-dotenv`
  locally and the deployment platform's secret store otherwise.

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
