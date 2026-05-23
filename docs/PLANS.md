# Exec-plan workflow

For non-trivial changes, drop a short plan in
`docs/exec-plans/active/<slug>.md` before writing code. Move it to
`docs/exec-plans/archive/` (or delete) once the change ships.

Trivial diffs — a typo in a prompt, a doc tweak, a one-line bug fix —
don't need a plan. Use judgment: if the change touches more than one
file or involves a design decision, write the plan.

## Template

```markdown
---
slug: <kebab-case>
status: active   # active | done | abandoned
created: YYYY-MM-DD
---

## Why

One paragraph. What changed in the world that makes this work necessary
now? If you can't answer this, the plan isn't ready.

## What

Concrete changes, listed by file. Be specific.

- `domains/emotions/service/__init__.py` — add foo()
- `domains/emotions/types/__init__.py` — extend FooResponse with `bar` field
- `docs/SECURITY.md` — note the new prompt-injection consideration

## Verification

How will you know the change works? With no test suite, this is usually:

- Hit `/docs`, run endpoint X with payload Y, expect Z
- Confirm logs show the fallback path is still wired

## Open questions / risks

Anything you're unsure about. Default to listing more, not fewer — the
plan exists to surface decisions before they harden into code.

## Decision log

Append-only. Each entry: date, decision, reason.
```

## Why bother

- A 5-minute plan often kills a 2-hour wrong implementation.
- The "Why" line dates well: a year from now, the commit message tells
  you *what* changed, but only the plan tells you *why now*.
- Exec-plans are also the place to register that you can't finish
  something — half-finished work + a plan beats half-finished work alone.

## Anti-patterns

- **Writing the plan after the code.** Defeats the point. If you've
  already written the diff, just open the PR.
- **Boilerplate plans.** "Implement feature X" is not a plan. Either
  there's a real "why" worth writing down, or there isn't and you should
  skip the plan.
- **Stale `active/`.** If something is in `active/` for more than two
  weeks without progress, move it to `archive/` with status `abandoned`
  or revive it. Don't let the directory rot.
