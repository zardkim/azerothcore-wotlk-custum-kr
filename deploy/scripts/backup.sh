#!/usr/bin/env bash
#
# backup.sh — acore_auth(계정) + acore_characters(캐릭터)만 백업한다.
# acore_playerbots(봇), acore_world(게임 콘텐츠)는 백업 대상이 아니다
# (.agents/plans/ops-backup-reset-update/ops-backup-reset-update.PLAN.md 1.2절 참고).
#
# 사용법: ./backup.sh   (deploy/.env의 BASE_DATA_DIR 아래 backups/<timestamp>/에 저장)
#         BACKUP_KEEP=30 ./backup.sh   (보관 개수 조절, 기본 14)
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."   # deploy/ 로 이동 (compose/.env 기준)

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

if [ "$(docker inspect -f '{{.State.Running}}' "$DB_CONTAINER" 2>/dev/null || echo false)" != "true" ]; then
  echo "[오류] $DB_CONTAINER 컨테이너가 실행 중이 아닙니다. 'docker compose up -d ac-database'로 먼저 띄우세요." >&2
  exit 1
fi

TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_ROOT="$BASE_DATA_DIR/backups"
BACKUP_DIR="$BACKUP_ROOT/$TS"
mkdir -p "$BACKUP_DIR"

echo ">> 백업 시작: $BACKUP_DIR"

echo ">> acore_auth 덤프 중..."
docker exec "$DB_CONTAINER" sh -c \
  "mysqldump -u$DB_USER -p$DB_PASS --single-transaction --no-tablespaces --routines --triggers acore_auth" \
  | gzip > "$BACKUP_DIR/acore_auth.sql.gz"

echo ">> acore_characters 덤프 중..."
docker exec "$DB_CONTAINER" sh -c \
  "mysqldump -u$DB_USER -p$DB_PASS --single-transaction --no-tablespaces --routines --triggers acore_characters" \
  | gzip > "$BACKUP_DIR/acore_characters.sql.gz"

ACCOUNT_COUNT=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" \
  -e "SELECT COUNT(*) FROM account;" acore_auth 2>/dev/null | tr -d '\r')
CHARACTER_COUNT=$(docker exec "$DB_CONTAINER" mysql -N -u"$DB_USER" -p"$DB_PASS" \
  -e "SELECT COUNT(*) FROM characters;" acore_characters 2>/dev/null | tr -d '\r')
DB_IMAGE=$(docker inspect -f '{{.Config.Image}}' "$DB_CONTAINER" 2>/dev/null || echo "unknown")

cat > "$BACKUP_DIR/manifest.json" <<EOF
{
  "backup_id": "$TS",
  "created_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "account_count": ${ACCOUNT_COUNT:-0},
  "character_count": ${CHARACTER_COUNT:-0},
  "excluded_databases": ["acore_playerbots", "acore_world"],
  "db_image": "$DB_IMAGE",
  "files": {
    "acore_auth": "acore_auth.sql.gz",
    "acore_characters": "acore_characters.sql.gz"
  }
}
EOF

echo ">> 백업 완료: 계정 ${ACCOUNT_COUNT:-0}개, 캐릭터 ${CHARACTER_COUNT:-0}개"
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
