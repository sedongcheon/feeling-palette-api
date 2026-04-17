# 04. NAS 배포 (현재 운영 환경)

Synology NAS에서 Docker + Jenkins + GitLab으로 자동 배포하는 CI/CD 구성입니다.

## 환경

| 항목 | 값 |
|------|------|
| 플랫폼 | Synology NAS |
| GitLab | https://git.sedoli.cloud/sdchun/feeling-palette-api |
| Jenkins | NAS 내부 설치 |
| API 도메인 | https://feeling-api.sedoli.cloud |
| 내부 포트 | 8100 (호스트) → 8080 (컨테이너) |

## 아키텍처

```
[React Native 앱]
    ↓ POST /api/diary/analyze
[feeling-api.sedoli.cloud] (HTTPS, 443)
    ↓ Synology 역방향 프록시 (Let's Encrypt)
[localhost:8100] (NAS 로컬)
    ↓ Docker 포트 매핑
[feeling-palette-api container] (8080 내부)
    ↓ uvicorn
[FastAPI + LangChain]
    ↓ ChatGoogleGenerativeAI
[Gemini API]
```

## CI/CD 흐름

```
1. 개발자: git push → release/release 브랜치
2. 개발자: GitLab UI에서 main으로 Merge Request 생성 및 머지
3. GitLab: main push 이벤트 → Jenkins webhook 호출
4. Jenkins: 파이프라인 자동 실행
   ├─ Checkout (main 브랜치)
   ├─ Build (docker build)
   ├─ Deploy (기존 컨테이너 stop/rm → 새 컨테이너 run)
   ├─ Health Check (docker exec로 /docs 확인)
   └─ Cleanup (미사용 이미지 정리)
5. Synology 역방향 프록시: localhost:8100 → feeling-api.sedoli.cloud
```

## 초기 설정 (1회)

### 1. GitLab 프로젝트 생성

https://git.sedoli.cloud 접속 → New Project → `feeling-palette-api`

### 2. Jenkins Credential 등록

**Manage Jenkins → Credentials → (global) → Add Credentials**

#### GitLab Access Token
- GitLab → 프로필 → Edit Profile → Access Tokens → scope `read_repository`
- Jenkins:
  - Kind: Username with password
  - Username: `sdchun`
  - Password: GitLab에서 발급받은 토큰
  - ID: `gitlab-credentials`

#### Gemini API Key
- Kind: Secret text
- Secret: `AIzaSy...` (Google AI Studio에서 발급)
- ID: `gemini-api-key`

### 3. Jenkins Pipeline 생성

1. **새로운 Item** → `feeling-palette-api` → **Pipeline**
2. **Build Triggers**: **Build when a change is pushed to GitLab** 체크 → 표시된 webhook URL 복사
3. **Pipeline**:
   - Definition: **Pipeline script from SCM**
   - SCM: **Git**
   - Repository URL: `https://git.sedoli.cloud/sdchun/feeling-palette-api.git`
   - Credentials: `gitlab-credentials`
   - Branch: `*/main`
   - Script Path: `Jenkinsfile`

### 4. GitLab Webhook 연결

GitLab 프로젝트 → **Settings → Webhooks**:
- URL: 위에서 복사한 Jenkins webhook URL
- Trigger: **Push events** (Branch: `main`)
- SSL verification: 비활성화 (내부망)

### 5. Synology 역방향 프록시

**DSM → 제어판 → 로그인 포털 → 고급 → 역방향 프록시 → 생성**:

| 항목 | 값 |
|------|------|
| 설명 | `feeling-palette-api` |
| 소스 프로토콜 | HTTPS |
| 소스 호스트 | `feeling-api.sedoli.cloud` |
| 소스 포트 | 443 |
| 대상 프로토콜 | HTTP |
| 대상 호스트 | `localhost` |
| 대상 포트 | `8100` |

### 6. DNS + SSL

- **DNS**: `feeling-api.sedoli.cloud` → NAS 외부 IP (A 레코드 또는 CNAME)
- **SSL**: 제어판 → 보안 → 인증서에서 Let's Encrypt 발급

## Jenkinsfile 설명

현재 파이프라인:

