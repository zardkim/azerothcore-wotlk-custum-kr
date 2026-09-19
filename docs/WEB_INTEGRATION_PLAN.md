# WoW 웹 포털 통합 계획서

> **참고 (2026-09-19)**: 이 문서는 작성 당시 시점의 스냅샷입니다. 이후 `D:/project/wow_web`은
> 정리되어 삭제되었고, `azerothcore-playerbot-kr/web/`도 구버전이 되어 정리 대상이 되었습니다.
> 현재 이 프로젝트의 web 앱 정본은 이 저장소의 `web/wow-web/`입니다. 아래 본문의 경로 언급은
> 역사적 기록으로 남겨둡니다.

## 0. 결론 먼저 — 이미 있는 것 / 새로 해야 하는 것

`D:/project/wow_web/wow-web`을 확인한 결과, 요청하신 4개 기능이 **이미 코드로 구현되어 있습니다**:

| 요청 기능 | 실제 구현 위치 | 상태 |
|---|---|---|
| 계정 생성 | `src/app/api/register/route.ts`, `src/lib/account.ts` (SRP6 해시로 `account` 테이블에 직접 INSERT) | ✅ 구현됨 |
| 서버 상태 | `src/components/sections/ServerStatus.tsx`, `src/lib/status.ts` | ✅ 구현됨 |
| 온라인 접속 멤버 목록 | 위와 동일 (`getOnlinePlayers` — 이름/종족/직업/레벨 테이블) | ✅ 구현됨 |
| 클라이언트 다운로드 링크 | 관리자 페이지(`/admin`)에서 `patchUrl` 편집 → `HowToConnect.tsx`에 버튼으로 노출 | ✅ 구현됨 |

추가로 이미 있는 것: 비밀번호 찾기(SOAP), 관리자 대시보드, 랭킹(플레이타임/킬/명예/투기장), 한/영 다국어, 캡차, 이메일 발송.

**따라서 이 계획서의 실제 범위는 "새 기능 개발"이 아니라, 이 앱을 지금 이 프로젝트의 4-컨테이너
Docker Compose 스택에 5번째 컨테이너로 통합하고, AzerothCore 쪽 설정을 웹앱이 기대하는 형태로
맞추는 작업**입니다.

## 1. 원본 보존 원칙

- `D:/project/wow_web/wow-web`은 **절대 수정하지 않음** (원본 개발/테스트용으로 유지)
- 이 프로젝트 전용 사본을 새 경로에 생성: `D:/Project/azerothcore-wotlk-build/web/wow-web`
  (추후 Gitea 저장소 `azerothcore-playerbot-kr/web/`로 편입)
- `node_modules/`, `.next/`, `.env.local`은 복사 대상에서 제외 (재설치/재생성)
- **`.env.local`에는 실전 DB 비밀번호·관리자 비밀번호·세션 시크릿이 평문으로 들어있음** — 이 파일
  자체를 복사하지 말고, 이 프로젝트 전용 비밀값으로 새로 채운 `.env`를 별도 작성

## 2. 왜 SOAP 설정을 먼저 고쳐야 하는가 (중요, 차단 이슈)

현재 `deploy/configs/worldserver.conf`:
```
SOAP.Enabled = 1
SOAP.IP = "127.0.0.1"
SOAP.Port = 7878
```

`SOAP.IP`가 컨테이너 내부 루프백(127.0.0.1)에 바인딩되어 있어서, **다른 컨테이너(`ac-web`)는 물론
Docker의 포트포워딩(`-p 7878:7878`)으로도 도달할 수 없습니다.** 웹앱의 비밀번호 변경/찾기 기능이
SOAP를 쓰므로, 이 값을 컨테이너 내 모든 인터페이스에서 받도록 바꿔야 합니다:

```
SOAP.IP = "0.0.0.0"
```

(계정 "생성" 자체는 SOAP가 아니라 DB에 SRP6 값을 직접 INSERT하는 방식이라 SOAP 없이도 동작하지만,
비밀번호 변경/찾기는 SOAP가 반드시 필요합니다.)

## 3. Docker 통합

