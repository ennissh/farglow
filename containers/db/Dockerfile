# farglow-db: PostgreSQL 16, the single source of truth (game state and the job queue).
# Runs as the image's postgres user (uid 999), not root: the named volume inherits the
# data directory's ownership from the image. pg_isready is the health check (no Python here).
FROM postgres:16-bookworm@sha256:e8a07d2c7579b038938cdba6c539e580e5001caf9ea203d397b5cc83e76bd938

COPY containers/db/farglow.conf /etc/postgresql/farglow.conf
COPY containers/db/healthcheck.sh /usr/local/bin/farglow-healthcheck
RUN chmod 0755 /usr/local/bin/farglow-healthcheck \
    && chmod 0644 /etc/postgresql/farglow.conf \
    && mkdir -p /var/lib/postgresql/data \
    && chown -R postgres:postgres /var/lib/postgresql

USER postgres
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=6 \
    CMD ["/usr/local/bin/farglow-healthcheck"]
CMD ["postgres", "-c", "config_file=/etc/postgresql/farglow.conf"]

# Build metadata LAST: it changes on every build, so every layer above stays cached
# (build.sh also skips an image whose inputs are unchanged: scripts/inputs.py).
ARG FARGLOW_BUILD=0.0.0+local
ARG FARGLOW_REVISION=unknown
ARG FARGLOW_CREATED=unknown
ARG FARGLOW_INPUTS=unknown
LABEL org.opencontainers.image.title="farglow-db" \
      org.opencontainers.image.description="PostgreSQL 16 for Farglow" \
      org.opencontainers.image.version="${FARGLOW_BUILD}" \
      org.opencontainers.image.revision="${FARGLOW_REVISION}" \
      org.opencontainers.image.created="${FARGLOW_CREATED}" \
      org.opencontainers.image.source="https://github.com/ennissh/farglow" \
      org.opencontainers.image.vendor="Citus Technologies, LLC" \
      org.opencontainers.image.licenses="BUSL-1.1" \
      org.farglow.inputs="${FARGLOW_INPUTS}"
