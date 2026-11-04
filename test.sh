#!/bin/bash
###############################################################################
# test.sh - Farglow layer-1 checks: everything that runs on a developer machine.
# There is no CI: ./build.sh --push refuses to push unless this passes.
#
#   ./test.sh            all checks + unit, determinism and database tests
#   ./test.sh --quick    skip the database tests (no Docker needed)
#   ./test.sh --stack    also run the stack test: build images, install an isolated copy
#                        (project farglow-test, ports 18080/18443), tick, backup, wipe,
#                        restore, compare the state hash, uninstall. Takes a few minutes.
#   ./test.sh -k EXPR    pass -k EXPR to pytest
#
# Checks, in order: shellcheck · Dockerfile contract · dependency pins · design tokens
# fresh · secrets (gitleaks) · CHANGELOG entry · Python compile · pytest (unit,
# determinism, db) · [stack]. Needs: bash, python3 with venv, git, shellcheck (the venv
# provides it via shellcheck-py), Docker for the db and stack tests.
###############################################################################
set -uo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"
usage() { print_usage "$0"; }

QUICK=0 STACK=0 PYTEST_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --quick) QUICK=1 ;;
        --stack) STACK=1 ;;
        -k) [[ $# -ge 2 ]] || die "-k needs an expression"; PYTEST_ARGS+=(-k "$2"); shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done
cd "$FARGLOW_ROOT" || exit 2

FAILED=()
step() {  # step NAME CMD... : run a check, record failure, keep going
    local name="$1"; shift
    printf '%s--- %s%s\n' "$C_DIM" "$name" "$C_RST"
    if "$@"; then ok "$name"; else FAILED+=("$name"); printf '%sFAIL%s %s\n' "$C_RED" "$C_RST" "$name"; fi
}

# ---- toolchain: a private venv keyed on requirements-dev.txt
VENV="$FARGLOW_ROOT/.venv-test"
stamp="$(sha256sum requirements-dev.txt | cut -c1-16)"
if [[ ! -f "$VENV/.stamp-$stamp" ]]; then
    info "preparing the test venv (.venv-test)"
    rm -rf "$VENV"
    python3 -m venv "$VENV" || die "python3 -m venv failed (Ubuntu: apt install python3-venv)"
    pipenv=()
    [[ -n "${FARGLOW_BUILD_CA_FILE:-}" ]] && pipenv=(env "PIP_CERT=$FARGLOW_BUILD_CA_FILE")
    "${pipenv[@]}" "$VENV/bin/pip" install -q --disable-pip-version-check -r requirements-dev.txt shellcheck-py==0.11.0.1 \
        || die "could not install the test toolchain"
    touch "$VENV/.stamp-$stamp"
fi
PY="$VENV/bin/python"
export PATH="$VENV/bin:$PATH"

mapfile -t SHELL_FILES < <(git ls-files --cached --others --exclude-standard '*.sh' | sort)
step "shellcheck" shellcheck -S warning -x "${SHELL_FILES[@]}"
step "dockerfile contract" "$PY" scripts/check-dockerfiles.py
step "dependency pins" "$PY" scripts/check-pins.py
step "design tokens fresh" "$PY" tools/design/build_tokens_css.py --check
step "secrets (gitleaks)" scripts/check-secrets.sh
step "changelog" "$PY" scripts/check-changelog.py
step "python compile" "$PY" -m compileall -q farglow tools scripts tests

# ---- pytest: unit + determinism always; db tests on a throwaway PostgreSQL 16
PG_CID=""
cleanup() { [[ -n "$PG_CID" ]] && docker rm -f "$PG_CID" >/dev/null 2>&1; }
trap cleanup EXIT
if [[ $QUICK == 0 ]]; then
    if docker info >/dev/null 2>&1; then
        pg_image="$(sed -n 's/^FROM \(postgres:[^ ]*\).*/\1/p' containers/db/Dockerfile | head -1)"
        PG_CID="$(docker run -d --rm -e POSTGRES_PASSWORD=test -p 127.0.0.1::5432 "$pg_image")" \
            || die "could not start the test database ($pg_image)"
        port="$(docker port "$PG_CID" 5432/tcp | head -1 | sed 's/.*://')"
        for _ in $(seq 1 60); do
            docker exec "$PG_CID" pg_isready -q -h 127.0.0.1 -U postgres 2>/dev/null && break
            sleep 1
        done
        export FARGLOW_TEST_PG="127.0.0.1:$port"
    else
        warn "Docker is not available: database tests will be skipped (use --quick to silence this)"
        FAILED+=("db tests skipped: no Docker")
    fi
fi
mkdir -p test-reports
step "pytest" "$PY" -m pytest -q "${PYTEST_ARGS[@]}" --junitxml=test-reports/junit.xml

if [[ $STACK == 1 ]]; then
    step "stack test" tests/stack/stack-test.sh
fi

echo
if [[ ${#FAILED[@]} -gt 0 ]]; then
    printf '%sFAILED%s: %s\n' "$C_RED" "$C_RST" "$(IFS=,; echo "${FAILED[*]}")"
    exit 1
fi
ok "all checks passed"
