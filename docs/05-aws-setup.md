# 05. AWS 계정 설정

AWS Lambda 배포를 위한 초기 계정 세팅입니다.
이 문서는 **1회만 수행**하고 이후에는 거의 볼 일이 없습니다.

## 목표

- AWS 계정 생성 및 Root MFA
- 일상 작업용 IAM 관리자 유저
- 로컬 AWS CLI
- 비용 폭탄 방지 안전망 (Budget, Cost Anomaly Detection)

## Phase 0.1: 계정 생성 + Root 보안

### 1. AWS 계정 생성

1. https://aws.amazon.com/ko → **AWS 계정 생성**
2. 이메일, 계정 이름, 비밀번호 입력
3. 연락처: **개인** 선택
4. **결제 정보**: 신용/체크카드 등록 (무료 티어도 필수, $1 임시 결제 후 환불)
5. **전화 번호 인증**: SMS 또는 음성
6. **Support Plan**: **Basic (무료)** 선택

### 2. Root 계정 MFA 활성화

⚠️ **Root 계정은 최강 권한**이므로 반드시 MFA 필수.

1. Root 로그인 (이메일 + 비밀번호)
2. 우측 상단 리전을 **아시아 태평양 (서울) ap-northeast-2**로 변경
3. 우측 상단 계정 드롭다운 → **Security credentials (보안 자격 증명)**
4. **Multi-factor authentication (MFA)** 섹션 → **Assign MFA device**
5. 설정:
   - Device name: `root-mfa`
   - Type: **Authenticator app**
6. 스마트폰에 **Google Authenticator** 설치 → QR 스캔
7. 연속된 6자리 코드 2개 입력 (30초 간격)
8. **Add MFA**

### 3. 로그아웃 → 재로그인 테스트

Authenticator 코드 요구되면 정상 동작.

## Phase 0.2: IAM 관리자 유저

이제부터 **Root는 거의 사용 안 함**. 일상 작업용 IAM 유저를 만듭니다.

### 1. IAM 유저 생성

1. IAM Console → **Users → Create user**
2. 설정:
   - 사용자 이름: `feeling-admin`
   - **AWS Management Console에 대한 사용자 액세스 제공** 체크
   - **I want to create an IAM user** 선택
   - 콘솔 비밀번호: **Custom password** → 강력한 비밀번호
   - "다음 로그인 시 비밀번호 변경" 체크 해제
3. 권한: **Attach policies directly** → `AdministratorAccess` 체크
4. 태그 스킵 → **사용자 생성**
5. **중요**: 생성 완료 화면에서:
   - 콘솔 로그인 URL 복사 (예: `https://811821010182.signin.aws.amazon.com/console`)
   - 사용자 이름, 비밀번호 저장
   - **.csv 파일 다운로드** (자격증명 백업)

### 2. IAM 유저 MFA 추가 (권장)

Root와 동일한 방식으로 `feeling-admin` 유저에도 MFA 활성화:
- IAM → Users → `feeling-admin` → **Security credentials** → **MFA device 할당**

### 3. Access Key 발급

1. `feeling-admin` → **Security credentials** → **Create access key**
2. 사용 사례: **Command Line Interface (CLI)** 선택
3. "위 권장 사항을 이해합니다" 체크
4. 설명 태그: `local-cli`
5. **Create access key**
6. **중요**: Secret access key는 **이 화면 벗어나면 다시 볼 수 없음**
   - Access key ID 복사 (`AKIA...`)
   - Secret access key 복사 또는 **.csv 다운로드**

## Phase 0.3: AWS CLI

### 1. 설치

```bash
brew install awscli
aws --version  # aws-cli/2.x.x 확인
```

### 2. 프로필 설정

```bash
aws configure --profile feeling
```

입력값:
```
AWS Access Key ID: AKIA...
AWS Secret Access Key: ...
Default region name: ap-northeast-2
Default output format: json
```

### 3. 기본 프로필로 지정

```bash
echo '' >> ~/.zshrc
echo '# AWS CLI' >> ~/.zshrc
echo 'export AWS_PROFILE=feeling' >> ~/.zshrc
source ~/.zshrc
```

