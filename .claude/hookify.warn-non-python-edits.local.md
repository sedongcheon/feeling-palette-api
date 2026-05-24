---
name: warn-non-python-edits
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: ^(?!.*\.py$)(?!.*\.md$).+$
---

⚠️ **Python·문서 외 파일 수정 감지**

이 사용자는 Python 백엔드 개발자입니다. **`.py` 코드와 `.md` 문서**는
자유롭게 수정 가능하지만, 그 외 파일(`.yml`, `.json`, `.toml`, `Dockerfile*`,
`template.yaml`, 설정 파일 등)은 인프라성 변경이라 신중해야 합니다.

**확인할 점:**
- 정말 이 파일을 수정해야 하는 작업인가요?
- 사용자가 명시적으로 요청한 파일인가요?
- 혹시 동일한 변경을 Python 코드 또는 문서 안에서 처리할 수 있나요?

**권장 동작:**
- 명시적인 요청이 아니라면 작업을 중단하고 사용자에게 의도를 확인하세요.
- 설정/인프라 변경이 꼭 필요하다면 어떤 파일을 왜 수정하는지 먼저
  사용자에게 보고하세요.
