# 07. CloudWatch 알람 추가

Lambda 함수에 문제가 생기면 **이메일로 자동 알림**을 받도록 설정하는 가이드.

## 전체 구조

```
Lambda 실행
    ↓ 자동 지표 수집
CloudWatch Metrics
    ↓ 알람 조건 감시
CloudWatch Alarm
    ↓ 조건 만족 시 발동
SNS Topic
    ↓ 구독자에게 전달
Email (또는 SMS, Slack, Lambda 등)
```

## 이 프로젝트의 설계 원칙

**모든 AWS 리소스는 `template.yaml`로 관리**한다.
- CLI로 직접 만들면 "그림자 리소스" 발생 → SAM 재배포 시 충돌/삭제
- Git에 추적 가능 → 언제/왜 추가했는지 기록
- 다른 환경에 복제 가능 → 재사용성

이 원칙 때문에 CloudWatch 알람도 **template.yaml 수정 → sam deploy** 흐름으로 추가한다.

## 작업 순서

```
1. template.yaml 수정 (SNS + CloudWatch::Alarm 리소스 추가)
         ↓
2. IAM 정책 업데이트 (GitHub Actions role에 sns:*, cloudwatch:* 권한)
         ↓
3. git push → PR 머지 → GitHub Actions 자동 배포
         ↓
4. 첫 배포 시 SNS가 이메일로 구독 확인 메일 발송 → 사용자 수동 클릭
         ↓
5. 완료. 알람 발동 시 이메일 수신.
```

---

## Step 1: template.yaml 수정

### 1-1. Parameter 추가
```yaml
Parameters:
  AlertEmail:
    Type: String
    Default: sedong1000@gmail.com
    Description: Email to receive CloudWatch alarm notifications
```

**왜 파라미터로?** 이메일을 바꾸고 싶을 때 template 수정 없이 `--parameter-overrides AlertEmail=...`로 변경 가능.

### 1-2. SNS Topic 리소스

```yaml
Resources:
  AlertTopic:
    Type: AWS::SNS::Topic
    Properties:
      TopicName: feeling-palette-alerts
      Subscription:
        - Protocol: email
          Endpoint: !Ref AlertEmail
```

**SNS (Simple Notification Service)** = 알림 메시지 라우터.
- **Topic**: 메시지를 받는 채널 (이름 + ARN)
- **Subscription**: 이 Topic의 메시지를 받을 구독자
- Protocol은 `email`, `sms`, `https`, `sqs`, `lambda` 등 가능

### 1-3. CloudWatch Alarm 리소스

#### (A) 단순 알람 (단일 지표)
```yaml
DurationAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: feeling-palette-duration
    AlarmDescription: Lambda duration above 25 seconds
    ActionsEnabled: true
    AlarmActions:
      - !Ref AlertTopic      # 알람 발동 시 SNS로 전송
    MetricName: Duration
    Namespace: AWS/Lambda
    Dimensions:
      - Name: FunctionName
        Value: !Ref FeelingPaletteFunction
    Statistic: Maximum
    Period: 300              # 5분 단위 집계
    EvaluationPeriods: 1     # 1개 period가 조건 맞으면
    DatapointsToAlarm: 1     # 그 중 1개라도 조건이면 알람
    Threshold: 25000         # 25초 (밀리초)
    ComparisonOperator: GreaterThanThreshold
    TreatMissingData: notBreaching  # 호출 없을 때 = 정상으로 간주
```

**자주 쓰는 필드**:
- `Statistic`: `Sum`, `Average`, `Maximum`, `Minimum`, `p95`, `p99`
- `Period`: 60, 300, 3600 (초 단위)
- `ComparisonOperator`: `GreaterThanThreshold`, `LessThanThreshold`, `GreaterThanOrEqualToThreshold`
- `TreatMissingData`: `breaching` (데이터 없으면 알람), `notBreaching` (정상 간주), `ignore` (무시)

