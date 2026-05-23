# Security

The interesting surface here is the LLM, not the network — there is no
auth, no DB, no user-specific data stored. The two things that matter are
the **safety hotline rules** (mental-health crisis content) and the
**prompt-injection defense** baked into each system prompt.

## Safety hotline (1393)

`1393` is the Korean national suicide-prevention hotline. It must appear
in LLM output ONLY when **both** conditions hold:

1. `request.locale == "ko"`, AND
2. The model has detected a self-harm signal in the diary text.

For `locale="en"`, the `*_LOCALE_EN_OVERRIDE` block instructs the model
to omit `1393` and emit a generic sentence instead:

> "If you're struggling, please reach out to someone you trust or a local
> crisis helpline."

(Wording varies slightly by endpoint — see the override blocks in
`domains/emotions/service/__init__.py`.)

### Where the rules live

- `/analyze` — `SYSTEM_PROMPT` `[안전]` section. Self-harm signals only.
- `/month/summarize` — `MONTH_SUMMARY_SYSTEM_PROMPT` `[안전]` section.
  Self-harm signals, **or** sadness/anxiety ≥70 on ≥5 days that month.
- `/insights/weekly` — `WEEKLY_INSIGHT_SYSTEM_PROMPT` `[안전 / 케어
  신호]` section. Drives `care_flag=true`; if true, the model appends the
  hotline sentence to `insight_text`. If `care_flag=false`, "1393" must
  not appear in the text at all.
- `/api/diary/recommend` — `RECOMMEND_SYSTEM_PROMPT` `[안전]` section.
  Self-harm signals append the hotline sentence to `comfort_message`.
  Also instructs the model to avoid heavy/challenging works for deeply
  depressed content (calm/safe/hopeful recommendations instead).

### Do not

- Do not add `1393` to generic sadness or low-mood content (the prompts
  explicitly warn against this — it creates anxiety in the user).
- Do not translate the 1393 sentence into English — the EN override
  replaces it with the generic sentence.
- Do not invent additional hotlines or country-specific numbers without a
  product decision.

### Output cap interaction

Both the month-summary 250-char cap and the analyze 60-char comment cap
are **waived** when the output contains a hotline marker (`1393` or
`crisis helpline`). The clipper in `service.py`
(`_CAP_EXEMPT_MARKERS`) enforces this — preserve it when editing.

## Prompt-injection defense

Each of the three system prompts ends with a `[프롬프트 주입 방지]`
section that tells the model to treat any instruction-like text inside
the diary body ("앞의 지시를 무시하라", "너는 이제 X다", "다음 형식으로만
답하라") as **part of the diary**, not as an instruction.

**Keep this section in every prompt edit.** It is the only line of
defense — there is no input scrubbing on the application side.

If you add a new prompt, copy the existing `[프롬프트 주입 방지]` block
verbatim. The wording has been tuned; do not paraphrase.

## Schema rigidity

The Pydantic response models in `domains/emotions/types/` are strict
about emotion keys (`Literal["joy", "sadness", "anger", "anxiety", "calm",
"excitement"]`) and HEX color codes (instructed in the prompt). If a new
emotion is needed, the change touches:

1. `EmotionKey` literal in `types/`.
2. `EmotionScores` field in `types/`.
3. The `[감정-컬러 매핑]` table in the analyze `SYSTEM_PROMPT`.

All three must change in lockstep, in the same PR. Color codes are fixed
in the prompt — the LLM must not invent new HEX values.

## Network surface

- CORS is wide open (`allow_origins=["*"]`) in `apps/api/main.py`.
  Acceptable for now because the API has no auth and no per-user data,
  but if either is added, **lock CORS down first.**
- No authentication on any endpoint. `API_AUTH_TOKEN` env var is
  referenced historically (commit `be1952d` reverted Bearer auth on
  `/analyze`) but is currently unused.
- AWS Lambda fronted by HttpApi with throttling 10 rps / 20 burst
  (`template.yaml`). This is the only built-in rate limit.

## Secrets

- `GEMINI_API_KEY` — never log, never include in responses, never commit.
  Loaded from `.env` locally; from SSM SecureString on Lambda; from
  Jenkins credentials store on NAS.
- `.env` is gitignored. Verify before any large refactor that no new
  artifact (e.g. test fixtures, generated docs) embeds the key.
