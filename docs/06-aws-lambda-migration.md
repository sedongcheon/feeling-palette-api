# 06. AWS Lambda 마이그레이션

Synology NAS 배포 → AWS Lambda + API Gateway로 전환하는 가이드.
사전 준비: [05. AWS 계정 설정](05-aws-setup.md) 완료.

## 목표 아키텍처

```
[App]
  ↓ feeling-api.sedoli.cloud
  ↓ CNAME (Synology DNS)
  ↓ d-xxxxx.execute-api.ap-northeast-2.amazonaws.com
  ↓ API Gateway HTTP API
  ↓ AWS Lambda (container image from ECR)
  ↓ Mangum → FastAPI → LangChain → Gemini API
```

## 핵심 설계 결정

- **배포 형태**: Lambda **container image** (zip X, 250MB 제한 초과)
- **API**: **API Gateway HTTP API v2** (REST API 대비 50% 저렴)
- **Region**: **ap-northeast-2 (Seoul)**
- **IaC**: Phase 1 수동 Console, Phase 2 AWS SAM, Phase 3 GitHub Actions
- **Secret**: Phase 1 Lambda env var, Phase 2 SSM SecureString

## Phase 1: 수동 배포

### 1.1 코드 변경 (완료)

프로젝트에 이미 추가된 파일:

**`lambda_handler.py`**:
```python
from mangum import Mangum
from main import app
handler = Mangum(app, lifespan="off")
```

**`Dockerfile.lambda`**:
```dockerfile
FROM public.ecr.aws/lambda/python:3.11
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt
COPY *.py ${LAMBDA_TASK_ROOT}/
CMD ["lambda_handler.handler"]
```

**`requirements.txt`**에 `mangum>=0.17.0` 추가됨.

**`config.py`**는 `load_dotenv()`를 try/except로 감싸 Lambda에서 안전하게 동작.

### 1.2 로컬 테스트 (Lambda RIE)

```bash
# Apple Silicon이면 반드시 --platform linux/amd64
# --provenance=false 필수 (Lambda는 OCI manifest list 미지원)
docker buildx build --platform linux/amd64 --provenance=false -f Dockerfile.lambda -t feeling-palette-lambda:local .

docker run -d --name lambda-test -p 9000:8080 \
  -e GEMINI_API_KEY="$(grep GEMINI_API_KEY .env | cut -d= -f2)" \
  feeling-palette-lambda:local
```

테스트 요청 (Lambda 이벤트 v2.0 형식):
```bash
curl -s -XPOST "http://localhost:9000/2015-03-31/functions/function/invocations" \
  -d '{
    "version":"2.0",
    "routeKey":"POST /api/diary/analyze",
    "rawPath":"/api/diary/analyze",
    "requestContext":{
      "http":{"method":"POST","path":"/api/diary/analyze","sourceIp":"127.0.0.1","userAgent":"curl","protocol":"HTTP/1.1"},
      "requestId":"test","stage":"$default","time":"01/Jan/2026:00:00:00 +0000","timeEpoch":1735689600
    },
    "body":"{\"content\":\"오늘 날씨가 좋았다\"}",
    "isBase64Encoded":false,
    "headers":{"content-type":"application/json"}
  }'
```

성공 응답 (statusCode 200 + body에 감정 분석 JSON)이 나오면 다음 단계로.

정리:
```bash
docker stop lambda-test && docker rm lambda-test
```

### 1.3 ECR 생성 및 이미지 푸시

```bash
# Account ID 확인
AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
REGION=ap-northeast-2

# ECR 리포지토리 생성 (스캔 자동 활성화)
aws ecr create-repository \
  --repository-name feeling-palette \
  --region $REGION \
  --image-scanning-configuration scanOnPush=true

# Docker가 ECR에 로그인
aws ecr get-login-password --region $REGION \
  | docker login --username AWS --password-stdin $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com

# 이미지 태그 + 푸시
docker tag feeling-palette-lambda:local \
  $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/feeling-palette:latest

docker push $AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/feeling-palette:latest
```

확인:
```bash
aws ecr list-images --repository-name feeling-palette --region $REGION
```

### 1.4 Lambda 함수 생성 (Console)

1. Lambda Console: https://ap-northeast-2.console.aws.amazon.com/lambda
2. **Create function** → **Container image** 선택
3. 설정:
   - Function name: `feeling-palette-api`
   - Container image URI: **Browse images** → `feeling-palette:latest`
   - Architecture: **x86_64** (빌드 시 amd64로 했다면)
   - Permissions: **Create a new role with basic Lambda permissions**