#### (B) 계산식 알람 (여러 지표 조합)

에러율 = 에러 수 ÷ 호출 수 같은 건 단일 지표로 안 됨. `Metrics` 블록 사용.

```yaml
ErrorRateAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: feeling-palette-error-rate
    AlarmActions:
      - !Ref AlertTopic
    OKActions:              # 알람 해제 시에도 알림 (복구 확인용)
      - !Ref AlertTopic
    Metrics:
      - Id: errorRate
        Expression: IF(invocations > 0, 100 * errors / invocations, 0)
        Label: ErrorRate
        ReturnData: true    # 이 지표로 임계값 비교
      - Id: errors
        MetricStat:
          Metric:
            Namespace: AWS/Lambda
            MetricName: Errors
            Dimensions:
              - Name: FunctionName
                Value: !Ref FeelingPaletteFunction
          Period: 300
          Stat: Sum
        ReturnData: false   # 계산에만 사용
      - Id: invocations
        MetricStat:
          Metric:
            Namespace: AWS/Lambda
            MetricName: Invocations
            Dimensions:
              - Name: FunctionName
                Value: !Ref FeelingPaletteFunction
          Period: 300
          Stat: Sum
        ReturnData: false
    EvaluationPeriods: 1
    DatapointsToAlarm: 1
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
    TreatMissingData: notBreaching
```

**핵심**: `Expression`에서 수식, 각 `Id`로 참조. `IF(invocations > 0, ..., 0)`로 0 나누기 방지.

### 1-4. Outputs에 SNS ARN 노출 (선택)

```yaml
Outputs:
  AlertTopicArn:
    Description: SNS topic ARN for alarm notifications
    Value: !Ref AlertTopic
```

→ 배포 후 CLI/Console에서 ARN 확인 가능.

---

## Step 2: IAM 권한 추가

GitHub Actions가 SAM으로 SNS + CloudWatch 리소스를 만들려면 해당 권한이 있어야 한다.

### 2-1. 정책 파일 수정

`/tmp/github-actions-deploy-policy.json`에 아래 Statement 추가:

```json
{
  "Sid": "SNSManage",
  "Effect": "Allow",
  "Action": [
    "sns:CreateTopic",
    "sns:DeleteTopic",
    "sns:GetTopicAttributes",
    "sns:SetTopicAttributes",
    "sns:Subscribe",
    "sns:Unsubscribe",
    "sns:ListSubscriptionsByTopic",
    "sns:ListTagsForResource",
    "sns:TagResource",
    "sns:UntagResource"
  ],
  "Resource": "arn:aws:sns:ap-northeast-2:811821010182:feeling-palette-*"
},
{
  "Sid": "CloudWatchAlarmManage",
  "Effect": "Allow",
  "Action": [
    "cloudwatch:PutMetricAlarm",
    "cloudwatch:DeleteAlarms",
    "cloudwatch:DescribeAlarms",
    "cloudwatch:ListTagsForResource",
    "cloudwatch:TagResource",
    "cloudwatch:UntagResource"
  ],
  "Resource": "arn:aws:cloudwatch:ap-northeast-2:811821010182:alarm:feeling-palette-*"
}
```

**`Resource` 스코프**: 리소스 이름을 `feeling-palette-*` 로 제한 → 최소 권한 원칙.

### 2-2. AWS에 적용

```bash
aws iam put-role-policy \
  --role-name github-actions-feeling-palette \
  --policy-name deploy-policy \
  --policy-document file:///tmp/github-actions-deploy-policy.json
```

**이 명령어의 동작**:
- 역할 `github-actions-feeling-palette`의 인라인 정책 `deploy-policy`를 업데이트
- 정책 내용은 로컬 JSON 파일을 그대로 읽음
- 이미 존재하면 덮어쓰기, 없으면 새로 만듦

---

## Step 3: Git 커밋 + 푸시

