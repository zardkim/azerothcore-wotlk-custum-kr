# AzerothCore Playerbot 리팩 — Docker 배포 (한글화 완료본)

65개 모듈 + 한글화 SQL(01~06) + 한글 DBC + 실제 맵/vmap/mmap 데이터가 전부 적용된 상태로
자신의 컨테이너 레지스트리(`.env`의 `DOCKER_REGISTRY`)에 이미지로 구워져 있어야 합니다.
이미지를 직접 빌드/push하는 방법은 아래 "코어/모듈 업데이트 적용" 절 참고.

**상시 컨테이너**: `ac-database`, `ac-worldserver`, `ac-authserver`, `ac-web`(웹 포털) +
1회성 `ac-dirs-init`(폴더 준비), `ac-kr-data-init`(한글 DBC/data 최초 자동 설치),
`ac-playerbots-data-init`(mod-playerbots 갱신 확인).

모든 실제 데이터는 **사용자가 지정한 폴더 아래에 눈에 보이는 구조**로 저장됩니다 — 어떤 볼륨/디스크든
경로 하나(`BASE_DATA_DIR`)만 바꾸면 그쪽에 설치됩니다.

```
${BASE_DATA_DIR}/
├── configs/         worldserver.conf, authserver.conf, 모듈 conf (직접 수정 가능)
├── data/            실제 맵/vmap/mmap/dbc (koKR 포함) — 최초 설치 시 자동으로 채워짐 (아래 참고)
│   └── playbots/    mod-playerbots 자체 갱신 확인용 SQL (자동 생성됨)
├── mysql/           MySQL 데이터 파일 (65개 모듈+한글화 SQL 이미 적용됨, 비어있으면 자동 시딩)
└── logs/            서버 로그
```

## 배포 방법

```bash
# 1) .env 준비 — BASE_DATA_DIR·DOCKER_REGISTRY·KR_DATA_URL·KR_DBC_URL을 배포 환경에 맞게 지정
cp .env.example .env
vi .env
# Synology NAS 기본값: BASE_DATA_DIR=/volume1/docker/azerothcore (볼륨 번호는 원하는 대로)
# Ubuntu 등 일반 리눅스 기본값: BASE_DATA_DIR=/opt/azerothcore
# DOCKER_REGISTRY: 이 이미지들을 구워서 올려둔 자신의 레지스트리 주소+프로젝트
# (예: harbor.example.com/azerothcore, 또는 Docker Hub 계정 등)
# KR_DATA_URL/KR_DBC_URL: data.zip / 한글 DBC zip 다운로드 주소 (아래 참고)

# 2) 필요한 폴더 미리 생성 + configs 복사 (최초 1회만)
chmod +x setup.sh
./setup.sh

# 3) 레지스트리가 private면 로그인
docker login "$DOCKER_REGISTRY"

# 4) 실행 — 최초 기동 시 ac-kr-data-init이 한글 DBC/data를 자동으로 받아서 풀어줍니다
docker compose pull
docker compose up -d
docker compose logs -f ac-kr-data-init   # 진행 상황 확인 (용량에 따라 몇 분~몇십 분)
```

### 한글 DBC/data(maps/vmaps/mmaps/dbc) — 최초 1회 자동 설치

용량이 커서(약 4GB) 이미지로 배포하지 않고, `ac-kr-data-init` 컨테이너가 나스 파일
공유 등에서 두 zip을 순서대로 받아 `${BASE_DATA_DIR}/data/`에 자동으로 풀어줍니다:

1. `KR_DATA_URL` → `data.zip` (Cameras/maps/mmaps/vmaps/기본 dbc)
2. `KR_DBC_URL` → `DBC 3.3.5a 12340.zip` (한글 DBC) — 1번을 푼 뒤 그 위에 덮어써서
   `data/dbc/` 안의 같은 파일명을 한글판으로 교체합니다(별도 `koKR` 서브폴더 아님).

**Synology File Station의 "공유" 링크는 권장하지 않습니다** — 브라우저 전용 HTML
페이지를 주는 경우가 있어 `curl`로 직접 받아지지 않습니다(실제로 겪음). 대신
**Web Station 등으로 정적 파일 서버**를 하나 만들어서 그 위에 zip을 올려두고, 일반
HTTP(S) 정적 파일 URL을 쓰세요 — 예: `https://dl.example.com/wow_data/data.zip`.
파일명에 공백이 있으면 URL 인코딩(`%20`)이 필요합니다. 링크를 `.env`에 넣기 전에
아래처럼 직접 확인해보세요:

