#!/bin/bash
###############################################################################
# restore.sh - restore a backup made by backup.sh, then restart PAUSED
#
#   ./restore.sh backups/farglow-backup-<host>-T<tick>-<date>.tar.gz
#
# Options:
#   --with-secrets       also restore .env from the backup's encrypted secrets.env.enc
#                        (passphrase asked, or FARGLOW_BACKUP_PASSPHRASE). Needed on a new host.
#   --no-safety-backup   skip the safety backup of the current data (not recommended)
#   --yes                do not ask for confirmation
#   -h, --help           this help
#
# Steps: 1 verify the file (format, SHA-256 of every file, version not newer than this
# checkout) · 2 safety backup of the current data into backups/safety/ · 3 stop the game
# services · 4 replace the database with the dump · 5 run migrations · 6 check the restored
# tick and state hash against the manifest · 7 pause the engine and start everything.
# The engine stays paused until you resume it:
#     docker compose exec tick python -m farglow engine resume
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"
usage() { print_usage "$0"; }

FILE="" WITH_SECRETS=0 SAFETY=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --with-secrets) WITH_SECRETS=1 ;;
        --no-safety-backup) SAFETY=0 ;;
        --yes) export FARGLOW_ASSUME_YES=1 ;;
        -h|--help) usage; exit 0 ;;
        -*) die "unknown option: $1 (see --help)" ;;
        *) [[ -z "$FILE" ]] || die "only one backup file"; FILE="$1" ;;
    esac
    shift
done
[[ -n "$FILE" ]] || { usage; exit 2; }
[[ -f "$FILE" ]] || die "no such file: $FILE"
require_docker
require_cmd tar sha256sum

# ------------------------------------------------------------------ 1 verify
info "1/7 verifying $FILE"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
tar -tzf "$FILE" >/dev/null 2>&1 || die "not a readable .tar.gz"
# Refuse absolute paths or .. before extracting anything.
if tar -tzf "$FILE" | grep -qE '(^/|(^|/)\.\.(/|$))'; then die "unsafe paths in the archive"; fi
tar -C "$work" -xzf "$FILE" --no-same-owner
B="$work/farglow-backup"
[[ -f "$B/manifest.json" ]] || die "no manifest.json: not a Farglow backup"
mget() { sed -n "s/^  \"$1\": \"\{0,1\}\([^\",]*\)\"\{0,1\},\{0,1\}$/\1/p" "$B/manifest.json" | head -1; }
[[ "$(mget format)" == "farglow-backup/1" ]] || die "unsupported backup format '$(mget format)'"
bad=0
while IFS= read -r line; do
    f="$(sed -n 's/^ *"\(.*\)": "\([0-9a-f]\{64\}\)",\{0,1\}$/\1/p' <<< "$line")"
    h="$(sed -n 's/^ *"\(.*\)": "\([0-9a-f]\{64\}\)",\{0,1\}$/\2/p' <<< "$line")"
    [[ -z "$f" ]] && continue
    if [[ ! -f "$B/$f" ]] || [[ "$(sha256sum "$B/$f" | cut -d' ' -f1)" != "$h" ]]; then
        warn "checksum mismatch: $f"; bad=1
    fi
done < <(sed -n '/"files": {/,/}/p' "$B/manifest.json")
[[ $bad == 0 ]] || die "the backup is damaged (checksum mismatch)"
B_VERSION="$(mget farglow_version)" B_TICK="$(mget tick)" B_HASH="$(mget state_hash)" B_CREATED="$(mget created_at)"
HERE="$(farglow_version)"
newest="$(printf '%s\n%s\n' "$B_VERSION" "$HERE" | sort -V | tail -1)"
[[ "$newest" == "$HERE" ]] || die "this backup is from Farglow $B_VERSION, newer than this checkout ($HERE). Upgrade first."
ok "verified: Farglow $B_VERSION, tick $B_TICK, made $B_CREATED on $(mget host)"
if [[ $WITH_SECRETS == 1 && ! -f "$B/secrets.env.enc" ]]; then die "--with-secrets: this backup has no secrets (made without --with-secrets)"; fi
[[ $WITH_SECRETS == 0 && ! -f "$FARGLOW_ENV" ]] && die "no .env here: run ./install.sh first, or restore with --with-secrets"

echo
warn "This REPLACES ALL GAME DATA on this server with tick $B_TICK from $B_CREATED."
confirm "Continue?" n || die "cancelled"

# ------------------------------------------------------------------ 2 safety backup
if [[ $SAFETY == 1 && -n "$(compose ps -q db 2>/dev/null)" ]]; then
    info "2/7 safety backup of the current data"
    "$FARGLOW_ROOT/backup.sh" --output "$FARGLOW_ROOT/backups/safety/farglow-safety-$(date -u +%Y%m%dT%H%M%SZ).tar.gz" \
        || die "the safety backup failed; nothing was changed (use --no-safety-backup to skip it)"
