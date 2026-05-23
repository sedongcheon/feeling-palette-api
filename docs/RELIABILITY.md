# Reliability

This service is one LLM call away from a 500. Most reliability work here is
about being deliberate at the boundaries: caps on input, structured output
with a fallback, and manual verification because there is no test suite.

## Input caps

| Endpoint                  | Cap                                                  | Where                                    |
|---------------------------|------------------------------------------------------|------------------------------------------|
| `POST /api/diary/analyze` | `content` ≤ 1000 chars (rejects with 400)            | `domains/emotions/ui/routes.py`          |
| `POST /api/month/summarize` | `MAX_ENTRIES = 1000` (uniform-step sampled), `MAX_CONTENT_CHARS = 400` per entry | `domains/emotions/service/__init__.py` |
| `POST /api/insights/weekly` | `WEEKLY_MAX_ENTRIES = 60` (most recent by date)    | `domains/emotions/service/__init__.py` |

These caps exist to keep cost and latency bounded under adversarial input.
Don't bump them without considering p99 latency and Gemini token cost.

## LLM provider

- **Model pin:** `gemini-2.5-flash-lite` for both `llm` and `llm_summary`.
  The flash-lite variant is intentional (cost) — **do not bump without
  asking.**
- **Two instances** in `domains/emotions/config/__init__.py`:
  - `llm` — 512 max output tokens, 30s timeout. Used by `/analyze`.
  - `llm_summary` — 2048 max output tokens, 60s timeout. Used by month
    summary and weekly insight (longer Korean output).
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

- 400 with `{"error": "..."}` for empty content / empty entries / over-cap
- 500 with `{"error": "..."}` for LLM failures (after both structured and
  fallback paths raise)

`logger.exception(...)` is called inside each 500 branch so the stack
trace lands in CloudWatch / Docker logs.

## Verification (no test suite)

After any change, manually verify:

1. Start `uvicorn apps.api.main:app --reload --port 8080`.
2. Open `http://localhost:8080/docs`.
3. For each touched endpoint, run a happy-path request with both
   `locale="ko"` and `locale="en"`.
4. For `/analyze`: try empty content (expect 400) and a 1001-char string
   (expect 400).
5. For month/weekly: try `entries=[]` (expect 400) and a realistic
   payload.

If a change can't be verified through the API (e.g. tweaking only a
prompt internal), say so explicitly in the PR — don't claim verification
you didn't do.