```bash
git add template.yaml
git commit -m "Add CloudWatch alarms for Lambda errors and duration"
git push origin release/release
git push github release/release
```

이후 GitHub에서 `release/release` → `main` PR 머지 → GitHub Actions 자동 배포.

---

## Step 4: 이메일 구독 확인

**첫 배포 시점**에 AWS SNS가 `AlertEmail`로 **구독 확인 이메일** 발송.

- **From**: `AWS Notifications <no-reply@sns.amazonaws.com>`
- **Subject**: `AWS Notification - Subscription Confirmation`
- **본문**: "Confirm subscription" 링크

**반드시 클릭**해야 구독이 활성화됨. 미확인 시 알람 트리거되어도 아무 메일 안 옴.

확인 후 상태 검증:
```bash
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:ap-northeast-2:811821010182:feeling-palette-alerts \
  --region ap-northeast-2
```

`SubscriptionArn`이 `PendingConfirmation`이 아닌 실제 ARN으로 표시되면 OK.

---

## Step 5: 테스트 (알람 강제 발동)

실제 알람이 오는지 확인하려면 임시로 임계값을 낮춰 발동시켜 본다.

### 방법 A: 임계값 임시 조정
1. `template.yaml`의 `Threshold: 5` → `Threshold: 0` 으로 변경 후 배포
2. 일반 API 호출 몇 번 → 에러 없어도 `0%가 > 0`이 아니므로 안 터짐 ...
   → 이 방법은 안 먹힘. 실제 에러를 일으켜야 함.

### 방법 B: 실제 에러 유도
```bash
# 잘못된 payload로 400 에러 유발 (5% 초과할 정도로 많이)
for i in $(seq 1 30); do
  curl -X POST https://feeling-api-aws.sedoli.co.kr/api/diary/analyze \
    -H 'Content-Type: application/json' \
    -d '{}'
done
```

(주의: 400은 `Errors` 지표로 안 잡힘. Lambda 런타임 에러만 잡힘.)

### 방법 C: CLI로 알람 상태 강제 세팅 (가장 확실) ✅ 실제 테스트 검증됨

```bash
# 1) 알람 발동
aws cloudwatch set-alarm-state \
  --alarm-name feeling-palette-error-rate \
  --state-value ALARM \
  --state-reason "Manual test — verifying email delivery" \
  --region ap-northeast-2
```

수 초 내 이메일 도착. 실제로 수신된 이메일 본문 예시:

```
You are receiving this email because your Amazon CloudWatch Alarm
"feeling-palette-error-rate" in the Asia Pacific (Seoul) region has
entered the ALARM state, because "Manual test — verifying email delivery"
at "Saturday 18 April, 2026 01:32:20 UTC".

Alarm Details:
- Name:        feeling-palette-error-rate
- Description: Lambda error rate above 5% over 5 minutes
- State Change: OK -> ALARM
- Reason for State Change: Manual test — verifying email delivery
- Timestamp:   Saturday 18 April, 2026 01:32:20 UTC
- AWS Account: 811821010182

Monitored Metrics:
- MetricExpression: IF(invocations > 0, 100 * errors / invocations, 0)
- MetricLabel:      ErrorRate

State Change Actions:
- OK:    [arn:aws:sns:ap-northeast-2:811821010182:feeling-palette-alerts]
- ALARM: [arn:aws:sns:ap-northeast-2:811821010182:feeling-palette-alerts]
```

이메일 제목: **"ALARM: feeling-palette-error-rate in Asia Pacific (Seoul)"**

확인 후 원상 복구:
```bash
# 2) 정상 상태로 복구 (OK 알림 이메일도 한 번 더 옴 — OKActions 설정 덕)
aws cloudwatch set-alarm-state \
  --alarm-name feeling-palette-error-rate \
  --state-value OK \
  --state-reason "Test complete — manual reset" \
  --region ap-northeast-2
```

복구 시 이메일 제목: **"OK: feeling-palette-error-rate in Asia Pacific (Seoul)"**