4. **Create function**

**Configuration** 탭에서:

#### General configuration → Edit
- Memory: `512 MB`
- Timeout: `30 sec`

#### Environment variables → Edit
- Key: `GEMINI_API_KEY`
- Value: Google AI Studio에서 발급받은 키

### 1.5 Lambda 테스트

Lambda Console → **Test** 탭:
- Create new event
- Event name: `test-analyze`
- Template: **apigateway-aws-proxy** (이것으로 시작해서 JSON 교체)
- Event JSON:

```json
{
  "version": "2.0",
  "routeKey": "POST /api/diary/analyze",
  "rawPath": "/api/diary/analyze",
  "requestContext": {
    "http": {
      "method": "POST",
      "path": "/api/diary/analyze",
      "sourceIp": "127.0.0.1",
      "userAgent": "test",
      "protocol": "HTTP/1.1"
    },
    "requestId": "test",
    "stage": "$default",
    "time": "01/Jan/2026:00:00:00 +0000",
    "timeEpoch": 1735689600
  },
  "body": "{\"content\":\"오늘 날씨가 좋아서 기분이 좋았다\"}",
  "isBase64Encoded": false,
  "headers": {"content-type": "application/json"}
}
```

**Save** → **Test**:
- 첫 호출 (cold start): 5~10초
- 성공 시 statusCode 200 + body에 감정 분석 결과

### 1.6 API Gateway HTTP API

1. API Gateway Console: https://ap-northeast-2.console.aws.amazon.com/apigateway
2. **Create API** → **HTTP API** (REST API 아님)
3. **Add integration**:
   - Integration type: Lambda
   - AWS Region: ap-northeast-2
   - Lambda function: `feeling-palette-api`
4. API name: `feeling-palette-http-api`
5. **Configure routes**:
   - Method: `POST`
   - Resource path: `/api/diary/analyze`
   - Integration target: `feeling-palette-api`
6. Stage: `$default` (auto-deploy 체크)
7. **Create**

생성 후 표시되는 **Invoke URL** 복사 (예: `https://abc123.execute-api.ap-northeast-2.amazonaws.com`).

테스트:
```bash
curl -X POST https://abc123.execute-api.ap-northeast-2.amazonaws.com/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"테스트"}'
```

### 1.7 커스텀 도메인 연결

실제 사용한 도메인: **`feeling-api-aws.sedoli.co.kr`** (가비아 DNS 관리)

운영 중인 `feeling-api.sedoli.cloud` (Synology NAS 가리킴)을 유지하며 별도 테스트 도메인으로 AWS 병행 운영.

#### 1. ACM 인증서 요청

⚠️ 반드시 **ap-northeast-2 리전**에서 요청 (us-east-1 아님 — Regional API Gateway는 같은 리전 인증서 필요).

**CLI로 요청**:
```bash
aws acm request-certificate \
  --domain-name feeling-api-aws.sedoli.co.kr \
  --validation-method DNS \
  --region ap-northeast-2
```

출력된 `CertificateArn`을 변수에 저장:
```bash
CERT_ARN=arn:aws:acm:ap-northeast-2:811821010182:certificate/xxxxx
```

#### 2. DNS 검증 레코드 확인

```bash
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region ap-northeast-2 \
  --query 'Certificate.DomainValidationOptions[0].ResourceRecord'
```

출력 예:
```json
{
  "Name": "_979e7e7f126172b617144f889c5f94ec.feeling-api-aws.sedoli.co.kr.",
  "Type": "CNAME",
  "Value": "_3843a039192d94783738c92e75ba95e8.jkddzztszm.acm-validations.aws."
}
```

#### 3. 가비아 DNS에 검증 CNAME 추가

1. https://dns.gabia.com 접속 → `sedoli.co.kr` **DNS 관리** → **레코드 수정**
2. **레코드 추가**:
   - **타입**: CNAME
   - **호스트**: `_979e7e7f126172b617144f889c5f94ec.feeling-api-aws` (⚠️ `sedoli.co.kr` 제외)
   - **값/위치**: `_3843a039192d94783738c92e75ba95e8.jkddzztszm.acm-validations.aws.` (⚠️ 끝에 `.` 필수)
   - **TTL**: 600
3. **저장** → **설정 적용** (가비아는 2단계)

#### 4. ACM 발급 완료 확인

