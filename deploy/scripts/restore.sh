#!/usr/bin/env bash
#
# restore.sh — backup.sh가 만든 계정(acore_auth)/캐릭터(acore_characters) 백업을
# 되살린다. mysqldump 기본 옵션(--opt)에 DROP TABLE IF EXISTS가 포함돼 있어서,
# 복원 대상 DB에 이미 있는 계정/캐릭터 테이블은 백업 시점 데이터로 완전히
# 덮어써진다 — 병합이 아니다. 그래서 대상 DB가 비어있지 않으면 기본적으로 막는다.
#
# 사용법: ./restore.sh <backup_id> [--force] [--yes]
#   <backup_id>  backups/ 아래 폴더 이름 (예: 20260915-140000). ls로 확인.
#   --force      대상 DB에 이미 계정이 있어도 강제로 덮어쓴다 (위험 — 지금 데이터가 사라짐).
#   --yes        확인 프롬프트를 건너뛴다 (스크립트/cron에서 호출할 때만 사용).
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."   # deploy/ 로 이동 (compose/.env 기준)

BACKUP_ID="${1:-}"
FORCE=0
ASSUME_YES=0
for arg in "${@:2}"; do
  case "$arg" in
    --force) FORCE=1 ;;
    --yes) ASSUME_YES=1 ;;
    *) echo "[오류] 알 수 없는 옵션: $arg" >&2; exit 1 ;;
  esac
done

if [ -z "$BACKUP_ID" ]; then
  echo "사용법: ./restore.sh <backup_id> [--force] [--yes]" >&2
  exit 1
fi

if [ ! -f .env ]; then
  echo "[오류] .env 파일이 없습니다." >&2
  exit 1
fi

BASE_DATA_DIR=$(grep -E '^BASE_DATA_DIR=' .env | tail -1 | cut -d= -f2-)
if [ -z "${BASE_DATA_DIR:-}" ]; then
  echo "[오류] .env에 BASE_DATA_DIR이 설정되어 있지 않습니다." >&2
  exit 1
fi

DB_CONTAINER="${DB_CONTAINER:-ac-database}"
DB_USER="${DB_USER:-acore}"
DB_PASS="${DB_PASS:-acore}"

BACKUP_DIR="$BASE_DATA_DIR/backups/$BACKUP_ID"
AUTH_DUMP="$BACKUP_DIR/acore_auth.sql.gz"
CHAR_DUMP="$BACKUP_DIR/acore_characters.sql.gz"

if [ ! -d "$BACKUP_DIR" ] || [ ! -f "$AUTH_DUMP" ] || [ ! -f "$CHAR_DUMP" ]; then
  echo "[오류] 백업을 찾을 수 없습니다: $BACKUP_DIR" >&2
  echo "       사용 가능한 백업 목록:" >&2
  find "$BASE_DATA_DIR/backups" -mindepth 1 -maxdepth 1 -type d -printf '  %f\n' 2>/dev/null | sort >&2
  exit 1
fi

if [ -f "$BACKUP_DIR/manifest.json" ]; then
  echo ">> 백업 정보 ($BACKUP_DIR/manifest.json):"
  cat "$BACKUP_DIR/manifest.json"
  echo
fi

if [ "$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null || echo false)" != "true" ]; then
  echo "[오류] $DB_CONTAINER 컨테이너가 실행 중이 아닙니다." >&2
  exit 1
fi

CURRENT_ACCOUNTS=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" \
  -e "SELECT COUNT(*) FROM account;" acore_auth 2>/dev/null | tr -d '\r' || echo 0)

if [ "${CURRENT_ACCOUNTS:-0}" -gt 0 ] && [ "$FORCE" -ne 1 ]; then
  echo "[오류] 대상 DB에 이미 계정이 ${CURRENT_ACCOUNTS}개 있습니다." >&2
  echo "       이 복원은 병합이 아니라 덮어쓰기라서 지금 있는 데이터가 사라집니다." >&2
  echo "       베이스라인으로 초기화한 뒤 복원하거나(reset.sh, 추후 제공),"
  echo "       정말 덮어써야 한다면 --force를 붙여 다시 실행하세요." >&2
  exit 1
fi

if [ "$ASSUME_YES" -ne 1 ]; then
  echo ">> $BACKUP_ID 백업을 $DB_CONTAINER(acore_auth, acore_characters)에 복원합니다."
  echo ">> 현재 계정 수: ${CURRENT_ACCOUNTS:-0}개 (복원 후 백업 시점 데이터로 대체됨)"
  read -r -p ">> 계속하려면 RESTORE 를 입력하세요: " CONFIRM
  if [ "$CONFIRM" != "RESTORE" ]; then
    echo ">> 취소되었습니다."
    exit 1
  fi
fi

echo ">> worldserver/authserver를 잠시 멈춥니다 (복원 중 접속 방지)..."
docker compose stop ac-worldserver ac-authserver 2>/dev/null || true

echo ">> acore_auth 복원 중..."
gunzip -c "$AUTH_DUMP" | docker exec -i "$DB_CONTAINER" mysql -u"$DB_USER" -p"$DB_PASS" acore_auth

echo ">> acore_characters 복원 중..."
gunzip -c "$CHAR_DUMP" | docker exec -i "$DB_CONTAINER" mysql -u"$DB_USER" -p"$DB_PASS" acore_characters

NEW_ACCOUNTS=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" \
  -e "SELECT COUNT(*) FROM account;" acore_auth 2>/dev/null | tr -d '\r' || echo 0)
NEW_CHARACTERS=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" \
  -e "SELECT COUNT(*) FROM characters;" acore_characters 2>/dev/null | tr -d '\r' || echo 0)

echo ">> 복원 완료: 계정 ${NEW_ACCOUNTS}개, 캐릭터 ${NEW_CHARACTERS}개"

echo ">> worldserver/authserver 재시작..."
docker compose start ac-worldserver ac-authserver 2>/dev/null || true

echo ">> 완료."
