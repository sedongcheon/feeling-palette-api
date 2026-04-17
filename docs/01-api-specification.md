# 01. API 명세

## 엔드포인트

### POST `/api/diary/analyze`

일기 텍스트를 받아 감정을 분석하여 반환합니다.

#### Request

```http
POST /api/diary/analyze
Content-Type: application/json

{
  "content": "오늘 하루도 힘들었어. 회사에서 야근하고 집에 오니까 너무 지쳤다."
}
```

| 필드 | 타입 | 필수 | 설명 |
|------|------|------|------|
| `content` | string | ✅ | 일기 텍스트. 1~1000자, 빈 문자열 불가. |

#### Response (200 OK)

```json
{
  "primary_emotion": "sadness",
  "emotions": {
    "joy": 5,
    "sadness": 75,
    "anger": 15,
    "anxiety": 30,
    "calm": 5,
    "excitement": 0
  },
  "comment": "힘든 하루를 보내셨군요. 오늘 하루 고생한 자신을 토닥여주세요.",
  "color": "#4A90D9"
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `primary_emotion` | string | 대표 감정 (6개 중 1개) |
| `emotions` | object | 6가지 감정 각각의 강도 (0~100) |
| `comment` | string | 따뜻한 공감 메시지 (한국어, 존댓말) |
| `color` | string | 대표 감정의 HEX 컬러코드 |

#### Response (400 Bad Request)

```json
{ "error": "일기 내용이 비어있습니다." }
```

또는

```json
{ "error": "일기 내용은 1000자 이하로 작성해주세요." }
```

#### Response (500 Internal Server Error)

```json
{ "error": "감정 분석 중 오류가 발생했습니다." }
```

## 감정 분류

6가지 감정으로 분석합니다.

| 영문 | 한글 | 컬러 |
|------|------|------|
| `joy` | 기쁨 | `#FFD700` |
| `sadness` | 슬픔 | `#4A90D9` |
| `anger` | 분노 | `#E74C3C` |
| `anxiety` | 불안 | `#9B59B6` |
| `calm` | 평온 | `#2ECC71` |
| `excitement` | 설렘 | `#FF69B4` |

### emotions 해석

- 각 감정의 강도는 0~100으로 독립적 (합이 100일 필요 없음)
- 복합 감정 표현 가능 (예: 슬픔 70 + 불안 40)
- `primary_emotion`은 전체 중 가장 두드러지는 1개

## 예시

### 긍정

```bash
curl -X POST http://localhost:8080/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"오늘 날씨가 좋아서 기분이 좋았다"}'
```

```json
{
  "primary_emotion": "joy",
  "emotions": {"joy":80, "sadness":10, "anger":0, "anxiety":0, "calm":20, "excitement":10},
  "comment": "맑은 날씨처럼 당신의 마음에도 화사한 기쁨이 가득하길 바라요.",
  "color": "#FFD700"
}
```

### 복합 감정

```bash
curl -X POST http://localhost:8080/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"회식 끝나고 집 왔는데 피곤하지만 재밌었어"}'
```

```json
{
  "primary_emotion": "calm",
  "emotions": {"joy":50, "sadness":0, "anger":0, "anxiety":5, "calm":60, "excitement":30},
  "comment": "피곤 속에 즐거움이 녹아든 하루였네요. 푹 쉬세요.",
  "color": "#2ECC71"
}
```

## 인증 / CORS

- 현재 인증 없음 (공개 API)
- CORS: 모든 Origin 허용 (`allow_origins=["*"]`) — 모바일 앱 접근 위함

## 요청 제한

- 현재 rate limiting 없음
- 남용 발생 시 API Gateway throttling 추가 예정

## 내부 동작

```
Request → FastAPI (main.py)
       → 검증 (빈 문자열, 1000자 초과)
       → analyze_diary() (service.py)
       → LangChain ChatGoogleGenerativeAI
       → gemini-2.5-flash-lite with structured output
       → Pydantic AnalyzeResponse 반환
```

상세 구현: `service.py`, `models.py` 참조.
