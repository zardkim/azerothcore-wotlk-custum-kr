#!/usr/bin/env bash
#
# restore.sh — backup.sh가 만든 실제 플레이어 계정/캐릭터 백업(봇 계정 제외)을
# 되살린다. 대상 DB에 이미 있는 "실제 계정"(봇 계정 제외) 관련 데이터는 먼저
# 전부 삭제한 뒤 백업 내용을 가져온다 - 병합이 아니라 교체다. 봇 계정/데이터는
# 이 스크립트가 아예 건드리지 않는다(백업 대상도 아니었으므로).
#
# 사용법: ./restore.sh <backup_id> [--force] [--yes]
#   <backup_id>  backups/ 아래 폴더 이름 (예: 20260915-140000). ls로 확인.
#   --force      대상 DB에 이미 실제 계정이 있어도 강제로 덮어쓴다 (위험 — 지금 데이터가 사라짐).
#   --yes        확인 프롬프트를 건너뛴다 (스크립트/cron에서 호출할 때만 사용).
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # deploy/ 로 이동 (compose/.env 기준)

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
BOT_PREFIX="${BOT_PREFIX:-rndbot}"

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

# shellcheck source=lib/player-tables.sh
source "$SCRIPT_DIR/lib/player-tables.sh"

MYSQL_CMD="mysql -N -B -u$DB_USER -p$DB_PASS --default-character-set=utf8mb4"

CURRENT_ACCOUNTS=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 \
  -e "SELECT COUNT(*) FROM account WHERE username NOT LIKE '${BOT_PREFIX}%';" acore_auth 2>/dev/null | tr -d '\r' || echo 0)

if [ "${CURRENT_ACCOUNTS:-0}" -gt 0 ] && [ "$FORCE" -ne 1 ]; then
  echo "[오류] 대상 DB에 이미 실제 계정이 ${CURRENT_ACCOUNTS}개 있습니다 (봇 계정 제외)." >&2
  echo "       이 복원은 병합이 아니라 교체라서 지금 있는 실제 계정 데이터가 사라집니다." >&2
  echo "       베이스라인으로 초기화한 뒤 복원하거나(reset.sh), 정말 덮어써야 한다면" >&2
  echo "       --force를 붙여 다시 실행하세요." >&2
  exit 1
fi

if [ "$ASSUME_YES" -ne 1 ]; then
  echo ">> $BACKUP_ID 백업을 $DB_CONTAINER(실제 계정/캐릭터만, 봇 제외)에 복원합니다."
  echo ">> 현재 실제 계정 수: ${CURRENT_ACCOUNTS:-0}개 (복원 후 백업 시점 데이터로 대체됨, 봇 계정은 그대로 유지)"
  read -r -p ">> 계속하려면 RESTORE 를 입력하세요: " CONFIRM
  if [ "$CONFIRM" != "RESTORE" ]; then
    echo ">> 취소되었습니다."
    exit 1
  fi
fi

echo ">> worldserver/authserver를 잠시 멈춥니다 (복원 중 접속 방지)..."
docker compose stop ac-worldserver ac-authserver 2>/dev/null || true

ACCOUNT_WHERE=$(resolve_player_where '{ACCOUNT_SQL}' "$BOT_PREFIX")

# ---- 1) 대상 DB에 이미 있는 실제 계정 관련 데이터를 먼저 삭제 (교체를 위한 정리) ----
echo ">> 기존 실제 계정 데이터 삭제 중 (봇 계정은 건드리지 않음)..."
delete_script="set -e
"
for entry in "${PLAYER_CHAR_TABLES[@]}"; do
  table="${entry%%|*}"
  where_tpl="${entry#*|}"
  where=$(resolve_player_where "$where_tpl" "$BOT_PREFIX")
  # 원격 sh가 -e 인자(큰따옴표)를 파싱할 때 backtick을 커맨드 치환으로 취급하지
  # 않도록, 이스케이프된 backtick(\`)을 "값"으로 안전하게 만든다 - 작은따옴표
  # 안에서 만들면 bash 쪽 backtick/이스케이프 해석 자체를 피할 수 있다(groups는
  # MySQL 예약어라 반드시 식별자를 감싸야 함).
  qtable='\`'"$table"'\`'
  delete_script="${delete_script}if $MYSQL_CMD -e \"SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='acore_characters' AND TABLE_NAME='$table'\" 2>/dev/null | grep -q 1; then
  $MYSQL_CMD -e \"SET FOREIGN_KEY_CHECKS=0; DELETE FROM $qtable WHERE $where;\" acore_characters
fi
"
done
printf '%s' "$delete_script" | docker exec -i "$DB_CONTAINER" sh -s

auth_delete_script="set -e
$MYSQL_CMD -e \"SET FOREIGN_KEY_CHECKS=0; DELETE FROM account_access WHERE id IN ($ACCOUNT_WHERE); DELETE FROM account_banned WHERE id IN ($ACCOUNT_WHERE);\" acore_auth
if $MYSQL_CMD -e \"SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='acore_auth' AND TABLE_NAME='account_muted'\" 2>/dev/null | grep -q 1; then
  $MYSQL_CMD -e \"SET FOREIGN_KEY_CHECKS=0; DELETE FROM account_muted WHERE guid IN ($ACCOUNT_WHERE);\" acore_auth
fi
$MYSQL_CMD -e \"SET FOREIGN_KEY_CHECKS=0; DELETE FROM account WHERE username NOT LIKE '${BOT_PREFIX}%';\" acore_auth
"
printf '%s' "$auth_delete_script" | docker exec -i "$DB_CONTAINER" sh -s

# ---- 2) 백업 내용 복원 ----
echo ">> acore_auth 복원 중..."
gunzip -c "$AUTH_DUMP" | docker exec -i "$DB_CONTAINER" mysql -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 --binary-mode=1 acore_auth

echo ">> acore_characters 복원 중..."
gunzip -c "$CHAR_DUMP" | docker exec -i "$DB_CONTAINER" mysql -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 --binary-mode=1 acore_characters

NEW_ACCOUNTS=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 \
  -e "SELECT COUNT(*) FROM account WHERE username NOT LIKE '${BOT_PREFIX}%';" acore_auth 2>/dev/null | tr -d '\r' || echo 0)
NEW_CHARACTERS=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 \
  -e "SELECT COUNT(*) FROM characters WHERE account IN (SELECT id FROM acore_auth.account WHERE username NOT LIKE '${BOT_PREFIX}%');" \
  acore_characters 2>/dev/null | tr -d '\r' || echo 0)

echo ">> 복원 완료: 실제 계정 ${NEW_ACCOUNTS}개, 캐릭터 ${NEW_CHARACTERS}개 (봇 계정은 변경 없음)"

echo ">> worldserver/authserver 재시작..."
docker compose start ac-worldserver ac-authserver 2>/dev/null || true

echo ">> 완료."
