#!/bin/sh
set -e
DEST="/azerothcore/env/dist/etc"
mkdir -p "$DEST"
echo ">> Populating env/dist/etc (worldserver.conf, authserver.conf, dbimport.conf, 65개 모듈 conf) into ${DEST} ..."
cp -rn /patch/etc/. "$DEST"/
echo ">> Done."
