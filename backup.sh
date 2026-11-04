#!/bin/bash
###############################################################################
# backup.sh - one portable backup file of this Farglow server
#
#   ./backup.sh                       backups/farglow-backup-<host>-T<tick>-<date>.tar.gz
#   ./backup.sh --with-secrets        also include .env, encrypted with a passphrase
#   ./backup.sh --output FILE         write to FILE instead
#
# Options:
#   --with-secrets   add secrets.env.enc (AES-256, PBKDF2 600k rounds, via openssl). The
#                    passphrase is asked twice, or read from FARGLOW_BACKUP_PASSPHRASE.
#   --output FILE    destination path (directories are created)
#   -h, --help       this help
#
# Contents: db.dump (pg_dump custom format, a consistent snapshot), config/, VERSION,
# manifest.json (version, git commit, tick, state hash, SHA-256 of every file). Without
# --with-secrets the file holds no passwords or keys; restoring it needs this server's
# .env (or a fresh ./install.sh). The game keeps running during a backup.
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"
usage() { print_usage "$0"; }

WITH_SECRETS=0 OUTPUT=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-secrets) WITH_SECRETS=1 ;;
        --output) [[ $# -ge 2 ]] || die "--output needs a path"; OUTPUT="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done

require_docker
require_cmd tar sha256sum
[[ -f "$FARGLOW_ENV" ]] || die "no .env: is Farglow installed here? (./install.sh)"
[[ -n "$(compose ps -q db 2>/dev/null)" ]] || die "the db service is not running (docker compose up -d db)"
DB="$(env_get POSTGRES_DB)"; DB="${DB:-farglow}"
DBU="$(env_get POSTGRES_USER)"; DBU="${DBU:-farglow}"

psql_q() { compose exec -T db psql -qAt -U "$DBU" -d "$DB" -c "$1"; }

passphrase=""
if [[ $WITH_SECRETS == 1 ]]; then
    require_cmd openssl
    passphrase="${FARGLOW_BACKUP_PASSPHRASE:-}"
    if [[ -z "$passphrase" ]]; then
        [[ -t 0 ]] || die "--with-secrets needs a terminal or FARGLOW_BACKUP_PASSPHRASE"
        read -r -s -p "Passphrase for the secrets (min 12 characters): " passphrase; echo
        read -r -s -p "Again: " p2; echo
        [[ "$passphrase" == "$p2" ]] || die "passphrases differ"
    fi
    (( ${#passphrase} >= 12 )) || die "the passphrase must be at least 12 characters"
fi

work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir -p "$work/farglow-backup"
B="$work/farglow-backup"

info "dumping the database"
# pg_dump is one consistent snapshot. The manifest's tick and hash are read before and
# after it; if a tick landed in between, dump again (ticks are minutes apart, so a retry
# always settles).
engine_row() { psql_q "SELECT tick, state_hash, (SELECT max(version) FROM schema_migrations) FROM engine_state" | tr '|' ' '; }
for attempt in 1 2 3; do
    before="$(engine_row)"
    compose exec -T db pg_dump -Fc -U "$DBU" -d "$DB" > "$B/db.dump"
    after="$(engine_row)"
    [[ "$before" == "$after" ]] && break
    [[ $attempt == 3 ]] && die "the engine ticked during every attempt; pause it and retry"
    warn "a tick happened during the dump; dumping again"
done
[[ -s "$B/db.dump" ]] || die "pg_dump produced an empty file"
read -r TICK HASH SCHEMA <<< "$after"
TICK="${TICK:-0}"

cp -R "$FARGLOW_ROOT/config" "$B/config"
cp "$FARGLOW_ROOT/VERSION" "$B/VERSION"
if [[ $WITH_SECRETS == 1 ]]; then
    info "encrypting .env into the backup"
    FARGLOW_PASS="$passphrase" openssl enc -aes-256-cbc -pbkdf2 -iter 600000 -salt \
        -in "$FARGLOW_ENV" -out "$B/secrets.env.enc" -pass env:FARGLOW_PASS
fi

host="$(hostname -s 2>/dev/null || hostname)"
stamp="$(date -u +%Y%m%dT%H%M%SZ)"
(
    cd "$B"
    files_json="$(find . -type f ! -name manifest.json -printf '%P\n' | sort | while read -r f; do
        printf '    "%s": "%s",\n' "$f" "$(sha256sum "$f" | cut -d' ' -f1)"; done | sed '$ s/,$//')"
    cat > manifest.json <<JSON
{
  "format": "farglow-backup/1",
  "farglow_version": "$(farglow_version)",
  "git_commit": "$(farglow_git_rev)",
  "image_tag": "$(env_get FARGLOW_IMAGE_TAG)",
  "created_at": "$stamp",
  "host": "$host",
  "tick": $TICK,
  "state_hash": "${HASH:-}",
  "schema_version": ${SCHEMA:-0},
  "with_secrets": $([[ $WITH_SECRETS == 1 ]] && echo true || echo false),
  "files": {
$files_json
  }
}
JSON
)

OUTPUT="${OUTPUT:-$FARGLOW_ROOT/backups/farglow-backup-${host}-T${TICK}-${stamp}.tar.gz}"
mkdir -p "$(dirname "$OUTPUT")"
umask 077
tar -C "$work" -czf "$OUTPUT" farglow-backup
chmod 600 "$OUTPUT"
ok "backup written: $OUTPUT ($(du -h "$OUTPUT" | cut -f1), tick $TICK$([[ $WITH_SECRETS == 1 ]] && echo ', with encrypted secrets'))"