```bash
aws acm describe-certificate \
  --certificate-arn $CERT_ARN \
  --region ap-northeast-2 \
  --query 'Certificate.Status' --output text
```

`ISSUED`로 바뀌면 다음 단계 (보통 5분 이내, 늦어도 30분).

#### 5. API Gateway 커스텀 도메인 생성

```bash
aws apigatewayv2 create-domain-name \
  --domain-name feeling-api-aws.sedoli.co.kr \
  --domain-name-configurations \
    CertificateArn=$CERT_ARN,EndpointType=REGIONAL,SecurityPolicy=TLS_1_2 \
  --region ap-northeast-2
```

응답의 `ApiGatewayDomainName` 필드 (예: `d-2gc7ye9t7b.execute-api.ap-northeast-2.amazonaws.com`)를 기록.

#### 6. API 매핑 연결

API Gateway HTTP API ID (예: `prla2b674h`) 확인 후:
```bash
aws apigatewayv2 create-api-mapping \
  --domain-name feeling-api-aws.sedoli.co.kr \
  --api-id prla2b674h \
  --stage '$default' \
  --region ap-northeast-2
```

#### 7. 가비아 DNS에 서비스 CNAME 추가

- **타입**: CNAME
- **호스트**: `feeling-api-aws`
- **값**: `d-2gc7ye9t7b.execute-api.ap-northeast-2.amazonaws.com.` (⚠️ 끝 `.` 필수)
- **TTL**: 300
- **저장 + 설정 적용**

#### 8. 검증

DNS 전파 대기 (보통 1~5분):
```bash
dig +short feeling-api-aws.sedoli.co.kr CNAME
# → d-2gc7ye9t7b.execute-api.ap-northeast-2.amazonaws.com.
```

API 호출:
```bash
curl -X POST https://feeling-api-aws.sedoli.co.kr/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"오늘 날씨가 좋아서 기분이 좋았다"}'
```

정상 응답 나오면 **Phase 1 완료!** 🎉

#### 참고: Console UI로 같은 작업

CLI 대신 Console을 쓰려면:
- ACM: https://ap-northeast-2.console.aws.amazon.com/acm
- API Gateway: Custom domain names → Create

화면에 생성되는 CNAME을 그대로 가비아에 추가하면 됨.

#### 나중에 운영 도메인 전환 (선택)

완전 이전 결정 시 `feeling-api.sedoli.cloud` → AWS로 변경:
1. Synology DNS에서 `feeling-api` A 레코드 (NAS IP) 삭제
2. CNAME 추가: `feeling-api` → `d-2gc7ye9t7b.execute-api.ap-northeast-2.amazonaws.com.`
3. ACM에 `feeling-api.sedoli.cloud` 추가 인증서 요청 (또는 SAN 추가)
4. API Gateway 커스텀 도메인 추가 + 매핑
5. 앱 클라이언트는 변경 불필요 (URL 동일)

⚠️ 컷오버 전날 TTL을 300초로 낮춰두면 롤백 빠름.

## Phase 2: AWS SAM IaC (완료)

Console 클릭으로 만든 리소스를 `template.yaml`로 코드화 완료. 실제 진행 절차는 아래.

### 2.1 SAM CLI 설치
```bash
brew install aws-sam-cli
sam --version   # 1.158.0+
```

### 2.2 SSM SecureString 저장
```bash
aws ssm put-parameter \
  --name /feeling-palette/gemini-api-key \
  --value "AQ.Ab8RN6..." \
  --type SecureString \
  --region ap-northeast-2
```

### 2.3 template.yaml (프로젝트 루트)

`template.yaml` 파일 참조. 핵심:
- `AWS::Serverless::Function` (container image)
- `AWS::Serverless::HttpApi`
- `AWS::Logs::LogGroup` (retention 7일)
- `GeminiApiKey`를 NoEcho CloudFormation Parameter로 받음

### 2.4 CloudFormation 제약 주의

**Lambda 환경변수에서 `{{resolve:ssm-secure:...}}` dynamic reference 사용 불가.**
해결: 배포 명령어에서 SSM값을 직접 가져와 `--parameter-overrides`로 전달.

### 2.5 기존 Console 리소스 teardown

