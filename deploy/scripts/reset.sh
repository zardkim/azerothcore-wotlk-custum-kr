#!/usr/bin/env bash
#
# reset.sh — DB를 "65개 모듈 + 한글화 SQL이 적용된 베이스라인" 상태로 되돌린다.
# ac-database-kr 이미지가 그 상태를 이미지 안에 구워둔 시드로 갖고 있고,
# /var/lib/mysql이 비어있으면 컨테이너가 자동으로 그 시드를 복사해 넣는 구조를
# 그대로 이용한다 (kr-patch/database-baked-v3/entrypoint-wrapper.sh 참고).
#
# ⚠ 베이스라인 이후 가입한 계정/생성된 캐릭터/변경된 게임 콘텐츠는 전부 사라진다.
#   그래서 초기화 직전 backup.sh를 자동으로 먼저 실행한다(끌 수 없음 — 안전망).
#
# 사용법: ./reset.sh [--restore-after] [--yes]
#   --restore-after   초기화 직후, 방금 만든 백업(acore_auth/acore_characters)을
#                      바로 복원해서 "게임 콘텐츠만 베이스라인으로 되돌리고
#                      계정/캐릭터는 그대로 유지"하는 모드로 동작한다.
#   --yes             확인 프롬프트를 건너뛴다 (자동화용).
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."   # deploy/ 로 이동 (compose/.env 기준)

RESTORE_AFTER=0
ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --restore-after) RESTORE_AFTER=1 ;;
    --yes) ASSUME_YES=1 ;;
    *) echo "[오류] 알 수 없는 옵션: $arg" >&2; exit 1 ;;
  esac
done

if [ ! -f .env ]; then
  echo "[오류] .env 파일이 없습니다." >&2
  exit 1
fi

BASE_DATA_DIR=$(grep -E '^BASE_DATA_DIR=' .env | tail -1 | cut -d= -f2-)
if [ -z "${BASE_DATA_DIR:-}" ]; then
  echo "[오류] .env에 BASE_DATA_DIR이 설정되어 있지 않습니다." >&2
  exit 1
fi

MYSQL_DIR="$BASE_DATA_DIR/mysql"
DB_CONTAINER="${DB_CONTAINER:-ac-database}"

if [ "$ASSUME_YES" -ne 1 ]; then
  echo "########################################################################"
  echo "  서버 초기화 — $MYSQL_DIR 아래 모든 DB 데이터를 지우고"
  echo "  ac-database-kr 이미지에 구워진 베이스라인(65개 모듈 + 한글화 SQL)으로"
  echo "  되돌립니다. 진행 전 계정/캐릭터를 자동으로 백업합니다."
  if [ "$RESTORE_AFTER" -eq 1 ]; then
    echo "  --restore-after 지정됨: 초기화 직후 방금 만든 백업을 바로 복원합니다"
    echo "  (게임 콘텐츠만 베이스라인, 계정/캐릭터는 유지)."
  else
    echo "  --restore-after 없음: 초기화 후 계정/캐릭터는 비어있는 상태로 남습니다."
    echo "  나중에 필요하면 ./scripts/restore.sh <backup_id> 로 직접 복원하세요."
  fi
  echo "########################################################################"
  read -r -p ">> 계속하려면 RESET을 입력하세요: " CONFIRM
  if [ "$CONFIRM" != "RESET" ]; then
    echo ">> 취소되었습니다."
    exit 1
  fi
fi

echo ">> [1/6] 초기화 직전 계정/캐릭터 백업 중..."
BACKUP_OUTPUT=$(./scripts/backup.sh)
echo "$BACKUP_OUTPUT"
BACKUP_ID=$(echo "$BACKUP_OUTPUT" | grep -oE '[0-9]{8}-[0-9]{6}' | tail -1)
if [ -z "$BACKUP_ID" ]; then
  echo "[오류] 백업 ID를 확인하지 못했습니다. backup.sh 출력을 확인하세요." >&2
  exit 1
fi
echo ">> 백업 ID: $BACKUP_ID"

echo ">> [2/6] worldserver/authserver/web 중지..."
docker compose stop ac-worldserver ac-authserver ac-web 2>/dev/null || true

echo ">> [3/6] $DB_CONTAINER 중지 및 DB 데이터 삭제..."
docker compose stop "$DB_CONTAINER" 2>/dev/null || true
if [ -d "$MYSQL_DIR" ]; then
  find "$MYSQL_DIR" -mindepth 1 -maxdepth 1 -exec rm -rf {} +
fi

echo ">> [4/6] $DB_CONTAINER 재기동 (베이스라인 재시딩 대기)..."
docker compose up -d "$DB_CONTAINER"
for i in $(seq 1 60); do
  STATUS=$(docker inspect -f '{{.State.Health.Status}}' "$DB_CONTAINER" 2>/dev/null || echo "starting")
  if [ "$STATUS" = "healthy" ]; then
    echo ">> $DB_CONTAINER healthy."
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo "[오류] $DB_CONTAINER 가 3분 내에 healthy 상태가 되지 않았습니다. 'docker logs $DB_CONTAINER'로 확인하세요." >&2
    exit 1
  fi
  sleep 3
done

echo ">> [5/6] 나머지 서비스 재기동..."
docker compose up -d

if [ "$RESTORE_AFTER" -eq 1 ]; then
  echo ">> [6/6] 방금 만든 백업($BACKUP_ID) 복원 중..."
  ./scripts/restore.sh "$BACKUP_ID" --force --yes
else
  echo ">> [6/6] --restore-after 미지정 — 계정/캐릭터는 베이스라인 상태(비어있음)로 둡니다."
  echo "   나중에 복원하려면: ./scripts/restore.sh $BACKUP_ID --force"
fi

echo ">> 초기화 완료."
