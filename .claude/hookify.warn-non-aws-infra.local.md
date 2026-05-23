---
name: warn-non-aws-infra
enabled: true
event: bash
action: warn
pattern: (^|\s|;|&&|\|\|)(kubectl|terraform|tf|helm|docker|docker-compose|gcloud|az|minikube|kustomize|ansible)\b
---

⚠️ **AWS 외 인프라 CLI 감지**

이 사용자는 인프라 작업을 **AWS 명령어 요청만** 하도록 정의했습니다.
다른 인프라 도구(kubectl, terraform, docker, gcloud, azure 등)는 사용 범위 밖입니다.

**확인할 점:**
- 이 작업이 정말 필요한가요? AWS 서비스로 대체 가능한가요?
- 사용자가 명시적으로 이 도구 사용을 허락했나요?

**권장 동작:**
- 명시적 허락이 없다면 명령 실행을 멈추고 의도를 확인하세요.
- AWS로 처리 가능하다면 AWS CLI 명령어 가이드만 제공하고 사용자가 직접 실행하도록 안내하세요. (참고: 사용자는 AWS CLI도 직접 실행함)