### 3-1. Dockerfile 작성 (`web/wow-web/Dockerfile`, 신규)

Next.js 15/16 권장 방식인 `output: "standalone"`으로 멀티스테이지 빌드:

```dockerfile
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/public ./public
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
EXPOSE 3000
CMD ["node", "server.js"]
```

`next.config.ts`에 `output: "standalone"` 한 줄 추가 필요 (사본에서만 수정, 원본은 그대로).

`data/site-content.json`(관리자 페이지에서 수정하는 실시간 콘텐츠)은 이미지에 구워지면 안 되고,
이 프로젝트의 다른 데이터처럼 **bind mount로 영속화**해야 함 — 재배포해도 관리자가 편집한 내용
(realmlist 주소, 다운로드 링크, 소개글 등)이 보존되도록.

### 3-2. `docker-compose.yml`에 5번째 컨테이너 추가

```yaml
  ac-web:
    image: ${DOCKER_REGISTRY}/ac-web:latest
    container_name: ac-web
    networks: [ac-network]
    restart: unless-stopped
    env_file:
      - ${BASE_DATA_DIR}/web.env
    volumes:
      - ${BASE_DATA_DIR}/web-data:/app/data
    ports:
      - "${DOCKER_WEB_EXTERNAL_PORT:-3000}:3000"
    depends_on:
      ac-database:
        condition: service_healthy
```

`ac-network`에 같이 있으므로 DB/SOAP 접속은 외부 포트가 아니라 컨테이너 이름으로:
`DB_HOST=ac-database`, `SOAP_HOST=ac-worldserver`.

### 3-3. `web.env` (신규, `.env`와 별도 파일 — git에 커밋 금지)

```
DB_HOST=ac-database
DB_PORT=3306
DB_AUTH_USER=acore
DB_AUTH_PASS=acore
DB_AUTH_NAME=acore_auth

REALMS=[{"id":1,"name":"AzerothCore","charactersDb":"acore_characters"}]

SERVER_CORE=1
SRP6_SUPPORT=true

SOAP_HOST=ac-worldserver
SOAP_PORT=7878
SOAP_URI=urn:AC
SOAP_USERNAME=<이 프로젝트 전용으로 새로 만들 SOAP 계정>
SOAP_PASSWORD=<새 비밀번호>
SOAP_CA_COMMAND=account create {USERNAME} {PASSWORD}
SOAP_CP_COMMAND=account set password {USERNAME} {PASSWORD} {PASSWORD}

SMTP_HOST=...          # 비밀번호 찾기 이메일 쓸 경우만
ADMIN_USERNAME=admin
ADMIN_PASSWORD=<새 비밀번호>
ADMIN_SESSION_SECRET=<openssl rand -hex 32 로 새로 생성>
```

`SOAP_USERNAME`용 계정은 기존에 쓰던 걸 재사용하지 말고, worldserver 콘솔에서 이 프로젝트용으로
새로 발급:
```
account create websoap <새비밀번호>
account set gmlevel websoap 3 -1
```
(SOAP는 GM 권한 있는 계정만 명령 실행 가능)

## 4. DB 계정 권한 — 선택지

| 방식 | 장점 | 단점 |
|---|---|---|
| **A. 기존 `acore`/`acore` 재사용** | 설정 간단, 추가 작업 없음 | 웹앱(외부 노출 서비스)이 DB 전체 권한을 가짐 — 웹앱 취약점 발생 시 DB 전체가 위험 |
| **B. 웹앱 전용 제한 계정 신규 생성 (권장)** | `acore_auth.account`, `acore_characters.characters`(읽기), `acore_characters.arena_team`(읽기)만 접근 가능 → 피해 범위 최소화 | SQL로 권한을 한 번 더 설정해야 함 |

B안 SQL 예시:
```sql
CREATE USER 'wow_web'@'%' IDENTIFIED BY '<새비밀번호>';
GRANT SELECT, INSERT, UPDATE, ALTER ON acore_auth.account TO 'wow_web'@'%';
GRANT SELECT ON acore_characters.characters TO 'wow_web'@'%';
GRANT SELECT ON acore_characters.arena_team TO 'wow_web'@'%';
FLUSH PRIVILEGES;
```
웹앱은 공개 인터넷에 노출되는 유일한 서비스이므로 **B안을 권장**합니다.

