#!/usr/bin/env bash
#
# backup.sh — 봇 계정(기본 접두어 rndbot)을 제외한 실제 플레이어 계정/캐릭터만
# 백업한다. acore_auth/acore_characters 전체를 통째로 덤프하지 않는다 — 이
# 프로젝트는 개인/소규모 운영이 목적이라, 수만 개의 봇 계정까지 매번 백업하는
# 무거운 방식은 낭비다. 코어/모듈 업데이트 전후로 실제 플레이어 진행 상황만
# 보존하면 충분하고, 봇은 재시작하면 mod-playerbots가 알아서 다시 만든다.
#
# acore_playerbots(봇 AI 상태), acore_world(게임 콘텐츠)는 원래도 백업 대상이
# 아니다 (.agents/plans/ops-backup-reset-update/ops-backup-reset-update.PLAN.md
# 참고). Windows 리팩용 계정 이관 도구(acore_migration V12)의 테이블 목록·
# 문자셋(utf8mb4) 강제 방식을 Docker/bash 환경에 맞게 옮겼다.
#
# 사용법: ./backup.sh
#         BACKUP_KEEP=30 ./backup.sh     (보관 개수 조절, 기본 14)
#         BOT_PREFIX=rndbot ./backup.sh  (봇 계정 접두어가 다르면 지정, 기본 rndbot —
#                                          playerbots.conf의 AiPlayerbot.RandomBotAccountPrefix와 맞출 것)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # deploy/ 로 이동 (compose/.env 기준)

if [ ! -f .env ]; then
  echo "[오류] .env 파일이 없습니다. 먼저 실행하세요: cp .env.example .env" >&2
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
BACKUP_KEEP="${BACKUP_KEEP:-14}"
BOT_PREFIX="${BOT_PREFIX:-rndbot}"

if [ "$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null || echo false)" != "true" ]; then
  echo "[오류] $DB_CONTAINER 컨테이너가 실행 중이 아닙니다. 'docker compose up -d ac-database'로 먼저 띄우세요." >&2
  exit 1
fi

# shellcheck source=lib/player-tables.sh
source "$SCRIPT_DIR/lib/player-tables.sh"

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="$BASE_DATA_DIR/backups"
BACKUP_DIR="$BACKUP_ROOT/$TS"
mkdir -p "$BACKUP_DIR"

echo ">> 백업 시작 (봇 계정 '${BOT_PREFIX}*' 제외): $BACKUP_DIR"

DUMP_CMD="mysqldump -u$DB_USER -p$DB_PASS --default-character-set=utf8mb4 --set-charset --single-transaction --no-tablespaces --no-create-info --complete-insert --skip-triggers"
MYSQL_CMD="mysql -N -B -u$DB_USER -p$DB_PASS --default-character-set=utf8mb4"
ACCOUNT_WHERE=$(resolve_player_where '{ACCOUNT_SQL}' "$BOT_PREFIX")

AUTH_OUT="$BACKUP_DIR/acore_auth.sql"
CHAR_OUT="$BACKUP_DIR/acore_characters.sql"

# ---- acore_auth: account / account_access / account_banned / (있으면) account_muted ----
auth_script="set -e
echo 'SET NAMES utf8mb4;'
echo 'SET FOREIGN_KEY_CHECKS=0;'
$DUMP_CMD --where=\"username NOT LIKE '${BOT_PREFIX}%'\" acore_auth account
$DUMP_CMD --where=\"id IN ($ACCOUNT_WHERE)\" acore_auth account_access
$DUMP_CMD --where=\"id IN ($ACCOUNT_WHERE)\" acore_auth account_banned
if $MYSQL_CMD -e \"SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='acore_auth' AND TABLE_NAME='account_muted'\" 2>/dev/null | grep -q 1; then
  $DUMP_CMD --where=\"guid IN ($ACCOUNT_WHERE)\" acore_auth account_muted
fi
echo 'SET FOREIGN_KEY_CHECKS=1;'
"
printf '%s' "$auth_script" | docker exec -i "$DB_CONTAINER" sh -s > "$AUTH_OUT"

# ---- acore_characters: PLAYER_CHAR_TABLES 목록 전부, 존재하는 테이블만 ----
char_script="set -e
echo 'SET NAMES utf8mb4;'
echo 'SET FOREIGN_KEY_CHECKS=0;'
"
for entry in "${PLAYER_CHAR_TABLES[@]}"; do
  table="${entry%%|*}"
  where_tpl="${entry#*|}"
  where=$(resolve_player_where "$where_tpl" "$BOT_PREFIX")
  char_script="${char_script}if $MYSQL_CMD -e \"SELECT 1 FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_SCHEMA='acore_characters' AND TABLE_NAME='$table'\" 2>/dev/null | grep -q 1; then
  $DUMP_CMD --where=\"$where\" acore_characters $table
fi
"
done
char_script="${char_script}echo 'SET FOREIGN_KEY_CHECKS=1;'
"
printf '%s' "$char_script" | docker exec -i "$DB_CONTAINER" sh -s > "$CHAR_OUT"

gzip -f "$AUTH_OUT"
gzip -f "$CHAR_OUT"

ACCOUNT_COUNT=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 \
  -e "SELECT COUNT(*) FROM account WHERE username NOT LIKE '${BOT_PREFIX}%';" acore_auth 2>/dev/null | tr -d '\r')
CHARACTER_COUNT=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" --default-character-set=utf8mb4 \
  -e "SELECT COUNT(*) FROM characters WHERE account IN (SELECT id FROM acore_auth.account WHERE username NOT LIKE '${BOT_PREFIX}%');" \
  acore_characters 2>/dev/null | tr -d '\r')
DB_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$DB_CONTAINER" 2>/dev/null || echo "unknown")

cat > "$BACKUP_DIR/manifest.json" <<EOF
{
  "backup_id": "$TS",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "account_count": ${ACCOUNT_COUNT:-0},
  "character_count": ${CHARACTER_COUNT:-0},
  "bot_prefix_excluded": "$BOT_PREFIX",
  "excluded_databases": ["acore_playerbots", "acore_world"],
  "scope": "account/character 단위 선별 백업 (전체 DB 덤프 아님)",
  "db_image": "$DB_IMAGE",
  "files": {
    "acore_auth": "acore_auth.sql.gz",
    "acore_characters": "acore_characters.sql.gz"
  }
}
EOF

echo ">> 백업 완료: 실제 계정 ${ACCOUNT_COUNT:-0}개, 캐릭터 ${CHARACTER_COUNT:-0}개 (봇 제외)"
echo ">> 저장 위치: $BACKUP_DIR"

# 보관 정책: 오래된 백업부터 BACKUP_KEEP개를 넘는 만큼 삭제
mkdir -p "$BACKUP_ROOT"
mapfile -t ALL_BACKUPS < <(find "$BACKUP_ROOT" -mindepth 1 -maxdepth 1 -type d -printf '%f\n' | sort)
COUNT=${#ALL_BACKUPS[@]}
if [ "$COUNT" -gt "$BACKUP_KEEP" ]; then
  TO_DELETE=$((COUNT - BACKUP_KEEP))
  for i in $(seq 0 $((TO_DELETE - 1))); do
    OLD="${ALL_BACKUPS[$i]}"
    echo ">> 보관 개수($BACKUP_KEEP) 초과로 오래된 백업 삭제: $OLD"
    rm -rf "${BACKUP_ROOT:?}/${OLD:?}"
  done
fi
