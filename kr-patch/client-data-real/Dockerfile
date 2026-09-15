FROM alpine:3.20
COPY kr-patch/client-data-real/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh
COPY data/ /source/data/
ENTRYPOINT ["/entrypoint.sh"]
