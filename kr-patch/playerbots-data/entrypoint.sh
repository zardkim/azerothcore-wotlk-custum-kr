#!/bin/sh
set -e
DEST="/azerothcore/source/azerothCore/modules/mod-playerbots/data/sql/playerbots"
mkdir -p "$DEST"
if [ -d "$DEST/base" ] && [ -n "$(ls -A "$DEST/base" 2>/dev/null)" ]; then
  echo ">> ${DEST} 에 이미 데이터가 있어 건너뜁니다 (재복사 안 함)."
else
  echo ">> Populating mod-playerbots custom SQL data into ${DEST} ..."
  cp -r /patch/playerbots/. "$DEST"/
  echo ">> Done."
fi