### 테스트 시 주의사항

- **강제 세팅한 상태는 일시적**: 다음 지표 수집 주기(5분)가 되면 실제 데이터에 따라 재평가됨. 수동으로 OK 복구하지 않아도 자연스럽게 정상화됨.
- **이메일 지연**: 평소 즉시 오지만 가끔 1~2분 지연 가능. 5분 지나도 안 오면 SNS 구독 상태 재확인.
- **OK 알림도 받고 싶지 않으면**: template.yaml의 `OKActions` 라인 제거 후 재배포.
- **비용 걱정 없음**: 이 테스트로 발생하는 SNS 이메일 2건(ALARM + OK)은 월 1,000건 무료 티어 안.

---

## 상태 확인 명령어 치트시트

```bash
# 알람 목록
aws cloudwatch describe-alarms \
  --alarm-name-prefix feeling-palette \
  --region ap-northeast-2 \
  --query 'MetricAlarms[].[AlarmName,StateValue,StateReason]' \
  --output table

# SNS Topic 목록
aws sns list-topics --region ap-northeast-2 | grep feeling-palette

# SNS 구독 상태
aws sns list-subscriptions-by-topic \
  --topic-arn arn:aws:sns:ap-northeast-2:811821010182:feeling-palette-alerts \
  --region ap-northeast-2

# Lambda 지표 직접 조회 (최근 1시간)
aws cloudwatch get-metric-statistics \
  --namespace AWS/Lambda \
  --metric-name Errors \
  --dimensions Name=FunctionName,Value=feeling-palette-api \
  --start-time $(date -u -v -1H +%Y-%m-%dT%H:%M:%S) \
  --end-time $(date -u +%Y-%m-%dT%H:%M:%S) \
  --period 300 \
  --statistics Sum \
  --region ap-northeast-2
```

---

## 자주 추가하는 알람 레시피

### Lambda Throttles (동시 실행 한도 초과)
```yaml
ThrottleAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: feeling-palette-throttles
    AlarmActions: [!Ref AlertTopic]
    MetricName: Throttles
    Namespace: AWS/Lambda
    Dimensions: [{Name: FunctionName, Value: !Ref FeelingPaletteFunction}]
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 1
    ComparisonOperator: GreaterThanOrEqualToThreshold
    TreatMissingData: notBreaching
```

### API Gateway 4XX/5XX
```yaml
Api5xxAlarm:
  Type: AWS::CloudWatch::Alarm
  Properties:
    AlarmName: feeling-palette-api-5xx
    AlarmActions: [!Ref AlertTopic]
    MetricName: 5XXError
    Namespace: AWS/ApiGateway
    Dimensions: [{Name: ApiId, Value: !Ref FeelingPaletteApi}]
    Statistic: Sum
    Period: 300
    EvaluationPeriods: 1
    Threshold: 5
    ComparisonOperator: GreaterThanThreshold
```

### 비용 알람 (Billing)
별도 리전 필요 (us-east-1). 이 프로젝트에는 Budgets + Cost Anomaly Detection으로 이미 커버됨.

---

## 비용

- **CloudWatch Alarms**: 알람 10개까지 무료. 이후 $0.10/알람/월
- **SNS**: 이메일 1,000건까지 무료. 이후 $2/100,000건
- **현재 사용**: 알람 2개, 이메일 가끔 → **모두 무료 범위**

---

## 참고

- AWS Docs: [CloudWatch 알람 만들기](https://docs.aws.amazon.com/ko_kr/AmazonCloudWatch/latest/monitoring/AlarmThatSendsEmail.html)
- Lambda 지표 목록: [Working with Lambda metrics](https://docs.aws.amazon.com/lambda/latest/dg/monitoring-metrics.html)
- SAM 리소스 스펙: [AWS::CloudWatch::Alarm](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/aws-resource-cloudwatch-alarm.html)
