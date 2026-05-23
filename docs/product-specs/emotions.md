# Emotions domain — product spec

The only domain in this service. Reads diary text, returns structured
emotion data with a warm Korean (or English) comment.

## Endpoints

| Method | Path                       | Input shape                                                 | Output shape                                                                                  |
|--------|----------------------------|-------------------------------------------------------------|-----------------------------------------------------------------------------------------------|
| POST   | `/api/diary/analyze`       | `{ content: str, locale: "ko" \| "en" }`                    | `{ primary_emotion, emotions: {6 scores}, comment, color, palette: [5 HEX] }`                 |
| POST   | `/api/month/summarize`     | `{ year_month: "YYYY-MM", entries: EntryIn[], locale }`     | `{ summary, dominant_emotion }`                                                               |
| POST   | `/api/insights/weekly`     | `{ anchor_date: "YYYY-MM-DD", entries: EntryIn[], locale }` | `{ insight_text, trend, keyword, confidence, care_flag }`                                     |

Authoritative schemas: [`domains/emotions/types/__init__.py`](../../domains/emotions/types/__init__.py).

## Emotion vocabulary (fixed)

Six emotion keys. Each maps to an **anchor HEX** (the `color` field) and
a **5-color palette** (the `palette` field, `palette[0] == color`).
Anchor + palette are defined in `EMOTION_PALETTES`
(`domains/emotions/service/__init__.py`). The analyze `SYSTEM_PROMPT`
references the anchor only; the palette is attached server-side after
the LLM call. Changing requires updating `EmotionKey`, `EmotionScores`,
the prompt's color table, and `EMOTION_PALETTES` in the same PR.

| Key          | Korean   | Anchor    | Palette (anchor + 4 supporting)                                  |
|--------------|----------|-----------|------------------------------------------------------------------|
| `joy`        | 기쁨     | `#FFD700` | `#FFD700 #FFE57F #FFB300 #FFEBA1 #F5A623`                        |
| `sadness`    | 슬픔     | `#4A90D9` | `#4A90D9 #7AAEE5 #2C5F8E #B8D4ED #5B7C99`                        |
| `anger`      | 분노     | `#E74C3C` | `#E74C3C #FF6B5B #B83B2C #FFAAA0 #C0392B`                        |
| `anxiety`    | 불안     | `#9B59B6` | `#9B59B6 #B58CC8 #6F3D85 #DBC4E3 #6B5B95`                        |
| `calm`       | 평온     | `#2ECC71` | `#2ECC71 #5FD895 #21955A #B6EAC8 #A8C9A8`                        |
| `excitement` | 설렘     | `#FF69B4` | `#FF69B4 #FF93C7 #D44A8E #FFC1DD #F1C0B9`                        |

Supporting colors follow the pattern **light · deep · pale · muted** so
Flutter can use them for gradient backgrounds, accent borders, or text
contrast as needed.

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
