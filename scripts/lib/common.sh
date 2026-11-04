#!/bin/bash
# Shared helpers for the root scripts (install, uninstall, build, test, backup, restore).
# Sourced, never run. Keep it dependency-free: bash, coreutils, docker.

# shellcheck disable=SC2034  # variables are used by the scripts that source this file
FARGLOW_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FARGLOW_SERVICES=(nginx api tick worker db migrate llm-gateway mailer backup)
FARGLOW_APP_SERVICES=(nginx api tick worker mailer llm-gateway backup)   # everything but db and migrate

if [[ -t 1 ]]; then
    C_RED=$'\e[31m'; C_GRN=$'\e[32m'; C_YEL=$'\e[33m'; C_BLU=$'\e[34m'; C_DIM=$'\e[2m'; C_RST=$'\e[0m'
else
    C_RED=""; C_GRN=""; C_YEL=""; C_BLU=""; C_DIM=""; C_RST=""
fi

info() { printf '%s==>%s %s\n' "$C_BLU" "$C_RST" "$*"; }
ok()   { printf '%s ok%s %s\n' "$C_GRN" "$C_RST" "$*"; }
warn() { printf '%swarn%s %s\n' "$C_YEL" "$C_RST" "$*" >&2; }
die()  { printf '%serror%s %s\n' "$C_RED" "$C_RST" "$*" >&2; exit 1; }

farglow_version() { tr -d '[:space:]' < "$FARGLOW_ROOT/VERSION"; }

farglow_git_rev() {
    git -C "$FARGLOW_ROOT" rev-parse --short=12 HEAD 2>/dev/null || echo "nogit"
}

require_cmd() {
    local c
    for c in "$@"; do command -v "$c" >/dev/null 2>&1 || die "'$c' is required but not installed"; done
}

require_docker() {
    require_cmd docker
    docker info >/dev/null 2>&1 || die "cannot talk to Docker (is it running, and are you in the docker group or root?)"
    docker compose version >/dev/null 2>&1 || die "Docker Compose v2 is required (the 'docker compose' plugin)"
}

# Project name and settings file. Overridable so the stack test can run a second,
# isolated copy (project farglow-test, its own env file) next to a real server.
FARGLOW_PROJECT="${FARGLOW_COMPOSE_PROJECT:-farglow}"
FARGLOW_ENV="${FARGLOW_ENV_FILE:-$FARGLOW_ROOT/.env}"

# compose ARGS... : docker compose for this checkout's project and settings file.
compose() {
    local envf=()
    [[ -f "$FARGLOW_ENV" ]] && envf=(--env-file "$FARGLOW_ENV")
    docker compose -p "$FARGLOW_PROJECT" --project-directory "$FARGLOW_ROOT" -f "$FARGLOW_ROOT/compose.yaml" "${envf[@]}" "$@"
}

# env_get KEY [FILE] : the value of KEY in a .env file (single-quoted or bare), empty if unset.
env_get() {
    local key="$1" file="${2:-$FARGLOW_ENV}" line
    [[ -f "$file" ]] || return 0
    line="$(grep -E "^${key}=" "$file" | tail -n 1)" || true
    line="${line#*=}"
    line="${line#\'}"; line="${line%\'}"
    printf '%s' "$line"
}

# random_secret [BYTES] : hex secret from the kernel CSPRNG.
random_secret() {
    local n="${1:-32}"
    od -An -tx1 -N "$n" /dev/urandom | tr -d ' \n'
}

# random_seed : a positive 62-bit integer for the galaxy seed.
random_seed() {
    local hex
    hex="$(od -An -tx8 -N 8 /dev/urandom | tr -d ' \n')"
    printf '%d' "$(( 0x$hex & 0x3FFFFFFFFFFFFFFF ))"
}

# detect_dns_servers : the host's upstream DNS (skipping 127.x stubs), space separated.
# Containers need them to resolve LAN or Tailscale names (e.g. an Ollama host).
detect_dns_servers() {
    local servers=""
    if command -v resolvectl >/dev/null 2>&1; then
        servers=$(resolvectl status 2>/dev/null | sed -n 's/^ *\(Current \)\{0,1\}DNS Servers\{0,1\}: *//p' \
            | tr ' ' '\n' | grep -vE '^(127\.|::1|$)' | awk '!seen[$0]++' | head -2 | tr '\n' ' ')
    fi
    if [[ -z "${servers// /}" ]]; then
        servers=$(for f in /run/systemd/resolve/resolv.conf /etc/resolv.conf; do
                      [[ -f $f ]] && awk '/^nameserver/ {print $2}' "$f"
                  done | grep -vE '^(127\.|::1)' | awk '!seen[$0]++' | head -2 | tr '\n' ' ')
    fi
    printf '%s' "${servers% }"
}

# wait_healthy SECONDS : wait until every running service of the project reports healthy.
wait_healthy() {
    local timeout="${1:-180}" deadline=$((SECONDS + ${1:-180})) bad
    while (( SECONDS < deadline )); do
        bad="$(compose ps --format '{{.Service}} {{.State}} {{.Health}}' 2>/dev/null \
               | awk '$1 != "migrate" && ($2 != "running" || ($3 != "" && $3 != "healthy")) {print $1"("$2","$3")"}')"
        [[ -z "$bad" ]] && return 0
        sleep 3
    done
    warn "not healthy after ${timeout}s: $bad"
    return 1
}

# confirm "Question?" [default y|n] : yes/no prompt; honours FARGLOW_ASSUME_YES=1.
confirm() {
    local q="$1" def="${2:-n}" ans hint="[y/N]"
    [[ "$def" == y ]] && hint="[Y/n]"
    if [[ "${FARGLOW_ASSUME_YES:-0}" == 1 ]]; then return 0; fi
    read -r -p "$q $hint " ans || ans=""
    ans="${ans:-$def}"
    [[ "$ans" =~ ^[Yy] ]]
}

# print_usage FILE : the script's header block (between the first two ##### rules), unprefixed.
print_usage() {
    awk '/^#{20,}/ { n++; next } n == 1 { sub(/^# ?/, ""); print } n >= 2 { exit }' "$1"
}