SAM이 동일 이름 리소스를 생성하므로 먼저 제거:
```bash
# API mapping 제거 (커스텀 도메인은 유지)
aws apigatewayv2 delete-api-mapping \
  --domain-name feeling-api-aws.sedoli.co.kr \
  --api-mapping-id <mapping-id> \
  --region ap-northeast-2

# HTTP API + Lambda + Log group 삭제
aws apigatewayv2 delete-api --api-id <old-api-id> --region ap-northeast-2
aws lambda delete-function --function-name feeling-palette-api --region ap-northeast-2
aws logs delete-log-group --log-group-name /aws/lambda/feeling-palette-api --region ap-northeast-2
```

### 2.6 배포

```bash
IMAGE_URI=811821010182.dkr.ecr.ap-northeast-2.amazonaws.com/feeling-palette:latest
GEMINI_KEY=$(aws ssm get-parameter \
  --name /feeling-palette/gemini-api-key \
  --with-decryption \
  --region ap-northeast-2 \
  --query 'Parameter.Value' --output text)

sam deploy \
  --template-file template.yaml \
  --stack-name feeling-palette \
  --region ap-northeast-2 \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides ImageUri=$IMAGE_URI GeminiApiKey=$GEMINI_KEY \
  --resolve-s3 \
  --resolve-image-repos \
  --no-confirm-changeset \
  --no-fail-on-empty-changeset
```

배포 후 Outputs에서 새 HTTP API ID 확인.

### 2.7 커스텀 도메인 재매핑

SAM이 새 HTTP API를 생성하므로 커스텀 도메인에 다시 연결:
```bash
aws apigatewayv2 create-api-mapping \
  --domain-name feeling-api-aws.sedoli.co.kr \
  --api-id <new-api-id> \
  --stage '$default' \
  --region ap-northeast-2
```

전파 1~5분 후 `https://feeling-api-aws.sedoli.co.kr/api/diary/analyze` 정상 동작.

### 이후 배포

이미지만 새로 빌드/푸시한 뒤 동일한 `sam deploy` 재실행하면 됨. Infrastructure 변경 없이 코드만 바뀌면 Lambda만 업데이트됨.

## Phase 3: GitHub Actions CI/CD (완료)

`main` 브랜치에 push되면 자동으로 ECR 빌드/푸시 + SAM 배포 + smoke test 실행.
AWS Access Key를 GitHub Secrets에 저장하지 않고 **OIDC federation**으로 안전하게 인증.

### 3.1 GitHub OIDC Identity Provider (AWS)

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

### 3.2 IAM Role (GitHub Actions 전용)

Trust policy는 특정 GitHub 레포에만 AssumeRole 허용:
```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {
      "Federated": "arn:aws:iam::811821010182:oidc-provider/token.actions.githubusercontent.com"
    },
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
      "StringLike": {"token.actions.githubusercontent.com:sub": "repo:sedongcheon/feeling-palette-api:*"}
    }
  }]
}
```

실제 부여한 권한 (최소권한 기준):
- ECR push/pull: `feeling-palette*` 레포
- CloudFormation: SAM 배포용 (`GetTemplateSummary` 포함)
- Lambda 관리: `feeling-palette*` 함수
- API Gateway: 전체
- IAM: Lambda 실행 role 관리 (`feeling-palette-*`)
- CloudWatch Logs: Lambda 로그 그룹
- SSM: `/feeling-palette/*` 읽기 + KMS Decrypt (SecureString용)
- S3: SAM 관리 버킷

역할 생성:
```bash
aws iam create-role \
  --role-name github-actions-feeling-palette \
  --assume-role-policy-document file://trust-policy.json

aws iam put-role-policy \
  --role-name github-actions-feeling-palette \
  --policy-name deploy-policy \
  --policy-document file://deploy-policy.json
```

### 3.3 Workflow 파일 (`.github/workflows/deploy.yml`)

핵심 동작:
1. `actions/checkout@v4` + OIDC 인증 (`configure-aws-credentials@v4`)
2. ECR 로그인 → Docker buildx로 `linux/amd64` + `--provenance=false` 빌드 → `:sha`와 `:latest` 둘 다 push
3. SSM에서 Gemini API key 복호화 읽기 (`::add-mask::`로 로그 마스킹)
4. `sam deploy` (with `--image-repository` 필수)
5. Smoke test: `feeling-api-aws.sedoli.co.kr` curl 5회 재시도

`main` push + `workflow_dispatch` (수동 실행) 둘 다 트리거.

### 3.4 삽질 포인트

1. **GitHub PAT에 `workflow` 권한 필요**: classic 토큰의 `repo`만으로는 workflow 파일 push 거부
2. **`sam deploy` with Image package**: `--image-repository` 옵션 필수 (아니면 "Missing option" 에러)
3. **IAM 권한은 에러 나오는 대로 추가**: `GetTemplateSummary` 같은 건 사전에 예측 어려움

