#!/usr/bin/env bash
#
# apply-update.sh — 새로 빌드/푸시된 이미지(worldserver/authserver/db-import)를
# 라이브 서버에 반영한다: 백업 -> pull -> db-import(해시 기반 증분 SQL 반영, 계정/
# 캐릭터 보존) -> worldserver/authserver 교체 재기동.
# (.agents/plans/ops-backup-reset-update/ops-backup-reset-update.PLAN.md 3.2절 절차)
#
# 전제: harbor에 이미 새 버전 이미지가 push돼 있어야 한다 (이 스크립트는 이미지를
# 빌드하지 않는다 — 코어/모듈 재컴파일은 build4.log에서 검증된 기존 파이프라인 사용).
#
# 사용법: ./apply-update.sh [--yes]
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.."   # deploy/ 로 이동 (compose/.env 기준)

ASSUME_YES=0
for arg in "$@"; do
  case "$arg" in
    --yes) ASSUME_YES=1 ;;
    *) echo "[오류] 알 수 없는 옵션: $arg" >&2; exit 1 ;;
  esac
done

if [ ! -f .env ]; then
  echo "[오류] .env 파일이 없습니다." >&2
  exit 1
fi

if [ "$ASSUME_YES" -ne 1 ]; then
  echo "########################################################################"
  echo "  코어/모듈 업데이트 적용"
  echo "  1) 계정/캐릭터 백업  2) 새 이미지 pull  3) 신규 모듈 기본 설정 배치"
  echo "  4) DB에 증분 SQL 반영(dbimport)  5) worldserver/authserver 교체 재기동"
  echo "  dbimport는 해시 기반으로 이미 적용된 SQL은 건너뛰므로 계정/캐릭터/기존"
  echo "  게임 콘텐츠를 덮어쓰지 않습니다 — 그래도 만약을 위해 먼저 백업합니다."
  echo "  기존 설정 파일도 건드리지 않고, 새로 추가된 모듈의 기본 설정만 배치합니다."
  echo "########################################################################"
  read -r -p ">> 계속하려면 UPDATE를 입력하세요: " CONFIRM
  if [ "$CONFIRM" != "UPDATE" ]; then
    echo ">> 취소되었습니다."
    exit 1
  fi
fi

echo ">> [1/5] 업데이트 적용 전 계정/캐릭터 백업 중..."
./scripts/backup.sh

echo ">> [2/5] 새 이미지 pull 중..."
docker compose pull

echo ">> [3/5] 새로 추가된 모듈의 기본 설정 파일 배치 중 (기존 설정은 그대로 보존)..."
# shellcheck source=lib/sync-configs.sh
source "$SCRIPT_DIR/lib/sync-configs.sh"
BASE_DATA_DIR=$(grep -E '^BASE_DATA_DIR=' .env | tail -1 | cut -d= -f2-)
sync_new_configs "$BASE_DATA_DIR" "configs"

echo ">> [4/5] DB에 증분 SQL 반영 중 (ac-db-import)..."
docker compose up --exit-code-from ac-db-import ac-db-import

echo ">> [5/5] worldserver/authserver 등을 새 이미지로 교체 재기동..."
docker compose up -d

echo ">> 완료. 로그 확인: docker compose logs -f ac-worldserver ac-authserver"