else
    info "2/7 safety backup skipped"
fi

# ------------------------------------------------------------------ secrets
if [[ $WITH_SECRETS == 1 ]]; then
    require_cmd openssl
    pass="${FARGLOW_BACKUP_PASSPHRASE:-}"
    if [[ -z "$pass" ]]; then read -r -s -p "Backup passphrase: " pass; echo; fi
    FARGLOW_PASS="$pass" openssl enc -d -aes-256-cbc -pbkdf2 -iter 600000 \
        -in "$B/secrets.env.enc" -out "$work/env" -pass env:FARGLOW_PASS 2>/dev/null \
        || die "wrong passphrase (or damaged secrets)"
    [[ -f "$FARGLOW_ENV" ]] && cp -p "$FARGLOW_ENV" "$FARGLOW_ENV.pre-restore"
    install -m 600 "$work/env" "$FARGLOW_ENV"
    ok ".env restored from the backup (previous one kept as .env.pre-restore)"
fi
DB="$(env_get POSTGRES_DB)"; DB="${DB:-farglow}"
DBU="$(env_get POSTGRES_USER)"; DBU="${DBU:-farglow}"
psql_admin() { compose exec -T db psql -v ON_ERROR_STOP=1 -qAt -U "$DBU" -d postgres -c "$1"; }
psql_db()    { compose exec -T db psql -v ON_ERROR_STOP=1 -qAt -U "$DBU" -d "$DB" -c "$1"; }

# ------------------------------------------------------------------ 3 stop
info "3/7 stopping the game services (database stays up)"
compose stop "${FARGLOW_APP_SERVICES[@]}" >/dev/null 2>&1 || true
compose up -d db >/dev/null
wait_healthy 120 || die "the database did not become healthy"
if [[ $WITH_SECRETS == 1 ]]; then
    # The database cluster keeps the password it was created with; align it to the restored .env.
    pw="$(env_get POSTGRES_PASSWORD)"
    compose exec -T db psql -v ON_ERROR_STOP=1 -q -U "$DBU" -d postgres \
        -c "ALTER ROLE \"$DBU\" PASSWORD '${pw//\'/\'\'}'" >/dev/null
fi

# ------------------------------------------------------------------ 4 database
info "4/7 replacing the database"
psql_admin "DROP DATABASE IF EXISTS \"$DB\" WITH (FORCE)" >/dev/null
psql_admin "CREATE DATABASE \"$DB\" OWNER \"$DBU\"" >/dev/null
compose exec -T db pg_restore --exit-on-error --no-owner -U "$DBU" -d "$DB" < "$B/db.dump"

# ------------------------------------------------------------------ 5 migrate
info "5/7 running migrations"
compose run --rm --no-deps migrate >/dev/null

# ------------------------------------------------------------------ 6 check
info "6/7 checking the restored state"
read -r R_TICK R_HASH <<< "$(psql_db "SELECT tick, state_hash FROM engine_state" | tr '|' ' ')"
if [[ "$R_TICK" != "$B_TICK" || "$R_HASH" != "$B_HASH" ]]; then
    die "restored tick/hash ($R_TICK ${R_HASH:0:12}) differ from the manifest ($B_TICK ${B_HASH:0:12})"
fi
ok "tick $R_TICK, state hash ${R_HASH:0:16}… matches the backup"
if ! diff -rq "$B/config" "$FARGLOW_ROOT/config" >/dev/null 2>&1; then
    keep="$FARGLOW_ROOT/backups/restored-config-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$keep" && cp -R "$B/config/." "$keep/"
    warn "the backup's config/*.yaml differ from this checkout's; this checkout's are used. The backup's copy is in ${keep#"$FARGLOW_ROOT"/}"
fi

# ------------------------------------------------------------------ 7 pause + start
info "7/7 pausing the engine and starting everything"
psql_db "UPDATE engine_state SET paused = true, pause_reason = 'restored from backup (tick $B_TICK, $B_CREATED)', updated_at = now();
         INSERT INTO engine_events (tick, kind, detail)
         VALUES ($B_TICK, 'restore', jsonb_build_object('file', '$(basename "$FILE")', 'created_at', '$B_CREATED'))" >/dev/null
compose up -d >/dev/null 2>&1
wait_healthy 300 || die "services did not become healthy after the restore: docker compose ps"
compose exec -T tick python -m farglow engine verify || warn "replay check failed: see above"
ok "restore complete. The engine is PAUSED at tick $R_TICK. When ready:"
echo "     docker compose exec tick python -m farglow engine resume"
