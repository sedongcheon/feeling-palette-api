---
name: block-gitlab-push
enabled: true
event: bash
action: block
pattern: (^|\s|;|&&|\|\|)git\s+push\b.*?(\borigin\b|git\.sedoli\.cloud)
---

🚫 **GitLab(`origin`) 푸시 차단**

이 사용자는 **배포 채널을 GitHub로만 운영**하기로 결정했습니다.
GitLab(`origin` / `git.sedoli.cloud`)으로의 `git push`는 차단됩니다.

**상황 정리:**
- `origin` 리모트 = GitLab (`git.sedoli.cloud`) — 푸시 금지
- `github` 리모트 = GitHub (`github.com/sedongcheon/...`) — 배포용, 허용

**올바른 명령:**
```
git push github release/release
```
또는 명시적 URL:
```
git push https://github.com/sedongcheon/feeling-palette-api.git release/release
```

**예외가 필요하면:**
사용자에게 명시적으로 "이번만 GitLab에 푸시해도 되나?"를 묻고 허락을 받은 뒤에만 실행하세요. 자동으로 두 곳에 동시 푸시하지 마세요.

**영향 받지 않는 명령:** `git fetch origin`, `git pull origin ...`, `git remote -v` 등 읽기 작업은 그대로 허용됩니다.
