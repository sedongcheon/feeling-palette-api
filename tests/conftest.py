import os

# ChatVertexAI 는 project 미지정 시 임포트 시점에 ADC 조회를 시도해
# 자격증명 없는 환경(CI/로컬 테스트)에서 ImportError 로 전파된다.
# 테스트는 라우트 레벨에서 LLM 을 mock 하므로 더미 프로젝트로 충분하다.
os.environ.setdefault("GCP_PROJECT", "test-project")