### 3.5 이후 배포 흐름

```
로컬: git commit + git push origin release/release (GitLab) + git push github release/release
   ↓
GitHub UI: release/release → main PR 생성 + 머지
   ↓
GitHub Actions 자동 실행 (~4분)
   ↓
Lambda 업데이트 + smoke test 통과 → 배포 완료
```

Jenkins는 NAS 운영이 필요 없어지면 은퇴 가능.

## 비용 예상

**월 1,000건 기준 (Year 1)**:

| 항목 | 비용 |
|------|------|
| Lambda compute (512MB × 2s × 1000) | $0 (무료 400K GB-s) |
| Lambda requests (1,000) | $0 (무료 1M) |
| API Gateway HTTP API | $0 (12개월 무료 1M) |
| ECR storage (500MB+) | ~$0.05 |
| CloudWatch Logs | $0 (5GB 무료) |
| SSM SecureString | $0 |
| ACM cert | $0 |
| **합계** | **~$0.05/월** |

Year 2 이후: 약 $0.15~0.20/월.

## 주의사항

1. **Apple Silicon 빌드**: `--platform linux/amd64` 필수
2. **Cold start**: 첫 요청 2~4초. 메모리 1024MB로 올리면 절반 단축
3. **컨테이너만 사용**: zip 250MB 제한 초과
4. **ACM 리전**: HTTP API Regional → 같은 리전 (ap-northeast-2)
5. **NAT Gateway / VPC 금지**: 월 $32 함정
6. **이미지 태그**: `latest` 대신 `github.sha` 사용 (롤백 가능)
7. **DNS TTL 미리 낮추기**: 컷오버 전날 300초로

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| `exec format error` | 아키텍처 불일치 | `--platform linux/amd64` 필수 |
| `image manifest ... is not supported` | buildx OCI manifest list | `--provenance=false` 추가 |
| `KeyError: 'sourceIp'` | Lambda 이벤트 형식 오류 | requestContext.http.sourceIp 포함 |
| Cold start 오래 걸림 | 메모리 부족 | 512 → 1024 MB |
| 403 from Gemini | API key 문제 | Lambda env var 재확인, Google Cloud에서 Gemini API enable |
| 커스텀 도메인 504 | API mapping 없음 | Custom domain → API mappings 확인 |
| ACM cert validation 안 됨 | DNS CNAME 오타 | Synology DNS에 공백/오타 없이 정확히 |

## 롤백 방법

### Lambda 이전 버전으로 되돌리기
```bash
# 버전 목록
aws lambda list-versions-by-function --function-name feeling-palette-api

# 특정 이미지로 업데이트
aws lambda update-function-code \
  --function-name feeling-palette-api \
  --image-uri $ACCOUNT.dkr.ecr.ap-northeast-2.amazonaws.com/feeling-palette:<이전태그>
```

### NAS로 긴급 롤백
Synology DNS에서 `feeling-api` CNAME → 기존 A 레코드로 복구.
TTL 300이면 5분 내 복구.

## 진행 상황

- [x] Phase 0: AWS 계정 + IAM + CLI + Budget
- [x] Phase 1.1: 코드 변경 (lambda_handler, Dockerfile.lambda, mangum)
- [x] Phase 1.2: 로컬 RIE 테스트
- [x] Phase 1.3: ECR push
- [x] Phase 1.4: Lambda 함수 생성
- [x] Phase 1.5: 테스트 성공
- [x] Phase 1.6: API Gateway HTTP API (`prla2b674h.execute-api.ap-northeast-2.amazonaws.com`)
- [x] Phase 1.7: 커스텀 도메인 연결 (`feeling-api-aws.sedoli.co.kr` — 병행 운영)
- [x] Phase 2: SAM IaC (`template.yaml` 작성 및 `sam deploy` 완료)
- [x] Phase 3: GitHub Actions CI/CD (OIDC + 자동 배포)

## 현재 엔드포인트

| 환경 | URL | 비고 |
|------|-----|------|
| NAS (기존) | https://feeling-api.sedoli.cloud | 운영 중 |
| AWS Lambda (신규) | https://feeling-api-aws.sedoli.co.kr | 검증용, 병행 |

## 참고 링크

- [AWS Lambda Container Image](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Mangum (FastAPI on Lambda)](https://mangum.io/)
- [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/)
- [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
