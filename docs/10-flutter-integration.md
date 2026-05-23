# Flutter 통합 가이드 — palette + recommend

> 이 문서는 백엔드 신규/변경(2026-05-23 머지)을 Flutter 앱에 붙이기 위한
> 가이드입니다. 대상: 색상 팔레트 확장 (`/api/diary/analyze`) + 새 추천
> 엔드포인트 (`/api/diary/recommend`).

## 1. 베이스 URL

```
https://feeling-api-aws.sedoli.co.kr
```

- 타임아웃은 LLM 응답 고려해서 **15~20초** 권장
- Lambda throttling: 10 rps / 20 burst (`template.yaml`)
- 인증 없음 — 그대로 호출

## 2. 변경/추가 엔드포인트 요약

| 변경        | 엔드포인트                  | 영향                                                 |
|-------------|-----------------------------|------------------------------------------------------|
| 필드 추가   | `POST /api/diary/analyze`   | 응답에 `palette: List<String>` (HEX 5개) 추가         |
| 신규        | `POST /api/diary/recommend` | 위로 문장 + 음악/책 추천 + disclaimer                 |

호환성:
- `analyze` 의 기존 `color` 필드는 그대로 유지. `palette[0] == color`.
  구버전 클라이언트는 영향 없음.
- `recommend` 는 완전 신규 — 광고 시청 후 보너스 콘텐츠 흐름에 사용.

## 3. Dart 모델 (예시)

### 3-1. `/api/diary/analyze` — palette 필드 추가

```dart
class AnalyzeResponse {
  final String primaryEmotion;
  final Map<String, int> emotions;
  final String comment;
  final String color;             // 기존
  final List<String> palette;     // 신규, palette[0] == color

  AnalyzeResponse.fromJson(Map<String, dynamic> j)
    : primaryEmotion = j['primary_emotion'],
      emotions = Map<String, int>.from(j['emotions']),
      comment = j['comment'],
      color = j['color'],
      palette = (j['palette'] as List?)?.cast<String>() ?? [j['color']];
      // ?? 는 구버전 서버 호환용 안전망. 신서버는 항상 5개.
}
```

### 3-2. `/api/diary/recommend` — 신규

```dart
class MusicRecommendation {
  final String title, artist, reason;
  MusicRecommendation.fromJson(Map<String, dynamic> j)
    : title = j['title'], artist = j['artist'], reason = j['reason'];
}

class BookRecommendation {
  final String title, author, reason;
  BookRecommendation.fromJson(Map<String, dynamic> j)
    : title = j['title'], author = j['author'], reason = j['reason'];
}

class RecommendResponse {
  final String primaryEmotion;
  final String comfortMessage;
  final List<MusicRecommendation> music;
  final List<BookRecommendation> books;
  final String disclaimer;        // 반드시 화면에 노출

  RecommendResponse.fromJson(Map<String, dynamic> j)
    : primaryEmotion = j['primary_emotion'],
      comfortMessage = j['comfort_message'],
      music = (j['music'] as List)
          .map((e) => MusicRecommendation.fromJson(e)).toList(),
      books = (j['books'] as List)
          .map((e) => BookRecommendation.fromJson(e)).toList(),
      disclaimer = j['disclaimer'] ?? '';
}
```

## 4. API 클라이언트

```dart
Future<RecommendResponse> recommend({
  required String content,
  String locale = 'ko',
}) async {
  final res = await http.post(
    Uri.parse('$baseUrl/api/diary/recommend'),
    headers: {'Content-Type': 'application/json'},
    body: jsonEncode({'content': content, 'locale': locale}),
  ).timeout(const Duration(seconds: 20));

  if (res.statusCode == 400) {
    throw RecommendBadRequest(jsonDecode(res.body)['error']);
  }
  if (res.statusCode != 200) {
    // 500: LLM 일시 실패 — 재시도 안내
    throw RecommendServerError(res.statusCode);
  }
  return RecommendResponse.fromJson(jsonDecode(res.body));
}
```

요청 본문:
```json
{ "content": "...", "locale": "ko" }
```

응답 본문 (예):
```json
{
  "primary_emotion": "sadness",
  "comfort_message": "오늘 하루 정말 힘드셨겠어요. ...",
  "music": [
    { "title": "...", "artist": "...", "reason": "..." }
  ],
  "books": [
    { "title": "...", "author": "...", "reason": "..." }
  ],
  "disclaimer": "AI 가 추천하는 콘텐츠라 일부 정보가 정확하지 않을 수 있어요."
}
```

