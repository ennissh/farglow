#!/bin/bash
###############################################################################
# stack-test.sh - the Phase 0 round trip on real containers, isolated from any live server
#
# Project farglow-test, its own env file, ports 18080/18443, 5-second ticks:
#   build --local · install --non-interactive · wait for ticks · backup --with-secrets
#   · uninstall --purge (wipe) · install again (new secrets, new seed) · restore
#   --with-secrets · same tick and state hash, replay verified, engine paused · resume
#   ticks again · uninstall --purge.
# Run through ./test.sh --stack, or directly.
###############################################################################
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT/scripts/lib/common.sh"

WORK="$(mktemp -d)"
export FARGLOW_COMPOSE_PROJECT=farglow-test FARGLOW_ENV_FILE="$WORK/test.env"
export FARGLOW_PROJECT=farglow-test FARGLOW_ENV="$WORK/test.env"
export FARGLOW_ADMIN_EMAIL=stack-test@example.test FARGLOW_DOMAIN=localhost
export FARGLOW_HTTP_PORT=18080 FARGLOW_HTTPS_PORT=18443 FARGLOW_BIND=127.0.0.1
export FARGLOW_DEBUG=true FARGLOW_TICK_SECONDS=5 FARGLOW_TLS_DIR="$WORK/tls"
export FARGLOW_BACKUP_PASSPHRASE=stack-test-passphrase FARGLOW_ASSUME_YES=1
teardown() {
    "$ROOT/uninstall.sh" --purge --yes --no-backup >/dev/null 2>&1 || true
    rm -rf "$WORK"
}
trap teardown EXIT

hash_now() { compose exec -T tick python -m farglow engine hash; }
wait_tick() {  # wait_tick N : until the engine reaches tick >= N
    local n="$1"
    for _ in $(seq 1 60); do
        t="$(hash_now 2>/dev/null | cut -d' ' -f1)"; [[ -n "$t" && "$t" -ge "$n" ]] && return 0; sleep 2
    done
    die "engine did not reach tick $n"
}

info "stack: build"
"$ROOT/build.sh" --local >/dev/null
info "stack: install #1"
"$ROOT/install.sh" --non-interactive --source local --skip-mail-test >/dev/null
curl -fsS http://127.0.0.1:18080/readyz | grep -q '"ready"' || die "readyz not ready through nginx"
curl -fsS http://127.0.0.1:18080/ | grep -q "Galactic clock" || die "index page did not render"
wait_tick 3
compose exec -T tick python -m farglow engine pause --reason "stack test backup" >/dev/null
before="$(hash_now)"
info "stack: backup at tick ${before%% *}"
"$ROOT/backup.sh" --with-secrets --output "$WORK/b.tar.gz" >/dev/null
seed1="$(env_get FARGLOW_GALAXY_SEED)"

info "stack: wipe (uninstall --purge)"
"$ROOT/uninstall.sh" --purge --yes --no-backup >/dev/null
[[ ! -f "$FARGLOW_ENV" ]] || die ".env survived --purge"
docker volume inspect farglow-test_db-data >/dev/null 2>&1 && die "db volume survived --purge"

info "stack: install #2 (fresh secrets and seed)"
unset FARGLOW_GALAXY_SEED
"$ROOT/install.sh" --non-interactive --source local --skip-mail-test >/dev/null
[[ "$(env_get FARGLOW_GALAXY_SEED)" != "$seed1" ]] || die "fresh install reused the seed"

info "stack: restore --with-secrets"
"$ROOT/restore.sh" --yes --with-secrets "$WORK/b.tar.gz" >/dev/null
after="$(hash_now)"
[[ "$before" == "$after" ]] || die "state hash differs after restore: '$before' vs '$after'"
[[ "$(env_get FARGLOW_GALAXY_SEED)" == "$seed1" ]] || die "restored .env does not carry the original seed"
compose exec -T tick python -m farglow engine status | grep -q '"paused": true' || die "engine not paused after restore"
compose exec -T tick python -m farglow engine verify >/dev/null || die "replay verification failed after restore"
ok "restored tick and hash identical: ${after:0:30}…"

compose exec -T tick python -m farglow engine resume >/dev/null
wait_tick $(( ${after%% *} + 1 ))
compose exec -T tick python -m farglow engine verify >/dev/null || die "replay after resume failed"
ok "stack test passed"
