# RELEASE.md — 릴리즈 흐름

`release/release` 브랜치 한 번 사이클을 도는 표준 절차. 매 변경마다 같은
순서로 굴려야 GitHub PR 머지 → 로컬 main 동기화 → 브랜치 정리까지 어긋남
없이 끝난다.

원칙은 [CLAUDE.md](../CLAUDE.md) 의 "Required loop" 와 동일하다:
**Plan → Execute → Verify → Push to `release/release`**. 이 문서는 마지막
두 단계(Verify, Push 이후 정리)를 구체화한다.

## 원격(remote) 사용 규칙

- **`github`** — 유일한 푸시/머지 경로. PR 도 여기서 연다.
- **`origin` (GitLab)** — 푸시는 hookify (`block-gitlab-push`) 로 차단되어
  있다. 사용자가 수동으로 동기화한다. 에이전트는 `git push origin ...`
  을 시도하지 않는다.

## 표준 사이클

### 1. 스테이징 (`git add`)

- 의미 있는 변경만 명시적으로 스테이징한다. `git add -A` / `git add .` 금지.
- 다음은 기본적으로 제외:
  - 빈 파일(0 bytes) — 의도가 있으면 사용자에게 확인 후 포함.
  - `.local` 접미사 파일 — 사용자별 로컬 설정. 예: `.claude/settings.local.json`.
    글로벌 `~/.config/git/ignore` 가 이미 일부를 가린다.
- `.claude/hookify.*.local.md` 처럼 팀에 공유할 의도가 있는 로컬 룰은
  사용자가 명시할 때만 포함한다.

### 2. 커밋

- 메시지는 **무엇을, 왜** 두 가지를 짧게. CLAUDE.md 의 git 규칙을 따른다.
- Co-Authored-By 한 줄을 끝에 붙인다 (Claude Code 기본 포맷).
- 한 PR 안에 여러 커밋이 와도 무방하다 (예: 기능 + 로컬 룰 추가).

### 3. 푸시

```bash
git push github release/release
```

`origin` 으로의 푸시는 hookify 가 차단한다. 실패 메시지를 보면 우회하지
말고 `github` 로만 다시 시도한다.

### 4. PR 생성

```bash
gh pr create --repo sedongcheon/feeling-palette-api \
  --base main --head release/release \
  --title "<70자 이내 요약>" \
  --body "$(cat <<'EOF'
## Summary
- 핵심 변경 1~3줄

## Test plan
- [ ] pip install -r requirements-dev.txt && pytest
- [ ] (UI/엔드포인트 변경 시) /docs 에서 수동 검증
EOF
)"
```

`release/release` → `main` 방향. 본문에는 Summary + Test plan 두 섹션을
항상 포함한다. PR 번호는 다음 단계에서 쓰니 받아 둔다.

### 5. 머지 전 로컬 검증

```bash
source venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

- 현재 pytest 커버리지는 `/api/v1/journal/analyze` 한 군데뿐이다. 다른
  엔드포인트를 만졌다면 `/docs` Swagger 로 수동 확인까지 한다
  ([RELIABILITY.md](RELIABILITY.md) "Verification" 참고).
- 실패하면 머지하지 않는다. 원인 파악 후 같은 브랜치에 추가 커밋.

### 6. 머지

```bash
gh pr merge <PR번호> --repo sedongcheon/feeling-palette-api --merge
```

- 기본 전략은 **merge commit**. squash/rebase 가 필요하면 사용자에게 먼저
  묻는다.
- 머지 결과 commit sha 를 받아 둔다. GitHub `main` 만 갱신된다.

### 7. 정리 (post-merge)

```bash
git checkout main
git pull github main
git branch -D release/release
git push github --delete release/release
```

- 로컬 `release/release` 는 `-d` 가 GitLab `origin/release/release` 대비
  unmerged 라고 거부할 수 있다. GitHub main 에 머지가 반영됐다면 `-D` 로
  강제 삭제해도 안전하다.
- GitLab `origin/release/release` 는 그대로 둔다. 사용자가 GitLab 흐름을
  수동으로 동기화한다.

### 8. 다음 사이클 준비

```bash
git checkout -b release/release
```

`main` 이 최신 상태인 시점에서 새 `release/release` 를 따고 1단계로
돌아간다.

## 자주 마주치는 예외

- **로컬 main 이 뒤쳐져 있을 때:** `git pull github main` 으로 fast-forward.
  conflict 가 나면 원인부터 보고 강제 reset 으로 덮지 않는다.
- **hookify 가 `git push origin` 을 막을 때:** 정상 동작. 우회 금지.
  GitLab 동기화는 사용자 몫이다.
- **빈 파일이 untracked 로 남아 있을 때:** 의도된 placeholder 인지 사용자에게
  확인. 임의로 삭제하지 않는다.
- **`.local` 파일이 untracked 로 보일 때:** 기본 제외. 사용자가 명시적으로
  "include" 요청한 경우에만 스테이징.

## 빠른 참조

```bash
# 1. 커밋
git add <files>
git commit -m "..."

# 2. 푸시 (github 만)
git push github release/release

# 3. PR
gh pr create --repo sedongcheon/feeling-palette-api \
  --base main --head release/release --title "..." --body "..."

# 4. 테스트
pytest

# 5. 머지
gh pr merge <N> --repo sedongcheon/feeling-palette-api --merge

# 6. 정리
git checkout main && git pull github main
git branch -D release/release
git push github --delete release/release

# 7. 다음 사이클
git checkout -b release/release
```