### 4. 동작 확인

```bash
aws sts get-caller-identity
```

정상 응답:
```json
{
    "UserId": "AIDA...",
    "Account": "811821010182",
    "Arn": "arn:aws:iam::811821010182:user/feeling-admin"
}
```

## Phase 0.4: 비용 안전망

### 1. Zero-Spend Budget

$0.01만 과금되어도 이메일 알림:

1. AWS Console 검색: **Billing** → **청구 및 비용 관리**
2. 좌측 **Budgets** → **Create budget**
3. Budget type: **Use a template (simplified)**
4. 템플릿: **Zero-Spend Budget** 선택
5. Budget name: `My Zero-Spend Budget`
6. Email: `sedong1000@gmail.com`
7. **Create budget**

### 2. Cost Anomaly Detection

비정상적으로 증가한 사용량 감지:

1. Billing Console → **Cost Anomaly Detection**
2. **비용 모니터**: 계정 생성 시 AWS 서비스 모니터 자동 생성됨 (추가 생성 불필요)
3. **알림 구독** → **구독 생성**:
   - 이름: `email-alert`
   - 빈도: **일별 요약** (or **개별 알림**)
   - 기본 비용 영향 임계값: `$10` (이 이상의 이상 감지 시 알림)
   - 수신자: `sedong1000@gmail.com` (여러 개 가능)
4. **구독 생성**

### 3. 추가 안전 설정 (선택)

- **MFA 필수 설정**: IAM Console에서 Policy로 강제 가능
- **특정 리전만 허용**: IAM Policy로 ap-northeast-2 외 리전 차단
- **S3 Public Block**: 버킷 실수 공개 방지

## Phase 0.5: 유용한 도구

### AWS Console 사용 팁

- 즐겨찾기: 상단 **Pinned** 기능으로 자주 쓰는 서비스 고정
- 리전 고정: 계정 정보 드롭다운에서 기본 리전 설정
- 다크 모드: Unified settings에서 활성화

### 브라우저 플러그인

- **AWS Extend Switch Roles**: 여러 계정/역할 빠르게 전환 (나중에 필요)

### 명령줄 유틸

- `aws-vault`: Access key를 맥 Keychain에 보관 (보안 강화)
- `awscli2` 자동완성:
  ```bash
  echo 'complete -C aws_completer aws' >> ~/.zshrc
  ```

## 비용 확인 방법

### 주기적 확인

1. Billing Console → **Bills**: 월별 청구서
2. **Cost Explorer**: 서비스별 비용 시각화
3. **Free Tier**: 무료 티어 사용량 추적

### 무료 티어 알림

Billing Console → **Billing Preferences**:
- "무료 티어 사용량 알림 받기" 체크
- 이메일 입력

## 주의사항

### ❌ 절대 하지 말 것

- Root 계정 Access Key 발급
- Access Key를 GitHub에 커밋
- Public S3 버킷 생성
- NAT Gateway / Elastic IP를 VPC에 추가 ($32/월 함정)

### ⚠️ 조심해야 할 것

- 리전 실수: us-east-1이 아닌 **ap-northeast-2** 사용
- 서비스 enable만 해도 과금되는 것들 존재 (CloudTrail trails, Config rules 등)
- 계정 닫기 어려움 (90일 retention)

## 트러블슈팅

| 증상 | 원인 | 해결 |
|------|------|------|
| CLI `Unable to locate credentials` | 프로필 설정 안 됨 | `aws configure --profile feeling` 재실행 |
| `AccessDenied` | IAM 권한 부족 | 유저 정책 확인 |
| 콘솔 로그인 MFA 분실 | 디바이스 분실 | Root로 로그인 → 유저 MFA 삭제 → 재등록 |
| Budget 이메일 안 옴 | 스팸 폴더 | "@amazon.com" 필터 확인 |

## 다음 단계

Phase 0 완료 후 → [06. AWS Lambda 마이그레이션](06-aws-lambda-migration.md)
