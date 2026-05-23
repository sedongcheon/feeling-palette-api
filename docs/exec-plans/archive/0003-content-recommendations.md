---
slug: content-recommendations
status: done
created: 2026-05-23
---

## Why

원래 product plan 의 두 번째 항목: "감정 상태에 맞는 따뜻한 위로의 문장
이나 콘텐츠(음악, 책) 추천". 기존 `/api/diary/analyze` 응답의 `comment`
는 30~60자 한 줄이라 광고를 본 사용자에게 줄 "보너스 콘텐츠" 로는 가벼움.
별도 엔드포인트로 분리하면 (a) 매 분석마다 비용·지연 부담 없이 (b)
사용자가 광고 보고 추가로 받는 흐름과 자연스럽게 매핑.

## What

새 엔드포인트 `POST /api/diary/recommend` 추가.

- `domains/emotions/types/__init__.py` — 새 모델 4개:
  - `RecommendRequest` (`content: str`, `locale: LocaleKey`)
  - `MusicRecommendation` (`title`, `artist`, `reason`)
  - `BookRecommendation` (`title`, `author`, `reason`)
  - `RecommendResponse` (`primary_emotion`, `comfort_message`,
    `music: List[MusicRecommendation]`, `books: List[BookRecommendation]`,
    `disclaimer: str`)
- `domains/emotions/config/__init__.py` — `llm_recommend` 인스턴스
  (`flash-lite`, 1024 max tokens, 30s timeout). 응답 사이즈가 위로 글 +
  3+3 추천 + 이유 다 들어가서 기본 `llm` (512) 으론 빠듯.
- `domains/emotions/service/__init__.py` — 다음 추가:
  - `RECOMMEND_SYSTEM_PROMPT` (한국어 베이스)
  - `RECOMMEND_LOCALE_EN_OVERRIDE`
  - `RECOMMEND_DISCLAIMER_KO`, `RECOMMEND_DISCLAIMER_EN` (상수)
  - `recommend_content(content, locale)` 함수. structured output + JSON
    fallback 패턴. 마지막에 disclaimer 를 서버측에서 강제 attach (LLM
    이 잊거나 변형하지 않도록).
- `domains/emotions/ui/routes.py` — `@router.post("/api/diary/recommend")`.
  기존 라우트와 같은 패턴: empty/over-cap 400, LLM 실패 500, None 가드.
- `tests/test_recommend.py` — LLM mock 으로 happy / length-too-long /
  whitespace / Gemini-fail / None-반환 가드 검증. 6+ 케이스.
- `CLAUDE.md` — 4 → 5 endpoints, 3 → 4 LLM instances 로 갱신.
- `docs/ARCHITECTURE.md`, `docs/RELIABILITY.md`, `docs/SECURITY.md`,
  `docs/product-specs/emotions.md` — 새 엔드포인트 반영.

### LLM 추천 신뢰성

LLM 이 가짜 곡·책을 만들 위험을 시스템 프롬프트로 완화:

- "실제 발표된 곡 / 출판된 책만"
- "유명·검증된 작품 (스트리밍·온라인 서점에서 쉽게 찾을 정도)"
- "확신 없는 작품은 차라리 빼고, 1개라도 정확한 게 낫다"
- "특정 종교·정치·강한 이념 회피"
- "자해·우울 깊은 본문에는 무거운 작품 회피"

거기에 서버측 disclaimer 가 매 응답에 따라옴:
- ko: "AI 가 추천하는 콘텐츠라 일부 정보가 정확하지 않을 수 있어요."
- en: "AI-generated recommendations may not be fully accurate."

Flutter UI 에서 이 문구를 추천 리스트 하단에 작게 노출 권장.

## Verification

- `pytest` 통과 (기존 16 + 신규 ~6)
- 로컬 dev 서버:
  - 짧은 본문 (`"기분이 우울해"`) → primary `sadness`, 위로 글 2~3문장,
    music/books 각 1~3개, 모든 항목에 `title`+`artist`/`author`+`reason`
    채워짐. disclaimer 정상 노출.
  - 정상 본문 (`"오늘 회사에서 짜증나는 일 있었어"`) → primary `anger`,
    적절한 추천.
  - 빈 content → 400
  - 1001자 content → 400
- 응답 schema: music·books 각 ≥1, ≤3. disclaimer 항상 비어있지 않음.

## Open questions / risks

- **할루시네이션 측정:** 실호출에서 가짜 작품이 얼마나 나오는지는
  운영에서 확인. 베타 사용자 피드백 받으면서 시스템 프롬프트 강화 가능.
- **추천 다양성:** 같은 감정에 같은 추천이 반복될 가능성. flash-lite 의
  temperature 기본값 (0.7~1.0)이라 어느 정도 분산. 필요시 명시 설정.
- **음악·책 카테고리 비율:** 1~3 으로 했지만 사용자가 음악 위주를
  원하는지, 책 위주인지 미지수. 일단 균등하게.
- **저작권/유료 콘텐츠 링크:** 일단 텍스트만 (제목·아티스트·저자).
  Spotify·Google Books 딥링크는 별도 작업.
- **광고 흐름과의 결합:** API 자체는 무조건 응답. "광고 본 후만 호출"
  은 Flutter 측 로직.

## Decision log

- 2026-05-23 — 새 엔드포인트 (vs `/api/diary/analyze` 확장). 매 분석에
  비용·지연 따라붙는 게 부담. 광고 후 보너스 흐름과 자연 매핑.
- 2026-05-23 — 구체 제목 추천 + disclaimer (vs 장르·작가 스타일만).
  사용자에게 더 명확한 가치, 신뢰성 부족분은 disclaimer 로 커버.
- 2026-05-23 — `llm_recommend` 새 인스턴스, 1024 tokens. 응답 크기 감안.
  모델은 다른 인스턴스와 동일 `flash-lite`.
- 2026-05-23 — disclaimer 는 LLM 이 아닌 서버에서 attach. 일관성·다국어
  관리 단순.