```bash
curl -fL -o /tmp/test.zip "<다운로드 주소>"   # HTML이 아니라 실제 zip이 받아져야 함
curl -sI "<다운로드 주소>"                     # Content-Type: application/zip 인지 확인
```

- **최초 설치에서만 동작**: 이미 `${BASE_DATA_DIR}/data/dbc`에 내용이 있으면(과거에
  수동으로 넣어둔 서버 포함) 아무것도 하지 않고 건너뜁니다 — 업데이트할 때마다 매번
  다시 받지 않습니다.
- **DBC/data 내용이 바뀌면**: 나스의 zip을 새 버전으로 교체한 뒤,
  `${BASE_DATA_DIR}/data/.kr-data-installed` 마커 파일을 수동으로 지우고
  `docker compose up ac-kr-data-init`을 다시 실행하면 재설치됩니다(자동 감지 아님 —
  의도적으로 수동 절차로 둠).
- **직접 복사하고 싶다면**: `KR_DATA_URL`/`KR_DBC_URL` 없이도 기존처럼
  `${BASE_DATA_DIR}/data/`에 `maps`/`vmaps`/`mmaps`/`dbc`를 직접 복사해두면
  `ac-kr-data-init`이 이를 인식하고 건너뜁니다.
- `KR_DBC_URL`을 비워두면 기본(영문) dbc만 설치됩니다(한글 DBC는 나중에 수동으로
  `${BASE_DATA_DIR}/data/dbc/`에 덮어써서 넣을 수 있습니다).

## 계정/캐릭터 백업 · 복원

`scripts/backup.sh`, `scripts/restore.sh`는 **봇 계정(기본 접두어 `rndbot`)을 제외한
실제 플레이어 계정/캐릭터만** 테이블 단위로 선별 백업/복원합니다 — `acore_auth`/
`acore_characters` 전체를 통째로 덤프하지 않습니다. 이 프로젝트는 개인/소규모 운영이
목적이라, 수만 개에 이를 수 있는 봇 계정까지 매번 백업하는 건 낭비이고 코어/모듈
업데이트 전후로 실제 플레이어 진행 상황만 보존하면 충분합니다. `acore_playerbots`
(봇 AI 상태)와 `acore_world`(게임 콘텐츠)도 원래부터 대상이 아닙니다 — 봇 계정 자체는
재기동 시 mod-playerbots가 알아서 다시 채워주고, 게임 콘텐츠는 `ac-database-kr` 이미지의
베이크드 시드가 원본이기 때문입니다.

```bash
# 백업 (BASE_DATA_DIR/backups/<타임스탬프>/에 저장, 기본 14개 보관)
./scripts/backup.sh
BACKUP_KEEP=30 ./scripts/backup.sh    # 보관 개수 조절
BOT_PREFIX=myprefix ./scripts/backup.sh  # 봇 계정 접두어를 바꿨다면 지정
                                          # (playerbots.conf의 AiPlayerbot.RandomBotAccountPrefix와 맞출 것, 기본 rndbot)

# 복원 (대상 DB에 이미 실제 계정이 있으면 기본적으로 거부됨 — 병합이 아니라 교체라서.
# 봇 계정은 영향받지 않음)
find "$BASE_DATA_DIR/backups" -maxdepth 1 -type d   # 백업 목록 확인
./scripts/restore.sh <backup_id>
./scripts/restore.sh <backup_id> --force             # 기존 실제 계정이 있어도 강제 덮어쓰기
```

테이블 목록/필터 조건은 `scripts/lib/player-tables.sh`에서 관리하며, 웹 관리자 UI
(`src/lib/backup-storage.ts`)도 정확히 같은 목록을 따로 유지합니다 — 둘 중 하나만
고치면 CLI와 웹 UI 백업 범위가 서로 달라지니 항상 같이 수정하세요.

복원 중에는 `ac-worldserver`/`ac-authserver`가 잠시 멈췄다가 완료 후 자동으로
다시 시작됩니다.

**웹 관리자 페이지**(`/admin/backups`)에서도 같은 작업을 할 수 있습니다 — 같은
`${BASE_DATA_DIR}/backups` 볼륨을 공유해서 CLI로 만든 백업이 웹에도 보이고, 웹에서 만든
백업을 CLI로도 복원할 수 있습니다. 단, 웹 UI는 docker 제어 권한이 없어서(의도적으로
부여하지 않음) 복원 시 `ac-worldserver`/`ac-authserver`를 자동으로 멈추지 못합니다 —
**웹 UI로 복원할 땐 점검 시간에만 하거나, 미리 CLI로 두 서비스를 내려두세요.**

