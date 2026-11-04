#!/bin/bash
# farglow-backupd: once a day at FARGLOW_BACKUP_HOUR (UTC), pg_dump -Fc into
# /backups/nightly/farglow-YYYYMMDD.dump, keeping FARGLOW_BACKUP_KEEP days.
# Copy them to the host with:  docker compose cp backup:/backups/nightly ./backups/
set -uo pipefail

HOUR="${FARGLOW_BACKUP_HOUR:-03}"
KEEP="${FARGLOW_BACKUP_KEEP:-7}"
DIR=/backups/nightly
HEARTBEAT=/tmp/farglow-heartbeat
export PGHOST="${PGHOST:-db}" PGDATABASE="${PGDATABASE:-farglow}" PGUSER="${PGUSER:-farglow}"

log() { printf '{"ts":"%s","level":"%s","service":"backup","msg":"%s"}\n' "$(date -u +%FT%TZ)" "$1" "$2"; }

stop=0
trap 'stop=1' TERM INT

mkdir -p "$DIR"
log INFO "backup daemon started (nightly at ${HOUR}:00 UTC, keep ${KEEP})"
while [[ $stop -eq 0 ]]; do
    date +%s > "$HEARTBEAT"
    psql -qAtc "INSERT INTO service_heartbeats (service, instance, version, seen_at)
                VALUES ('backup', '$(hostname)', '${FARGLOW_BUILD:-unknown}', now())
                ON CONFLICT (service, instance) DO UPDATE SET seen_at = now(), version = EXCLUDED.version" \
        >/dev/null 2>&1 || true
    today="$(date -u +%Y%m%d)"
    if [[ "$(date -u +%H)" == "$HOUR" && ! -f "$DIR/farglow-$today.dump" ]]; then
        if pg_dump -Fc -f "$DIR/.farglow-$today.dump.tmp"; then
            mv "$DIR/.farglow-$today.dump.tmp" "$DIR/farglow-$today.dump"
            log INFO "nightly backup written: farglow-$today.dump"
            # keep the newest $KEEP
            find "$DIR" -maxdepth 1 -name 'farglow-*.dump' -printf '%f\n' | sort -r | tail -n +"$((KEEP + 1))" \
                | while read -r old; do rm -f -- "${DIR:?}/$old"; log INFO "pruned $old"; done
        else
            rm -f "$DIR/.farglow-$today.dump.tmp"
            log ERROR "nightly pg_dump failed"
        fi
    fi
    for _ in $(seq 1 30); do [[ $stop -eq 1 ]] && break; sleep 2; done
done
log INFO "backup daemon stopped"