`music`, `books` 각각 1~3개 (서버 보장).

## 5. UI 통합 포인트

### 5-1. 광고 → 추천 흐름

1. 광고 시청 완료 콜백에서 `recommend(content: 오늘의일기, locale: 현재locale)` 호출
2. 로딩 인디케이터 노출 (10~15초까지 발생 가능)
3. 결과 화면 구성:
   - 헤더: `primaryEmotion` 뱃지 (분석 화면 색상 재사용 가능)
   - 위로 문장 (`comfortMessage`)
   - 🎵 음악 카드 1~3개 — title, artist, reason
   - 📚 책 카드 1~3개 — title, author, reason
   - **하단에 `disclaimer` 작은 회색 텍스트** ← 필수 (아래 §7 참고)
4. 중복 호출 방지: 같은 일기로 광고 다시 봐도 새 추천 받을지 여부는 제품 결정 사항

### 5-2. Palette 활용 (선택)

분석 결과 화면 디자인 업그레이드 여지:

| 인덱스       | 톤        | 활용 예시                            |
|--------------|-----------|--------------------------------------|
| `palette[0]` | anchor    | 메인 색상 (기존 `color` 와 동일)     |
| `palette[1]` | light     | 그라데이션 보조색                    |
| `palette[2]` | deep      | 강조 보더 / 강한 텍스트              |
| `palette[3]` | pale      | 배경 카드 톤                         |
| `palette[4]` | muted     | 부드러운 텍스트 컨테이너             |

6개 감정(joy, sadness, anger, anxiety, calm, excitement) 각각 5색 고정 매핑.
서버 측 `EMOTION_PALETTES` 가 단일 진실 — Flutter 에서 같은 HEX 를 재정의
하지 말 것 (드리프트 위험).

## 6. 에러 처리 정책

| 코드     | 의미                       | 권장 UX                                                |
|----------|----------------------------|--------------------------------------------------------|
| 400      | 입력 비어있음 / 1000자 초과 | "일기를 1~1000자로 작성해주세요"                       |
| 500      | LLM 일시 실패              | "추천을 가져오지 못했어요. 다시 시도해주세요" + 재시도  |
| timeout  | Lambda cold start 등       | 자동 1회 재시도 후 위와 동일                           |
| 4xx 기타 | 거의 발생 안 함            | "일시 오류 — 잠시 후 다시"                             |

## 7. 반드시 지킬 것

- **`disclaimer` 노출**: LLM 이 가짜 곡/책을 만들 위험이 있어서, 사용자에게
  미리 알리기 위한 텍스트. 추천 리스트 하단에 작은 회색 글씨로. 백엔드
  `CLAUDE.md` 의 안전 규칙.
- **`primary_emotion` 처리**: `recommend` 응답의 값은 `analyze` 와 같은
  6 키 (`joy/sadness/anger/anxiety/calm/excitement`). 같은 색상 매핑 재사용
  가능.
- **광고 정책**: 추천은 "보너스 콘텐츠" 위치. 광고 미시청 사용자에게도
  일기 분석은 정상 작동해야 함 — 추천만 잠금.
- **locale**: 기존 `analyze` 와 동일하게 앱 설정 따라 전달. en 응답은
  `comfort_message` / `reason` / `disclaimer` 모두 영문.

## 8. 빠른 동작 확인 curl

```bash
# ko
curl -s -X POST https://feeling-api-aws.sedoli.co.kr/api/diary/recommend \
  -H 'Content-Type: application/json' \
  -d '{"content":"오늘 우울해","locale":"ko"}' | jq .

# en
curl -s -X POST https://feeling-api-aws.sedoli.co.kr/api/diary/recommend \
  -H 'Content-Type: application/json' \
  -d '{"content":"Today was rough.","locale":"en"}' | jq .

# palette
curl -s -X POST https://feeling-api-aws.sedoli.co.kr/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"오늘은 기분이 너무 좋았어","locale":"ko"}' | jq .
```

## 9. 향후 작업 후보 (아직 미구현)

- 음악/책 항목에 Spotify / Google Books 딥링크 추가
- 같은 일기 → 같은 추천 캐싱 (또는 매번 새 추천 정책)
- 추천 다양성 튜닝 (현재 temperature 기본값)

이 항목은 백엔드 추가 작업이 필요하면 별도 exec-plan 으로 다룰 것.
