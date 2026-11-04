#!/bin/bash
###############################################################################
# ui-test.sh - the headless-browser UI suite: plays the game and checks every screen
#
#   tests/ui/ui-test.sh                 build, install an isolated stack (project farglow-ui,
#                                       port 18090, development mode, no SMTP), run, remove it
#   tests/ui/ui-test.sh --url URL       run against a running server instead (it signs up a
#                                       test player there: the server needs no SMTP, or the
#                                       play-through stops at email verification)
#   tests/ui/ui-test.sh --keep          leave the isolated stack running afterwards
#   tests/ui/ui-test.sh --viewports 1366x768,1920x1080 --themes light,dark --ticks 4
#
# Report: test-reports/ui/<UTC time>/report.html (+ summary.json, screenshots). Exit 1 if
# anything FAILed. Also run by ./test.sh --ui. Checks and budgets: tests/ui/uitest.py and
# tests/ui/budgets.json; see TESTING.md "UI suite".
###############################################################################
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=scripts/lib/common.sh
source "$ROOT/scripts/lib/common.sh"

URL="" KEEP=0 PASS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --url) URL="${2:?--url needs a value}"; shift ;;
        --keep) KEEP=1 ;;
        --viewports|--themes|--ticks) PASS+=("$1" "${2:?$1 needs a value}"); shift ;;
        -h|--help) print_usage "$0"; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done
require_docker

RUN_ID="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="$ROOT/test-reports/ui/$RUN_ID"
mkdir -p "$OUT"
chmod 777 "$OUT"             # the runner writes as its own user (pwuser)

info "building the UI test runner (tests/ui)"
secret=()
[[ -n "${FARGLOW_BUILD_CA_FILE:-}" ]] && secret=(--secret "id=build_ca,src=$FARGLOW_BUILD_CA_FILE")
docker buildx build -q --load "${secret[@]}" -t farglow-uitest:local "$ROOT/tests/ui" >/dev/null

WORK=""
if [[ -z "$URL" ]]; then
    WORK="$(mktemp -d)"
    export FARGLOW_COMPOSE_PROJECT=farglow-ui FARGLOW_ENV_FILE="$WORK/ui.env"
    export FARGLOW_PROJECT=farglow-ui FARGLOW_ENV="$WORK/ui.env"
    export FARGLOW_ADMIN_EMAIL=ui-admin@example.test FARGLOW_DOMAIN=localhost FARGLOW_BIND=127.0.0.1
    export FARGLOW_HTTP_PORT=18090 FARGLOW_HTTPS_PORT=18453 FARGLOW_DEBUG=true FARGLOW_TICK_SECONDS=300
    export FARGLOW_TLS_DIR="$WORK/tls" FARGLOW_ASSUME_YES=1
    cleanup() {
        if [[ $KEEP == 0 ]]; then "$ROOT/uninstall.sh" --purge --yes --no-backup >/dev/null 2>&1 || true; rm -rf "$WORK"
        else info "stack kept: http://127.0.0.1:18090 (remove: FARGLOW_COMPOSE_PROJECT=farglow-ui FARGLOW_ENV_FILE=$WORK/ui.env ./uninstall.sh --purge)"; fi
    }
    trap cleanup EXIT
    info "building images and installing an isolated stack on port 18090"
    "$ROOT/build.sh" --local >/dev/null
    "$ROOT/install.sh" --non-interactive --source local --skip-mail-test >/dev/null
    URL="http://127.0.0.1:18090"
    EMAIL=(--email ui-admin@example.test)      # the host admin: the admin screen is checked too
else
    EMAIL=()
fi

info "running the UI suite against $URL"
rc=0
docker run --rm --network host --shm-size 1g -v "$OUT:/reports" farglow-uitest:local \
    --url "$URL" --out /reports "${EMAIL[@]}" "${PASS[@]}" || rc=$?
echo "   report: $OUT/report.html"
exit $rc