## 5. 클라이언트 다운로드 파일 호스팅

코드 상 `patchUrl`은 그냥 외부 URL 하나입니다 (지금 샘플 데이터도 Synology 공유링크). 세 가지 선택지:
1. **그대로 외부 링크 사용** (Synology File Station 공유 링크, Google Drive 등) — 추가 작업 없음, 지금 바로 가능
2. NAS의 File Station으로 정적 파일 직접 서빙 후 그 URL을 `patchUrl`에 입력
3. `ac-web` 컨테이너에 `public/downloads/`로 직접 포함 — 클라이언트 용량(수 GB~수십 GB)을 이미지/git에 넣는 셈이라 **비권장** (이 프로젝트 전체가 "대용량을 이미지에 넣지 않는다"는 원칙으로 설계됨)

**권장: 1번.** 관리자 페이지에서 링크만 바꾸면 되므로 별도 개발 불필요.

## 6. 반영 순서

1. `web/wow-web`으로 사본 생성 (node_modules/.next/.env.local 제외)
2. `next.config.ts`에 `output: "standalone"` 추가
3. `Dockerfile` 작성
4. `deploy/configs/worldserver.conf`의 `SOAP.IP`를 `0.0.0.0`으로 변경 (로컬 배포 파일 + 이미 배포된 서버의 실제 파일 둘 다)
5. worldserver 콘솔에서 SOAP 전용 계정 생성 + GM 권한 부여
6. (권장) DB에 `wow_web` 제한 계정 생성
7. `docker-compose.yml`에 `ac-web` 서비스 추가, `web.env`/`web-data/` 볼륨 경로를 `setup.sh`에도 반영
8. 로컬에서 `docker build` → 브라우저로 회원가입/로그인/서버상태/온라인목록 동작 확인
9. Harbor에 `ac-web` 이미지 푸시 (버전 태그 + latest, 저작자 라벨 동일 규칙 적용)
10. 서버에서 `docker compose pull && up -d`
11. 관리자 페이지(`/admin`)에서 realmlist 주소·다운로드 링크·소개 문구를 실제 값으로 수정
12. 위키에 `Web-Portal.md` 페이지 추가 (`web.env` 항목 설명, SOAP 계정 재발급 절차, 관리자 페이지 사용법)

## 7. 배포 후 확인 체크리스트

- [ ] 회원가입 → `acore_auth.account`에 실제 행 생성되는지 (`SELECT username FROM account;`)
- [ ] 생성한 계정으로 실제 WoW 클라이언트 로그인 성공
- [ ] 서버 상태 패널에 온라인 표시 (테스트 중이라면 플레이어봇들이 "온라인 캐릭터 목록"에 같이
      뜨는지 확인 — 봇도 `characters.online=1`이라 그대로 뜹니다. 실제 플레이어만 보이길
      원하시면 `getOnlinePlayers` 쿼리에 봇 계정 필터를 추가하는 작업이 별도로 필요합니다)
- [ ] 비밀번호 찾기(SOAP 경유) 정상 동작
- [ ] 관리자 페이지 로그인 및 realmlist/다운로드 링크 저장 후 새로고침해도 유지되는지 (`web-data` 볼륨 확인)
- [ ] 컨테이너 재시작(`docker compose restart ac-web`) 후에도 관리자 편집 내용 보존되는지

## 8. 미결정 사항 (진행 전 확인 필요)

- 봇 계정을 "온라인 멤버 목록"에서 제외할지 여부 (위 체크리스트 참고)
- 웹 포털 외부 노출 방식: 그냥 포트(`3000`)로 직접 노출 vs 리버스 프록시(Nginx/Caddy)로 도메인 연결 + HTTPS 적용 — 공개 서비스라면 HTTPS 권장
- DB 계정을 A안(재사용)으로 할지 B안(전용 계정)으로 할지
