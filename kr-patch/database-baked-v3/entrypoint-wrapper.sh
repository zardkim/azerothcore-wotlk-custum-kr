#!/bin/bash
set -e

# ls -A 로 "비어있는지"를 판단하면 시놀로지가 자동 생성하는 @eaDir, #recycle 같은
# 시스템 폴더 때문에 "데이터 있음"으로 오판할 수 있다. 실제 MySQL 데이터 유무는
# ibdata1(진짜 초기화된 데이터 디렉터리에만 존재) 파일로만 판단한다.
if [ ! -f /var/lib/mysql/ibdata1 ]; then
  echo ">> 유효한 MySQL 데이터 없음 - 65개 모듈 + 한글화 SQL(01~06) 적용된 초기 데이터를 복사합니다..."
  # @eaDir, #recycle 등 시놀로지가 만든 잔여 파일이 있으면 mysqld --initialize가
  # "data directory has files in it"으로 거부하므로 복사 전에 비워둔다.
  find /var/lib/mysql -mindepth 1 -maxdepth 1 -exec rm -rf {} +
  cp -a /var-lib-mysql-seed/. /var/lib/mysql/
  echo ">> 복사 완료."
else
  echo ">> 기존 데이터 사용 (건너뜀)."
fi
exec docker-entrypoint.sh "$@"