## 서버 초기화 (베이스라인으로 되돌리기)

`scripts/reset.sh`는 `${BASE_DATA_DIR}/mysql`을 비워서 `ac-database-kr` 이미지에
구워진 베이스라인(65개 모듈 + 한글화 SQL 적용 완료 상태)으로 되돌립니다. 진행 전
계정/캐릭터를 **자동으로 먼저 백업**하므로 끌 수 없는 안전망이 걸려 있습니다.

```bash
./scripts/reset.sh                  # 초기화만 (계정/캐릭터는 빈 상태로 남음)
./scripts/reset.sh --restore-after  # 초기화 직후 방금 만든 백업을 바로 복원
                                     # (게임 콘텐츠만 베이스라인, 계정/캐릭터는 유지)
```

`RESET`을 직접 입력해야 진행되는 확인 프롬프트가 있고(`--yes`로 스킵 가능),
`configs/`·`data/`(맵 등)·`logs/`는 건드리지 않습니다.

## 코어/모듈 업데이트 적용

코어(azerothcore-wotlk) 또는 65개 모듈 중 일부가 업데이트됐을 때, **라이브 서버의
계정/캐릭터/기존 게임 콘텐츠를 보존한 채** 새 SQL·바이너리만 반영하는 절차입니다.

### 1) 업데이트 확인 (아무것도 바꾸지 않음)

```bash
./scripts/check-updates.sh
```
코어는 `origin/<현재 브랜치>`, 각 모듈은 `modules.lock`에 고정된 commit과 원격 최신
commit을 비교해서 표로 보여줍니다. 실제 반영 여부는 변경 로그를 보고 직접 판단하세요 —
특히 `mod-playerbots`처럼 코어 자체에 영향을 주는 모듈은 신중하게 검토하세요.

### 2) 반영하기로 했으면 — 소스 갱신 + 이미지 재빌드 (수동)

```bash
# modules.lock에서 해당 모듈 줄의 commit을 새 값으로 수정한 뒤
./install-modules.sh                 # 또는 FORCE=1로 해당 모듈만 재설치
# 코어/모듈 재컴파일 + 이미지 빌드 (build4.log에서 검증된 기존 파이프라인 재사용)
# worldserver/authserver/db-import 이미지를 새 버전 태그로 harbor에 push
```
이 저장소는 처음부터 재현성을 위해 `modules.lock`으로 모듈 commit을 고정해뒀습니다
(자동 최신화 없음 — breaking change 가능성 때문에 항상 사람이 판단).

### 3) 라이브 서버에 반영

먼저 서버의 `deploy/` 폴더 자체를 최신 내용으로 갱신하세요(예: `git pull`, 또는
바뀐 파일만 `scp`) — 새 모듈의 conf.dist가 `deploy/configs/`에, 새 스크립트가
`deploy/scripts/`에 들어있어야 다음 단계가 그걸 찾아서 씁니다.

```bash
./scripts/apply-update.sh
```
순서: **①계정/캐릭터 백업(자동) → ②새 이미지 pull → ③새로 추가된 모듈의 기본 설정
파일 배치(이미 있는 설정은 절대 안 건드림) → ④`ac-db-import`로 증분 SQL 반영(해시
기반이라 이미 적용된 건 건너뜀) → ⑤worldserver/authserver를 새 이미지로 교체
재기동.** `ac-db-import`는 평소 `docker compose up -d`에는 끼지 않는
`profiles: [update]` 서비스라 업데이트할 때만(`apply-update.sh` 또는
`docker compose up ac-db-import`) 실행됩니다.

**③이 핵심입니다** — 예전에는 새 모듈이 추가되면 그 모듈의 conf 파일을 SSH로
접속해서 하나씩 복사해야 했지만, 이제 `apply-update.sh` 한 번으로 자동 배치됩니다.
`${BASE_DATA_DIR}/configs/`에 이미 있는 파일(기존 모듈 튜닝값 포함)은 절대 덮어쓰지
않고, 그 폴더에 아직 없는 파일(신규 모듈의 기본 conf)만 새로 놓습니다.

**롤백**: 이미지 태그를 `latest`로 덮어쓰지 말고 버전 태그로 관리해두면, 문제가 생겼을 때
이전 태그로 `docker compose up -d`만으로 되돌릴 수 있습니다. `dbimport`가 적용한 SQL은
기본적으로 전진 전용(forward-only)이라, DB 롤백이 꼭 필요하면 ①에서 만든 백업을
`scripts/restore.sh`로 복원하세요.

