---
name: warn-non-python-edits
enabled: true
event: file
action: warn
conditions:
  - field: file_path
    operator: regex_match
    pattern: ^(?!.*\.py$).+$
---

⚠️ **Python 외 파일 수정 감지**

이 사용자는 Python 백엔드 개발자로, **`.py` 파일 수정만** 수행해야 합니다.

**확인할 점:**
- 정말 이 파일을 수정해야 하는 작업인가요? (`.md`, `.yml`, `.json`, `.toml`, 설정 파일 등)
- 사용자가 명시적으로 요청한 파일인가요?
- 혹시 동일한 변경을 Python 코드 안에서 처리할 수 있나요?

**권장 동작:**
- 명시적인 요청이 아니라면 작업을 중단하고 사용자에게 의도를 확인하세요.
- 문서/설정 변경이 꼭 필요하다면 어떤 파일을 왜 수정하는지 먼저 사용자에게 보고하세요.
