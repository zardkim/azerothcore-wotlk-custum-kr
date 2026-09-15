#!/usr/bin/env bash
# BASE_DATA_DIR 아래에 필요한 모든 하위 폴더를 미리 만들고,
# configs/ 초기 내용을 복사해둔다. docker compose up 전에 한 번만 실행.
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [ ! -f .env ]; then
  echo "[오류] .env 파일이 없습니다. 먼저 실행하세요: cp .env.example .env"
  exit 1
fi

BASE_DATA_DIR=$(grep -E '^BASE_DATA_DIR=' .env | tail -1 | cut -d= -f2-)

if [ -z "${BASE_DATA_DIR:-}" ]; then
  echo "[오류] .env에 BASE_DATA_DIR이 설정되어 있지 않습니다."
  exit 1
fi

echo ">> 기준 경로: $BASE_DATA_DIR"

mkdir -p "$BASE_DATA_DIR/data/playbots"
mkdir -p "$BASE_DATA_DIR/mysql"
mkdir -p "$BASE_DATA_DIR/logs"
mkdir -p "$BASE_DATA_DIR/web-data"
mkdir -p "$BASE_DATA_DIR/backups"
echo ">> data/, data/playbots/, mysql/, logs/, web-data/, backups/ 폴더 준비 완료"

if [ -d "$BASE_DATA_DIR/configs" ]; then
  echo ">> configs/ 폴더가 이미 있어 건너뜁니다 (기존 설정 보존)"
else
  cp -r configs "$BASE_DATA_DIR/"
  echo ">> configs/ 폴더 복사 완료"
fi

echo
echo ">> 준비 완료. 이제 다음을 실행하세요:"
echo "     docker compose pull"
echo "     docker compose up -d"
