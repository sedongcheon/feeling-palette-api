# 08. API Gateway Throttling

API Gateway에 **요청 제한 (throttling)**을 설정해 어뷰즈를 차단하는 가이드.

## 왜 필요한가

URL이 유출되거나 악의적인 호출이 있으면:
- Lambda 호출 급증 → Gemini API 호출 급증 → **비용 폭탄**
- Throttling을 걸어두면 초당 일정 수준 이상은 거부되어 비용이 제한됨

## Token Bucket 알고리즘

API Gateway는 **토큰 버킷** 방식으로 동작한다.

```
┌─────────────────────┐
│  Bucket (최대 20)    │  ← BurstLimit
│  ● ● ● ● ● ● ● ● ● │
│  ● ● ● ● ● ● ● ● ● │
│  ● ●                │
└─────────────────────┘
     ↑ 초당 10개 보충     ← RateLimit
     
요청 1건 = 토큰 1개 소비
버킷 비면 → 429 Too Many Requests
```

- **RateLimit (10/sec)**: 초당 평균 처리 속도
- **BurstLimit (20)**: 순간 폭발 처리 한도 (여유 토큰)

## 설정값 선택 기준

이 프로젝트는 개인용 감정일기 앱이라 트래픽 적음. 다음 기준으로 값 정함:

| 시나리오 | 예상 req/sec | 현재 제한 대응 |
|---------|-------------|--------------|
| 평소 (혼자 테스트) | ~0.5 | ✅ 충분 |
| 다수 사용자 (100명 동시) | ~5 | ✅ 여유 |
| URL 유출 + 봇 | 100+ | ❌ 90% 차단 |
| DDoS | 10,000+ | ❌ 99.9% 차단 |

**결정**: Rate 10/sec, Burst 20 (SaaS 초기 단계 권장 기본값)

---

## 구현: template.yaml에 3줄 추가

```yaml
FeelingPaletteApi:
  Type: AWS::Serverless::HttpApi
  Properties:
    StageName: $default
    DefaultRouteSettings:
      ThrottlingRateLimit: 10       # 초당 평균
      ThrottlingBurstLimit: 20      # 순간 최대
```

`DefaultRouteSettings`: 모든 route에 기본 적용. 특정 route만 다르게 하고 싶으면 `RouteSettings` 블록 사용.

### 권한 추가? 불필요

기존 `github-actions-feeling-palette` IAM 역할의 `apigateway:*` 권한에 이미 포함되어 있음. 새로 추가할 게 없음.

### 배포

```bash
git add template.yaml
git commit -m "Enable API Gateway throttling"
git push origin release/release
git push github release/release
# GitHub에서 release/release → main PR 머지 → 자동 배포
```

---

## 검증

### 설정 확인

```bash
API_ID=$(aws cloudformation describe-stacks \
  --stack-name feeling-palette \
  --region ap-northeast-2 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiId`].OutputValue' \
  --output text)

aws apigatewayv2 get-stage \
  --api-id $API_ID \
  --stage-name '$default' \
  --region ap-northeast-2 \
  --query 'DefaultRouteSettings'
```

예상 출력:
```json
{
  "DetailedMetricsEnabled": false,
  "ThrottlingBurstLimit": 20,
  "ThrottlingRateLimit": 10.0
}
```

### 실제 동작 테스트

병렬 다수 요청으로 burst 초과 유도:
```bash
for i in $(seq 1 25); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://feeling-api-aws.sedoli.co.kr/api/diary/analyze \
    -H 'Content-Type: application/json' -d '{"content":"t"}' &
done
wait
```

---

## 실제 테스트 결과 (이 프로젝트 기준)

위 명령으로 25개 병렬 호출 시 **10개 200 + 15개 503** 결과. 예상과 달리 429가 아님.

### 원인 분석

신규 AWS 계정의 **Lambda 동시 실행 한도가 10**. 다음 순서로 걸림:

```
[25 동시 요청]
  ↓
[API Gateway]  ← Burst 20까지 허용
  ↓ (25개 다 통과 시도)
[Lambda]      ← 동시 실행 10이 한계
  ↓
10개 처리 (200)
15개 거부 (503)
```

**즉 Lambda 제한이 API Gateway 제한보다 먼저 걸림**.

### 확인 방법

```bash
# Lambda 동시 실행 한도 확인
aws lambda get-account-settings --region ap-northeast-2 \
  --query 'AccountLimit.ConcurrentExecutions'

# Service Quotas로 조정 가능 여부 확인
aws service-quotas get-service-quota \
  --service-code lambda \
  --quota-code L-B99A9384 \
  --region ap-northeast-2
```

### 이게 문제인가?

**아니다**. 방어 효과는 동일:
- 어뷰즈 시도 → 10 req/sec만 통과, 나머지는 403/503로 거부
- Gemini 호출 급증 방지 목적 그대로 달성
- 차이는 응답 코드 (429 vs 503)

### 개선 옵션 (필요 시)

| 옵션 | 방법 | 효과 |
|------|------|------|
| A. 현재 유지 | - | Lambda 한도가 실질 방어. 하비 프로젝트 권장 |
| B. Burst를 Lambda에 맞추기 | `ThrottlingBurstLimit: 10` | API Gateway가 먼저 429 반환. 일관된 응답 코드 |
| C. Lambda 한도 증액 | Service Quotas 요청 | 10 → 1000. 승인 1~3일. API Gateway 429 정상 작동 |

---

## 자주 묻는 질문

**Q. Rate/Burst 값을 얼마로 잡아야 하나?**
- 평소 초당 요청 수의 **10배 정도**를 Rate로 잡으면 여유 있음
- Burst는 Rate의 2~5배로 잡으면 일시적 spike 대응 가능
- 너무 낮으면 정상 사용자도 429 받을 수 있으니 주의

**Q. 사용자별로 제한 걸 수 있나?**
- HTTP API: 불가 (단순 throttling만 지원)
- REST API: Usage Plan + API Key로 가능하지만 복잡
- 이 프로젝트 규모에서는 기본 throttling으로 충분

**Q. 429 받은 클라이언트는 어떻게 처리해야 하나?**
- 기본: 잠시 후 재시도 (exponential backoff)
- `Retry-After` 헤더 참조 권장
- 앱에서는 "요청이 많아 잠시 후 다시 시도해주세요" 같은 UX 메시지

**Q. 비용은?**
- API Gateway HTTP API: 1M 요청당 $1.00 (이 프로젝트에선 12개월 무료)
- Throttling 기능 자체는 무료

---

## 참고

- AWS Docs: [Throttle API requests for better throughput](https://docs.aws.amazon.com/apigateway/latest/developerguide/api-gateway-request-throttling.html)
- SAM spec: [AWS::Serverless::HttpApi DefaultRouteSettings](https://docs.aws.amazon.com/serverless-application-model/latest/developerguide/sam-resource-httpapi.html)
- Service Quotas 증액 요청: https://console.aws.amazon.com/servicequotas
