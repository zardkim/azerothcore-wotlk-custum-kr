#!/bin/bash
set -e
: "${DB_HOST:=ac-database}"
: "${DB_PORT:=3306}"
: "${DB_USER:=root}"
: "${DB_PASSWORD:?DB_PASSWORD environment variable is required}"

echo ">> Waiting for MySQL at ${DB_HOST}:${DB_PORT} ..."
until mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" -e "SELECT 1" >/dev/null 2>&1; do
  sleep 2
done
echo ">> MySQL is reachable."

for f in /patch/sql/*.sql; do
  name=$(basename "$f")
  echo ">> Applying ${name} ..."
  mysql -h"$DB_HOST" -P"$DB_PORT" -u"$DB_USER" -p"$DB_PASSWORD" < "$f"
  echo ">> ${name} applied."
done

echo ">> Korean SQL patch (01~06) complete."
