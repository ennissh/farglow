# farglow-nginx: TLS, static files, reverse proxy to the api service.
# Based on nginx-unprivileged: runs as uid 101, listens on 8080/8443 (compose maps 80/443).
# Static files are baked in from farglow/web/static. Health check: busybox wget against
# 127.0.0.1 (part of the Alpine base; nothing is installed). Exception noted in CLAUDE.md.
FROM nginxinc/nginx-unprivileged:1.29-alpine@sha256:0c79d56aee561a1d81c63f00eee5fb5fe29279560cdc55e91425133104c7fbe6

ARG FARGLOW_BUILD=0.0.0+local
ARG FARGLOW_REVISION=unknown
ARG FARGLOW_CREATED=unknown
LABEL org.opencontainers.image.title="farglow-nginx" \
      org.opencontainers.image.description="TLS, static files and reverse proxy for Farglow" \
      org.opencontainers.image.version="${FARGLOW_BUILD}" \
      org.opencontainers.image.revision="${FARGLOW_REVISION}" \
      org.opencontainers.image.created="${FARGLOW_CREATED}" \
      org.opencontainers.image.source="https://github.com/ennissh/farglow" \
      org.opencontainers.image.vendor="Citus Technologies, LLC" \
      org.opencontainers.image.licenses="BUSL-1.1"

# The entrypoint renders /tmp/farglow-templates/*.template into conf.d (envsubst, FARGLOW_* only).
ENV NGINX_ENVSUBST_TEMPLATE_DIR=/tmp/farglow-templates \
    NGINX_ENVSUBST_FILTER=FARGLOW_ \
    FARGLOW_DOMAIN=localhost

COPY containers/nginx/templates/ /etc/farglow/nginx/
COPY containers/nginx/15-farglow-tls.sh /docker-entrypoint.d/15-farglow-tls.sh
COPY containers/nginx/healthcheck.sh /usr/local/bin/farglow-healthcheck
COPY farglow/web/static /usr/share/nginx/farglow/static
USER root
RUN chmod 0755 /docker-entrypoint.d/15-farglow-tls.sh /usr/local/bin/farglow-healthcheck \
    && rm -f /etc/nginx/conf.d/default.conf
USER 101

EXPOSE 8080 8443
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/usr/local/bin/farglow-healthcheck"]