## 왜 이렇게 구성했나

- `ac-database`는 SQL을 매번 다시 실행하는 대신 **이미 적용된 실제 DB 데이터 파일**을 이미지 안
  별도 경로(seed)에 구워뒀습니다. 컨테이너 시작 시 `/var/lib/mysql`이 비어있으면 그 seed에서
  자동으로 복사해 채운 뒤 mysqld를 시작합니다 (몇 초면 서비스 가능, SQL 재실행 없음).
- 이미 데이터가 있으면 건너뛰므로, 재기동/재배포해도 **기존에 쌓인 실제 캐릭터/계정 데이터를
  덮어쓰지 않습니다.**
- 맵 데이터는 용량이 커서 Docker 이미지로 배포하면 Docker 저장소(보통 특정 볼륨에 고정)에 불필요한
  용량이 이중으로 쌓이는 문제가 있어, 이미지가 아닌 **직접 복사** 방식으로 뺐습니다.

## 최초 기동 후 반드시 할 일

### 1. realmlist 주소 설정

기본값은 로컬 테스트용 `127.0.0.1`입니다. 클라이언트가 실제로 접근 가능한 주소로 바꿔야
합니다(`flag`는 반드시 `0`이어야 합니다 — `3`이면 오프라인/버전 불일치로 클라이언트 목록에서
빠집니다):

```bash
docker exec -it ac-database mysql -uacore -pacore acore_auth \
  -e "UPDATE realmlist SET name='AzerothCore', address='<서버 IP 또는 도메인>' WHERE id=1;"
```

- **같은 LAN에서만 접속** → 서버의 내부(사설) IP (예: `192.168.0.10`)
- **외부에서도 접속 필요** → 공인 IP/도메인 + 공유기 포트포워딩(3724, 8085) 필요. 단, 공유기가
  NAT 루프백(hairpin NAT)을 지원하지 않으면 같은 LAN 내부에서는 그 도메인으로 접속이 안 될 수
  있습니다 — 이 경우 내부망에서는 내부 IP, 외부망에서는 도메인을 각각 써야 합니다.

### 2. 계정 생성 및 GM 권한 설정

```bash
docker attach ac-worldserver
```

`AC>` 프롬프트에서:

```
account create <계정명> <비밀번호>
account set gmlevel <계정명> 3 -1
```

`<gmlevel>`은 0(일반)~3(관리자), 마지막 인자는 렐름 ID(특정 렐름에만 적용하려면 그 ID, 서버의
모든 렐름에 적용하려면 `-1`)입니다.

**콘솔 종료는 반드시 `Ctrl+P`, `Ctrl+Q`(순서대로)** — `Ctrl+C`를 누르면 worldserver 프로세스
자체가 종료됩니다.

