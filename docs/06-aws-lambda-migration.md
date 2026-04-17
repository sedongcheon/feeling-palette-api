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
docker buildx build --platform linux/amd64 -f Dockerfile.lambda -t feeling-palette-lambda:local .

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

### 1.7 커스텀 도메인 (feeling-api.sedoli.cloud)

#### 1. ACM 인증서 요청

⚠️ **ap-northeast-2 리전**에서 요청 (us-east-1 아님).

1. ACM Console: https://ap-northeast-2.console.aws.amazon.com/acm
2. **Request certificate** → **Public certificate** → Next
3. Fully qualified domain name: `feeling-api.sedoli.cloud`
4. Validation method: **DNS validation**
5. **Request**

생성된 인증서 클릭 → **Domains** 섹션에 CNAME 검증 레코드 표시:
- Name: `_abc123.feeling-api.sedoli.cloud`
- Value: `_xyz456.acm-validations.aws`

이 CNAME을 **Synology DNS Server**에 추가:
1. DSM → DNS Server → 영역 편집 → `sedoli.cloud`
2. 리소스 레코드 추가:
   - 이름: `_abc123.feeling-api`
   - 유형: CNAME
   - 값: `_xyz456.acm-validations.aws.`

5~30분 대기 → ACM 상태가 **Issued**로 변경.

#### 2. API Gateway 커스텀 도메인 연결

1. API Gateway → **Custom domain names** → **Create**
2. 설정:
   - Domain name: `feeling-api.sedoli.cloud`
   - Minimum TLS version: `TLS 1.2`
   - Endpoint type: **Regional**
   - ACM certificate: 위에서 Issued된 인증서 선택
3. **Create domain name**
4. 생성 후 표시되는 **API Gateway domain name** 복사 (예: `d-abcxyz.execute-api.ap-northeast-2.amazonaws.com`)

5. 같은 페이지 **API mappings** 탭 → **Configure API mappings**:
   - API: `feeling-palette-http-api`
   - Stage: `$default`
   - Path: (비워둠)
6. Save

#### 3. Synology DNS CNAME 추가

1. DSM → DNS Server → 영역 편집 → `sedoli.cloud`
2. 기존 `feeling-api` A 레코드 (NAS IP 가리킴) → **삭제**
3. 새 레코드 추가:
   - 이름: `feeling-api`
   - 유형: CNAME
   - 값: `d-abcxyz.execute-api.ap-northeast-2.amazonaws.com.`
   - TTL: 300

⚠️ **컷오버 전날** TTL을 300초로 낮춰두면 롤백 시 빠르게 복구 가능.

#### 4. 검증

```bash
# DNS 전파 확인 (5분 정도 기다림)
dig feeling-api.sedoli.cloud

# API 동작 확인
curl -X POST https://feeling-api.sedoli.cloud/api/diary/analyze \
  -H 'Content-Type: application/json' \
  -d '{"content":"테스트"}'
```

정상 응답 나오면 **Phase 1 완료!** 🎉

## Phase 2: AWS SAM IaC (예정)

Console 클릭으로 만든 리소스를 `template.yaml`로 코드화.

### 설치
```bash
brew install aws-sam-cli
sam --version
```

### `template.yaml` (프로젝트 루트)
```yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Parameters:
  GeminiApiKeyParam:
    Type: AWS::SSM::Parameter::Value<String>
    Default: /feeling-palette/gemini-api-key
    NoEcho: true

Resources:
  FeelingPaletteFunction:
    Type: AWS::Serverless::Function
    Properties:
      FunctionName: feeling-palette-api
      PackageType: Image
      ImageUri: !Sub '${AWS::AccountId}.dkr.ecr.${AWS::Region}.amazonaws.com/feeling-palette:latest'
      Architectures: [x86_64]
      MemorySize: 512
      Timeout: 30
      Environment:
        Variables:
          GEMINI_API_KEY: !Ref GeminiApiKeyParam
      Events:
        Analyze:
          Type: HttpApi
          Properties:
            ApiId: !Ref FeelingPaletteApi
            Path: /api/diary/analyze
            Method: POST

  FeelingPaletteApi:
    Type: AWS::Serverless::HttpApi
    Properties:
      StageName: $default

Outputs:
  ApiEndpoint:
    Value: !GetAtt FeelingPaletteApi.ApiEndpoint
```

### SSM에 키 이전
```bash
aws ssm put-parameter \
  --name /feeling-palette/gemini-api-key \
  --value "AIzaSy..." \
  --type SecureString \
  --region ap-northeast-2
```

### 배포
```bash
sam deploy --template-file template.yaml \
  --stack-name feeling-palette \
  --capabilities CAPABILITY_IAM \
  --region ap-northeast-2
```

Phase 1 수동 리소스는 teardown 후 SAM이 재생성. 커스텀 도메인 매핑만 Console에서 재연결.

## Phase 3: GitHub Actions CI/CD (예정)

Jenkins 은퇴. `main` 브랜치 push → 자동 ECR push + Lambda 업데이트.

### OIDC 신뢰 설정
1. IAM → Identity providers → Add:
   - URL: `https://token.actions.githubusercontent.com`
   - Audience: `sts.amazonaws.com`
2. Role `github-actions-feeling-palette` 생성 (trust policy를 GH 레포로 스코프)

### `.github/workflows/deploy.yml`
```yaml
name: Deploy to Lambda
on:
  push:
    branches: [main]
permissions:
  id-token: write
  contents: read
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::ACCOUNT_ID:role/github-actions-feeling-palette
          aws-region: ap-northeast-2
      - uses: aws-actions/amazon-ecr-login@v2
        id: ecr
      - name: Build and push
        run: |
          IMAGE=${{ steps.ecr.outputs.registry }}/feeling-palette:${{ github.sha }}
          docker build --platform linux/amd64 -f Dockerfile.lambda -t $IMAGE .
          docker push $IMAGE
      - uses: aws-actions/setup-sam@v2
      - name: SAM deploy
        run: sam deploy --stack-name feeling-palette --no-confirm-changeset --no-fail-on-empty-changeset
      - name: Smoke test
        run: |
          curl -fsS -XPOST https://feeling-api.sedoli.cloud/api/diary/analyze \
            -H 'content-type: application/json' \
            -d '{"content":"배포 확인"}'
```

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
- [ ] Phase 1.4: Lambda 함수 생성 (진행 중)
- [ ] Phase 1.5: 테스트
- [ ] Phase 1.6: API Gateway HTTP API
- [ ] Phase 1.7: 커스텀 도메인 연결
- [ ] Phase 2: SAM IaC
- [ ] Phase 3: GitHub Actions CI/CD

## 참고 링크

- [AWS Lambda Container Image](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Mangum (FastAPI on Lambda)](https://mangum.io/)
- [AWS SAM](https://docs.aws.amazon.com/serverless-application-model/)
- [GitHub Actions OIDC with AWS](https://docs.github.com/en/actions/deployment/security-hardening-your-deployments/configuring-openid-connect-in-amazon-web-services)
