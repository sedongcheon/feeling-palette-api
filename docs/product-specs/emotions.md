# Emotions domain — product spec

The only domain in this service. Reads diary text, returns structured
emotion data with a warm Korean (or English) comment.

## Endpoints

| Method | Path                       | Input shape                                                 | Output shape                                                                                  |
|--------|----------------------------|-------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| POST   | `/api/diary/analyze`       | `{ content: str, locale: "ko" \| "en" }`                    | `{ primary_emotion, emotions: {6 scores}, comment, color }`                                   |
| POST   | `/api/month/summarize`     | `{ year_month: "YYYY-MM", entries: EntryIn[], locale }`     | `{ summary, dominant_emotion }`                                                               |
| POST   | `/api/insights/weekly`     | `{ anchor_date: "YYYY-MM-DD", entries: EntryIn[], locale }` | `{ insight_text, trend, keyword, confidence, care_flag }`                                     |

Authoritative schemas: [`domains/emotions/types/__init__.py`](../../domains/emotions/types/__init__.py).

## Emotion vocabulary (fixed)

Six emotion keys, fixed HEX colors. Defined in the analyze
`SYSTEM_PROMPT`; changing requires updating `EmotionKey`, `EmotionScores`,
and the prompt's color table in the same PR.

| Key          | Korean   | HEX       |
|--------------|----------|-----------|
| `joy`        | 기쁨     | `#FFD700` |
| `sadness`    | 슬픔     | `#4A90D9` |
| `anger`      | 분노     | `#E74C3C` |
| `anxiety`    | 불안     | `#9B59B6` |
| `calm`       | 평온     | `#2ECC71` |
| `excitement` | 설렘     | `#FF69B4` |

## Tone rules

- **Comment / summary / insight tone:** warm, gentle, polite Korean (or
  English under `locale="en"`). No judgment, diagnosis, advice, or
  preaching — only reflect the user's feelings back.
- **No emojis** anywhere in LLM output.
- **No PII fabrication.** The model uses only what's in the diary; it
  never invents names, places, or numbers.

Sentence-length targets per endpoint live in the prompt; the
month-summary 250-char cap is also enforced post-hoc by
`_enforce_summary_cap` in `domains/emotions/service/__init__.py`.

## Safety

See [docs/SECURITY.md](../SECURITY.md) for the 1393 / crisis-helpline
rules.

## Open questions

- Should we expose a `/health` endpoint distinct from `/docs`? Jenkins
  currently health-checks `/docs`, which works but conflates "Swagger
  loaded" with "LLM is reachable."
- Should the weekly insight `care_flag=true` response also include a
  structured signal field (separate from `insight_text`) for the client
  to display differently? Right now the client has to detect "1393" in
  the text.