전체 GM 명령어 목록: [AzerothCore GM Commands](https://www.azerothcore.org/wiki/gm-commands)

## 설정 수정

`${BASE_DATA_DIR}/configs/worldserver.conf`, `authserver.conf`, `modules/*.conf`를 직접 열어서
수정한 뒤 `docker compose restart ac-worldserver ac-authserver`로 반영하면 됩니다. `creature_
template`/`npc_text`/`gossip_*` 등 DB 값을 직접 수정한 경우도 worldserver가 기동 시 메모리로
캐싱하기 때문에 마찬가지로 재시작이 필요합니다(재시작하면 접속 중이던 봇/플레이어는 전부
끊깁니다 — `ac-database` 컨테이너 자체는 재시작할 필요 없음).

### 봇 숫자 조정

설정 파일: `configs/modules/playerbots.conf`

```
AiPlayerbot.MinRandomBots = 20
AiPlayerbot.MaxRandomBots = 20
```

기본 배포값은 `20`(가벼운 시작값)입니다. **봇 수가 많아질수록 더 많은 RAM/CPU가 필요**하므로
서버 사양에 맞게 점진적으로 늘려가며 테스트하는 걸 권장합니다. 완전히 끄려면
`AiPlayerbot.Enabled = 0`. 봇에게 직접 명령을 내리는 채팅 명령어 목록은
[mod-playerbots Playerbot Commands](https://github.com/mod-playerbots/mod-playerbots/wiki/Playerbot-Commands)
참고. 모듈이 제공하는 기능형 NPC 소환 명령어는
[Wiki: NPC 소환 명령어](../../wiki/NPC-소환-명령어) 참고.

## Windows PC에서 DB에 직접 접속하기

매번 `docker exec`로 들어가는 대신 HeidiSQL/MySQL Workbench/DBeaver 등으로 서버의 DB에 직접
접속해서 작업할 수 있습니다.

| 항목 | 값 |
|---|---|
| 호스트 | 서버의 내부 IP (예: `192.168.0.10`) |
| 포트 | `.env`의 `DOCKER_DB_EXTERNAL_PORT` (기본 `3307`) |
| 계정 | `acore` / `acore` (또는 `root` — `.env`의 `DOCKER_DB_ROOT_PASSWORD`) |

접속이 "Access denied"로 실패하면 계정의 허용 호스트를 확인하세요:

```bash
docker exec -it ac-database mysql -uroot -p<루트비밀번호> \
  -e "SELECT user,host FROM mysql.user WHERE user='acore';"
```

`acore | %`가 없으면 추가:

```sql
CREATE USER IF NOT EXISTS 'acore'@'%' IDENTIFIED BY 'acore';
GRANT ALL PRIVILEGES ON *.* TO 'acore'@'%';
FLUSH PRIVILEGES;
```

DB를 직접 조작할 땐 한글 SQL 관련 [Wiki: 한글화 내역](../../wiki/한글화-내역)의 문자셋
주의사항도 참고하세요(GUI 툴 접속 시 `SET NAMES utf8mb4;` 필요).

## 완전 초기화하고 싶을 때

수동으로 `rm -rf "${BASE_DATA_DIR}/mysql"` 하지 말고 `./scripts/reset.sh`를 쓰세요 — 초기화 직전
계정/캐릭터를 자동으로 백업해주는 안전망이 있습니다. 자세한 내용은 위 "서버 초기화" 절 참고.

## 로컬 Windows 개발환경에서 테스트할 때

`ac-database-kr` 이미지는 Linux에서 구워져서 데이터 디렉터리가
`lower_case_table_names=0`으로 고정돼 있습니다. Windows Docker Desktop의 바인드 마운트
(NTFS, 대소문자 미구분)에서 이 이미지를 그대로 돌리면 MySQL이 기동 시점에 이 설정을
`2`로 재판단하면서 충돌해 **기동 자체가 실패**합니다(실제 배포 대상인 Synology/Ubuntu 등
Linux 호스트는 파일시스템이 대소문자를 구분해서 이 문제가 없습니다).

로컬 Windows에서 스크립트나 웹 UI를 테스트해야 한다면, `${BASE_DATA_DIR}/mysql` 바인드
마운트 대신 Docker named volume(Linux VM 내부, 대소문자 구분)을 쓰는
`docker-compose.local-test-override.yml`을 같이 넘기세요 — 이 파일은 로컬 테스트 전용이라
배포에는 쓰지 않습니다:

```bash
docker compose -f docker-compose.yml -f docker-compose.local-test-override.yml up -d
```

## 구성 이미지

| 이미지 | 태그 | 내용 |
|---|---|---|
| `ac-database-kr` | `1.0.0`, `latest` | 65개 모듈 SQL + 한글화 SQL(01~06) 적용 완료된 MySQL 데이터, 계정 acore/acore |
| `ac-playerbots-data` | `1.0.0`, `latest` | mod-playerbots 자체 갱신 확인용 소스 SQL 트리 |
| `ac-wotlk-worldserver` | `1.0.0`, `latest` | 65개 모듈 포함 컴파일된 worldserver 바이너리 |
| `ac-wotlk-authserver` | `1.0.0`, `latest` | 65개 모듈 포함 컴파일된 authserver 바이너리 |

모든 이미지 저작자: `zardkim` (OCI 라벨로 포함됨, `docker inspect <이미지> --format '{{json .Config.Labels}}'`로 확인 가능)

## 포트

- 3724: authserver (클라이언트 접속)
- 8085: worldserver
- 7878: SOAP
- 3307: MySQL (다른 MySQL/MariaDB와 충돌 방지용으로 기본값을 3307로 뒀습니다)

`.env`에서 `DOCKER_*_EXTERNAL_PORT` 값으로 변경 가능합니다.

## 문제가 생겼을 때

실제 구축 과정에서 겪었던 컴파일 에러, mod-playerbots 크래시, Synology `@eaDir` DB 초기화 루프,
realmlist 문제, 레지스트리 연결 실패 등은 [Wiki: 트러블슈팅](../../wiki/트러블슈팅)에 정리돼
있습니다.
