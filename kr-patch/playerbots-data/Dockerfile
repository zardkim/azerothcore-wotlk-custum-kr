FROM alpine:3.20
LABEL org.opencontainers.image.authors="zardkim" \
      org.opencontainers.image.version="1.0.0" \
      org.opencontainers.image.title="mod-playerbots Data Seed" \
      org.opencontainers.image.description="mod-playerbots custom SQL source tree, used to seed a bind-mounted folder so worldserver's own update-check finds it at startup."
COPY files/ /patch/playerbots/
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
ENTRYPOINT ["/entrypoint.sh"]
