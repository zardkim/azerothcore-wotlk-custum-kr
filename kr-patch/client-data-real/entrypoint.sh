#!/bin/sh
set -e
DEST="/azerothcore/env/dist/data"
mkdir -p "$DEST"
if [ -d "$DEST/maps" ] && [ -n "$(ls -A "$DEST/maps" 2>/dev/null)" ]; then
  echo ">> ${DEST} 에 이미 데이터가 있어 건너뜁니다 (재복사 안 함)."
else
  echo ">> Populating real extracted client data (maps/vmaps/mmaps/dbc incl. koKR) into ${DEST} ..."
  cp -r /source/data/. "$DEST"/
  echo ">> Done."
fi