```groovy
pipeline {
    agent any

    environment {
        IMAGE_NAME = 'feeling-palette-api'
        CONTAINER_NAME = 'feeling-palette-api'
        GEMINI_API_KEY = credentials('gemini-api-key')
    }

    stages {
        stage('Checkout') { steps { checkout scm } }

        stage('Build') {
            steps { sh 'docker build -t ${IMAGE_NAME}:latest .' }
        }

        stage('Deploy') {
            steps {
                sh 'docker stop ${CONTAINER_NAME} || true'
                sh 'docker rm ${CONTAINER_NAME} || true'
                sh '''
                    docker run -d \
                        --name ${CONTAINER_NAME} \
                        --restart unless-stopped \
                        -p 8100:8080 \
                        -e GEMINI_API_KEY=${GEMINI_API_KEY} \
                        ${IMAGE_NAME}:latest
                '''
            }
        }

        stage('Health Check') {
            steps {
                sh '''
                    for i in 1 2 3 4 5; do
                        sleep 3
                        docker exec ${CONTAINER_NAME} python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/docs')" && echo "Health check passed" && exit 0
                        echo "Attempt $i failed, retrying..."
                    done
                    echo "Health check failed after 5 attempts"
                    exit 1
                '''
            }
        }

        stage('Cleanup') { steps { sh 'docker image prune -f' } }
    }

    post {
        failure { sh 'docker logs ${CONTAINER_NAME} || true' }
    }
}
```

### 주의: NAS Docker 특성

- **`docker compose` V2 미지원**: 순수 `docker` 명령어만 사용
- **`localhost` 해석 이슈**: `python:3.11-slim`에서 `localhost`가 IPv6(`::1`)로 해석되는 경우가 있어 `127.0.0.1` 명시 권장
- **Jenkins 컨테이너 내부**: `localhost`는 Jenkins 컨테이너 자신을 가리킴 → `docker exec`로 API 컨테이너 내부에서 검증

## 배포 과정

### 일반 배포

```bash
# 1. 변경사항 release/release에 push
git checkout release/release
git add .
git commit -m "설명"
git push origin release/release

# 2. GitLab Web UI에서 Merge Request 생성
# URL: https://git.sedoli.cloud/sdchun/feeling-palette-api/-/merge_requests/new

# 3. main으로 머지 → Jenkins 자동 빌드
```

### 수동 배포

Jenkins Web UI → `feeling-palette-api` → **Build Now**

## 로그 확인

### SSH 접속

```bash
ssh sdchun@sedoli.cloud
```

### 컨테이너 로그

```bash
sudo docker logs -f feeling-palette-api       # 실시간
sudo docker logs --tail 100 feeling-palette-api  # 최근 100줄
sudo docker logs --since 10m feeling-palette-api # 최근 10분
```

### 컨테이너 상태

```bash
sudo docker ps | grep feeling
sudo docker exec feeling-palette-api env | grep GEMINI  # 환경변수 확인
```

### Synology Container Manager (GUI)

**DSM → Container Manager → 컨테이너 → feeling-palette-api → 로그 탭**

## 트러블슈팅

### 500 Internal Server Error
- 로그 확인: `docker logs feeling-palette-api`
- 보통 원인: Gemini API 키 문제, API 비활성화, rate limit

### Jenkins 빌드 실패
- `docker compose` 명령어 사용 시 → `docker` 명령어로 교체
- Git authentication 실패 → GitLab access token 재확인
- `COPY *.py .` 에러 → 목적지에 `/` 추가 (`COPY *.py ./`)

### Health check 실패
- 컨테이너 실행은 성공했지만 헬스체크 실패 → `sleep` 늘리기
- `localhost` → `127.0.0.1`로 명시
- IPv6 지원 안 되는 slim 이미지 고려

### 도메인 접근 안 됨
- DNS 확인: `dig feeling-api.sedoli.cloud`
- 인증서 만료 확인 (Let's Encrypt 3개월 주기)
- NAS 역방향 프록시 설정 확인

## 비용

- 전기료만 (NAS 24시간 운영)
- GitLab/Jenkins/Gemini 모두 무료 or 저렴한 사용량
