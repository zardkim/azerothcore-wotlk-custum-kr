FROM mysql:8.4
LABEL org.opencontainers.image.authors="zardkim" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.title="AzerothCore Playerbot Database (KR)" \
      org.opencontainers.image.description="65 AzerothCore modules + Korean localization SQL(01-06) pre-applied MySQL data. Auto-seeds an empty bind-mounted /var/lib/mysql on first start, then starts mysqld normally."

# 실제 마운트 지점(/var/lib/mysql)이 아닌 별도 seed 경로에 구운 데이터를 둔다.
# -> 사용자가 /var/lib/mysql을 폴더로 바인드 마운트해도 이 데이터가 가려지지 않고,
#    컨테이너 시작 시 비어있으면 여기서 복사해 넣는다 (1컨테이너로 통합).
ADD mysql-data.tar.gz /var-lib-mysql-seed/
RUN chown -R mysql:mysql /var-lib-mysql-seed && chmod 750 /var-lib-mysql-seed

COPY entrypoint-wrapper.sh /usr/local/bin/entrypoint-wrapper.sh
RUN chmod +x /usr/local/bin/entrypoint-wrapper.sh

ENTRYPOINT ["entrypoint-wrapper.sh"]
CMD ["mysqld"]
