# farglow-backup: nightly pg_dump of the database into the backups volume.
# Restore points every tick are written by the tick engine itself (restore_points table);
# full, portable backups are made on the host by ./backup.sh. Same PostgreSQL 16 base as
# farglow-db so pg_dump always matches the server. Runs as postgres (uid 999), not root.
FROM postgres:16-bookworm@sha256:e8a07d2c7579b038938cdba6c539e580e5001caf9ea203d397b5cc83e76bd938

ARG FARGLOW_BUILD=0.0.0+local
ARG FARGLOW_REVISION=unknown
ARG FARGLOW_CREATED=unknown
LABEL org.opencontainers.image.title="farglow-backup" \
      org.opencontainers.image.description="Nightly database backups for Farglow" \
      org.opencontainers.image.version="${FARGLOW_BUILD}" \
      org.opencontainers.image.revision="${FARGLOW_REVISION}" \
      org.opencontainers.image.created="${FARGLOW_CREATED}" \
      org.opencontainers.image.source="https://github.com/ennissh/farglow" \
      org.opencontainers.image.vendor="Citus Technologies, LLC" \
      org.opencontainers.image.licenses="BUSL-1.1"
ENV FARGLOW_BUILD=${FARGLOW_BUILD}

COPY containers/backup/backupd.sh /usr/local/bin/farglow-backupd
COPY containers/backup/healthcheck.sh /usr/local/bin/farglow-healthcheck
RUN chmod 0755 /usr/local/bin/farglow-backupd /usr/local/bin/farglow-healthcheck \
    && mkdir -p /backups/nightly \
    && chown -R postgres:postgres /backups

USER postgres
VOLUME ["/backups"]
HEALTHCHECK --interval=60s --timeout=5s --start-period=30s --retries=3 \
    CMD ["/usr/local/bin/farglow-healthcheck"]
ENTRYPOINT ["/usr/local/bin/farglow-backupd"]
