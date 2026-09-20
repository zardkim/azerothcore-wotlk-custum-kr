#!/bin/sh
#
# kr-data-init.sh — 최초 설치 시에만 아래 두 압축파일을 나스 파일 공유에서 받아
# ${BASE_DATA_DIR}/data 에 풀어준다:
#   1) KR_DATA_URL (data.zip)              — Cameras/maps/mmaps/vmaps/dbc(기본)
#   2) KR_DBC_URL  (DBC 3.3.5a 12340.zip)  — 한글 DBC. dbc/ 바로 아래(서브폴더 아님)의
#      같은 파일명을 덮어써서 기본 dbc를 한글판으로 교체한다 — 반드시 1번 다음에 푼다.
#
# 이미 데이터가 있으면(이 스크립트로 설치됐든, 예전에 수동으로 넣어뒀든) 아무것도
# 하지 않고 즉시 끝난다 - 업데이트할 때마다 매번 확인하지 않는다.
#
# docker-compose.yml의 ac-kr-data-init 서비스에서 실행되며, /data 는
# ${BASE_DATA_DIR}/data 가 마운트된 것이다.
#
set -e

MARKER=/data/.kr-data-installed

if [ -f "$MARKER" ]; then
  echo ">> 이미 설치됨 (${MARKER} 존재) - 건너뜀"
  exit 0
fi

# 이 스크립트가 배포되기 전부터 이미 수동으로 data/를 채워둔 서버(지금 테스트/운영
# 중인 서버 포함)를 덮어쓰지 않는다 - dbc/ 폴더에 내용이 있으면 이미 설치된 것으로
# 보고 마커만 남긴다.
if [ -d /data/dbc ] && [ -n "$(ls -A /data/dbc 2>/dev/null)" ]; then
  echo ">> 기존 data/ 내용 감지 - 마커만 기록하고 건너뜀"
  touch "$MARKER"
  exit 0
fi

if [ -z "$KR_DATA_URL" ]; then
  echo "[오류] KR_DATA_URL이 설정되어 있지 않습니다 (.env 확인)." >&2
  exit 1
fi

echo ">> 필요한 도구 설치 중..."
apk add --no-cache unzip curl >/dev/null

download_and_verify() {
  # download_and_verify <url> <sha256(선택)> <출력경로>
  url="$1"; sha256="$2"; out="$3"
  echo ">> 다운로드 중: $url"
  curl -fL --retry 5 --retry-delay 5 -C - -o "$out" "$url"
  if [ -n "$sha256" ]; then
    echo ">> 체크섬 확인 중..."
    echo "$sha256  $out" | sha256sum -c -
  fi
}

DATA_ZIP=/tmp/kr-data.zip
download_and_verify "$KR_DATA_URL" "$KR_DATA_SHA256" "$DATA_ZIP"
echo ">> data.zip 압축 해제 중... (몇 분 걸릴 수 있습니다)"
unzip -oq "$DATA_ZIP" -d /data
rm -f "$DATA_ZIP"

if [ -n "$KR_DBC_URL" ]; then
  DBC_ZIP=/tmp/kr-dbc.zip
  download_and_verify "$KR_DBC_URL" "$KR_DBC_SHA256" "$DBC_ZIP"
  echo ">> 한글 DBC 압축 해제 중 (기본 dbc 위에 덮어씀)..."
  # 압축파일 안에 "dbc/" 폴더가 들어있는 구조(로컬 원본과 동일)이므로 /data 에 바로
  # 풀면 /data/dbc/ 아래 같은 파일명이 한글판으로 교체된다.
  unzip -oq "$DBC_ZIP" -d /data
  rm -f "$DBC_ZIP"
else
  echo ">> KR_DBC_URL이 비어 있어 한글 DBC는 건너뜁니다 (기본 dbc만 설치됨)."
fi

touch "$MARKER"
echo ">> 한글 DBC/data 설치 완료"
