#!/bin/sh
set -e
DEST="/azerothcore/env/dist/data/dbc"
mkdir -p "$DEST"
COUNT=$(find /patch/dbc -maxdepth 1 -iname '*.dbc' | wc -l)
echo ">> Applying Korean DBC patch (${COUNT} files) into ${DEST} ..."
cp -f /patch/dbc/*.dbc "$DEST"/
cp -f /patch/dbc/component.wow-koKR.txt "$DEST"/ 2>/dev/null || true
echo ">> Korean DBC patch applied successfully."
