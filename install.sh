#!/bin/bash
###############################################################################
# install.sh - install (or reconfigure) a Farglow server on this machine
#
#   ./install.sh                     interactive: asks for everything, then starts the stack
#   ./install.sh --non-interactive   take answers from FARGLOW_* / SMTP_* environment
#                                    variables (or the existing .env), defaults otherwise
#
# Options:
#   --source ghcr|local   pull images from GHCR (default) or build them here (./build.sh --local)
#   --tag TAG             image tag to run (default: VERSION for ghcr, "local" for local)
#   --no-start            write .env only; do not pull, build or start anything
#   --skip-mail-test      do not send the SMTP test email
#   --settings MODE       when .env already exists: saved (use it as is, no questions),
#                         review (ask each setting, saved values as defaults) or fresh (ask
#                         each setting with the built-in defaults). Asked when not given.
#   -h, --help            this help
#
# What it asks: domain and ports, the admin email, the image source, the AI tier (T0 needs
# nothing; T1/T2 an Ollama URL and model; T3 an OpenAI-compatible URL, model and API key),
# and SMTP (blank host = mail off) with a test send. It writes .env (mode 600) and
# generates the database password, app secret, link-signing key and galaxy seed.
#
# Re-running is safe: secrets are never regenerated while a database exists (it uses them).
# To start a new galaxy, run ./uninstall.sh --purge first.
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"

usage() { print_usage "$0"; }

INTERACTIVE=1 START=1 MAIL_TEST=1 SOURCE_ARG="" TAG_ARG="" SETTINGS=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --non-interactive) INTERACTIVE=0 ;;
        --source) [[ $# -ge 2 ]] || die "--source needs ghcr or local"; SOURCE_ARG="$2"; shift ;;
        --tag) [[ $# -ge 2 ]] || die "--tag needs a value"; TAG_ARG="$2"; shift ;;
        --no-start) START=0 ;;
        --skip-mail-test) MAIL_TEST=0 ;;
        --settings) [[ $# -ge 2 ]] || die "--settings needs saved, review or fresh"; SETTINGS="$2"; shift ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done
[[ $INTERACTIVE == 1 && ! -t 0 ]] && die "no terminal for questions: use --non-interactive with FARGLOW_* variables"
[[ -z "$SETTINGS" || "$SETTINGS" =~ ^(saved|review|fresh)$ ]] || die "--settings must be saved, review or fresh"
ASK=$INTERACTIVE      # whether the questions are asked (a terminal is still needed for prompts later)
SECRET_KEYS=" POSTGRES_PASSWORD FARGLOW_SECRET_KEY FARGLOW_LINK_SIGNING_KEY FARGLOW_GALAXY_SEED "

ENV_FILE="$FARGLOW_ENV"
VERSION="$(farglow_version)"

# ---------------------------------------------------------------------------- answers
# current KEY DEFAULT : environment variable, else existing .env, else DEFAULT
current() {
    local key="$1" def="${2:-}" v
    v="${!key:-}"
    # fresh: the saved answers are ignored (the generated secrets are not: see below)
    if [[ -z "$v" && ( "$SETTINGS" != fresh || "$SECRET_KEYS" == *" $key "* ) ]]; then
        v="$(env_get "$key" "$ENV_FILE")"
    fi
    printf '%s' "${v:-$def}"
}

# ask KEY "Question" DEFAULT [secret] : sets KEY. Validation is done by the caller.
ask() {
    local key="$1" q="$2" def="$3" secret="${4:-}" ans shown
    if [[ $ASK == 0 ]]; then printf -v "$key" '%s' "$def"; return; fi
    shown="$def"
    [[ -n "$secret" && -n "$def" ]] && shown="(keep current)"
    if [[ -n "$secret" ]]; then
        read -r -s -p "  $q [${shown}]: " ans; echo
    else
        read -r -p "  $q [${shown}]: " ans
    fi
    printf -v "$key" '%s' "${ans:-$def}"
}

choose() {  # choose KEY "Question" DEFAULT option...
    local key="$1" q="$2" def="$3"; shift 3
    local opts=" $* "
    while :; do
        ask "$key" "$q ($*)" "$def"
        [[ "$opts" == *" ${!key} "* ]] && return
        [[ $ASK == 0 ]] && die "$key='${!key}' must be one of: $* (run ./install.sh --settings review to fix it)"
        warn "please answer one of: $*"
    done
}

valid_email() { [[ "$1" =~ ^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$ ]]; }
valid_host()  { [[ "$1" =~ ^[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?$ ]]; }
valid_port()  { [[ "$1" =~ ^[0-9]+$ ]] && (( $1 >= 1 && $1 <= 65535 )); }

# ---------------------------------------------------------------------------- preflight
info "Farglow ${VERSION} installer"
require_docker
[[ "$(uname -s)" == Linux ]] || warn "the supported host is Linux (Ubuntu 26.04 LTS); continuing anyway"
avail_kb="$(df -Pk "$FARGLOW_ROOT" | awk 'NR==2 {print $4}')"
(( avail_kb > 5 * 1024 * 1024 )) || warn "less than 5 GB free on $(df -P "$FARGLOW_ROOT" | awk 'NR==2 {print $6}')"
if [[ -f "$ENV_FILE" ]]; then
    g() { env_get "$1" "$ENV_FILE"; }
    echo
    info "Saved settings found in ${ENV_FILE/#$FARGLOW_ROOT\//}"
    echo "  server   $(g FARGLOW_PUBLIC_URL) · admin $(g FARGLOW_ADMIN_EMAIL)"
    echo "  images   $(g FARGLOW_IMAGE_SOURCE)$( [[ "$(g FARGLOW_IMAGE_SOURCE)" == ghcr ]] && echo " $(g FARGLOW_REGISTRY):$(g FARGLOW_IMAGE_TAG)")"
    echo "  AI       $(g FARGLOW_AI_TIER)$( [[ -n "$(g FARGLOW_LLM_ENDPOINT)" ]] && echo " · $(g FARGLOW_LLM_MODEL) at $(g FARGLOW_LLM_ENDPOINT)")"
    echo "  mail     $( [[ -n "$(g SMTP_HOST)" ]] && echo "$(g SMTP_HOST):$(g SMTP_PORT) $(g SMTP_SECURITY) as $(g SMTP_USER)" || echo off)"
    echo "  dev mode $(g FARGLOW_DEBUG)"
    if [[ -z "$SETTINGS" ]]; then
        if [[ $INTERACTIVE == 0 ]]; then
            SETTINGS=saved
        else
            echo "  1) Use these settings as they are (no questions)"
            echo "  2) Go through each setting (these values as the defaults)"
            echo "  3) Start from scratch (each setting with the built-in defaults)"
            while :; do
                read -r -p "  Choose 1, 2 or 3 [1]: " pick
                case "${pick:-1}" in 1) SETTINGS=saved; break ;; 2) SETTINGS=review; break ;; 3) SETTINGS=fresh; break ;;
                    *) warn "please answer 1, 2 or 3" ;; esac
            done
        fi
    fi
    [[ "$SETTINGS" == saved ]] && ASK=0
    if [[ "$SETTINGS" == fresh ]] && docker volume inspect "${FARGLOW_PROJECT}_db-data" >/dev/null 2>&1; then
        warn "starting the settings from scratch, but your galaxy and its secrets are kept (the database uses them).
       For a new galaxy as well: ./uninstall.sh --purge, then ./install.sh"
    fi
fi

# ---------------------------------------------------------------------------- questions
echo
info "Server"
while :; do
    ask FARGLOW_DOMAIN "Domain name players use (or localhost / an IP for a LAN server)" "$(current FARGLOW_DOMAIN localhost)"
    valid_host "$FARGLOW_DOMAIN" && break
    [[ $ASK == 0 ]] && die "FARGLOW_DOMAIN '$FARGLOW_DOMAIN' is not a valid host name"
    warn "that is not a valid host name"
done
while :; do
    ask FARGLOW_HTTP_PORT "HTTP port" "$(current FARGLOW_HTTP_PORT 80)"
    ask FARGLOW_HTTPS_PORT "HTTPS port" "$(current FARGLOW_HTTPS_PORT 443)"
    valid_port "$FARGLOW_HTTP_PORT" && valid_port "$FARGLOW_HTTPS_PORT" && break
    [[ $ASK == 0 ]] && die "ports must be 1-65535"
    warn "ports must be 1-65535"
done
FARGLOW_TLS_DIR="$(current FARGLOW_TLS_DIR ./tls)"
mkdir -p "$FARGLOW_ROOT/${FARGLOW_TLS_DIR#./}" 2>/dev/null || true
if [[ -s "$FARGLOW_ROOT/${FARGLOW_TLS_DIR#./}/fullchain.pem" ]]; then
    scheme=https port="$FARGLOW_HTTPS_PORT" defport=443
    ok "TLS certificate found in $FARGLOW_TLS_DIR: serving HTTPS"
else
    scheme=http port="$FARGLOW_HTTP_PORT" defport=80
    echo "  No certificate in $FARGLOW_TLS_DIR (fullchain.pem + privkey.pem): serving plain HTTP."
    echo "  Put a certificate there (or terminate TLS in front of this server) before going public."
fi
FARGLOW_PUBLIC_URL="${scheme}://${FARGLOW_DOMAIN}"
[[ "$port" != "$defport" ]] && FARGLOW_PUBLIC_URL="${FARGLOW_PUBLIC_URL}:${port}"

while :; do
    ask FARGLOW_ADMIN_EMAIL "Host admin email (gets the test email; becomes the first admin)" "$(current FARGLOW_ADMIN_EMAIL "")"
    valid_email "$FARGLOW_ADMIN_EMAIL" && break
    [[ $ASK == 0 ]] && die "FARGLOW_ADMIN_EMAIL is required and must be an email address"
    warn "please give a valid email address"
done

echo
info "Images"
src_default="$(current FARGLOW_IMAGE_SOURCE "")"
[[ -n "$SOURCE_ARG" ]] && src_default="$SOURCE_ARG"
# Offer GHCR only if the version is actually published there (a saved "ghcr" answer is
# re-checked when reviewing; "use as is" and an explicit --source ghcr skip the check, and a
# failed pull still offers a local build).
if [[ "$SOURCE_ARG" != ghcr && "$SETTINGS" != saved && ( -z "$src_default" || "$src_default" == ghcr ) ]]; then
    want_tag="${TAG_ARG:-$(current FARGLOW_IMAGE_TAG "")}"
    [[ "$want_tag" == local ]] && want_tag=""
    if [[ -z "$want_tag" ]]; then        # the release if it is out, else the newest build
        want_tag="$VERSION"
        published "$(current FARGLOW_REGISTRY ghcr.io/ennissh)" "$VERSION" || want_tag=latest
    fi
    if published "$(current FARGLOW_REGISTRY ghcr.io/ennissh)" "$want_tag"; then
        src_default=ghcr
    else
        src_default=local
        echo "  Farglow $want_tag is not on GHCR yet (never pushed, private, or GHCR unreachable): building here is the default."
    fi
fi
choose FARGLOW_IMAGE_SOURCE "Image source" "$src_default" ghcr local
FARGLOW_REGISTRY="$(current FARGLOW_REGISTRY ghcr.io/ennissh)"
if [[ "$FARGLOW_IMAGE_SOURCE" == local ]]; then
    FARGLOW_IMAGE_TAG="${TAG_ARG:-local}"
else
    ask FARGLOW_REGISTRY "Registry" "$FARGLOW_REGISTRY"
    tag_default="$(current FARGLOW_IMAGE_TAG "")"
    [[ "$tag_default" == local ]] && tag_default=""
    if [[ -z "$tag_default" ]]; then     # the release if it is out, else the newest build
        tag_default="$VERSION"
        published "$FARGLOW_REGISTRY" "$VERSION" || tag_default=latest
    fi
    ask FARGLOW_IMAGE_TAG "Version to run (X.Y.Z release, X.Y.Z-N build, or latest)" "${TAG_ARG:-$tag_default}"
fi

echo
info "AI (every feature works at T0, with no AI)"
echo "  T0 none · T1 small local model · T2 strong local model (Ollama) · T3 your own API key · T4 Relay (not yet available)"
choose FARGLOW_AI_TIER "AI tier" "$(current FARGLOW_AI_TIER T0)" T0 T1 T2 T3 T4
FARGLOW_LLM_ENDPOINT="$(current FARGLOW_LLM_ENDPOINT "")"
FARGLOW_LLM_MODEL="$(current FARGLOW_LLM_MODEL "")"
FARGLOW_LLM_API_KEY="$(current FARGLOW_LLM_API_KEY "")"
case "$FARGLOW_AI_TIER" in
    T1|T2)
        ask FARGLOW_LLM_ENDPOINT "Ollama URL (e.g. http://mac-studio:11434 over Tailscale; http://host.docker.internal:11434 on this host)" \
            "${FARGLOW_LLM_ENDPOINT:-http://host.docker.internal:11434}"
        ask FARGLOW_LLM_MODEL "Model" "${FARGLOW_LLM_MODEL:-$([[ $FARGLOW_AI_TIER == T1 ]] && echo llama3.2:3b || echo llama3.1:8b)}"
        FARGLOW_LLM_API_KEY="" ;;
    T3)
        ask FARGLOW_LLM_ENDPOINT "OpenAI-compatible API base URL" "${FARGLOW_LLM_ENDPOINT:-https://api.openai.com/v1}"
        ask FARGLOW_LLM_MODEL "Model" "${FARGLOW_LLM_MODEL:-gpt-4o-mini}"
        ask FARGLOW_LLM_API_KEY "API key" "$FARGLOW_LLM_API_KEY" secret
        [[ -n "$FARGLOW_LLM_API_KEY" ]] || die "T3 needs an API key" ;;
    T4)
        warn "the Generative Distractions Relay is not available yet: the server will run at T0 until it is" ;;
    *)  FARGLOW_LLM_ENDPOINT="" FARGLOW_LLM_MODEL="" FARGLOW_LLM_API_KEY="" ;;
esac

echo
info "Email (the morning Dispatch). Leave the SMTP host blank to turn mail off."
ask SMTP_HOST "SMTP host" "$(current SMTP_HOST "")"
SMTP_PORT="$(current SMTP_PORT 587)" SMTP_SECURITY="$(current SMTP_SECURITY starttls)"
SMTP_USER="$(current SMTP_USER "")" SMTP_PASSWORD="$(current SMTP_PASSWORD "")"
SMTP_FROM="$(current SMTP_FROM "Farglow <dispatch@${FARGLOW_DOMAIN}>")"
if [[ -n "$SMTP_HOST" ]]; then
    valid_host "$SMTP_HOST" || die "SMTP host '$SMTP_HOST' is not a valid host name"
    choose SMTP_SECURITY "Security" "$SMTP_SECURITY" starttls ssl none
    [[ "$SMTP_SECURITY" == ssl && "$SMTP_PORT" == 587 ]] && SMTP_PORT=465
    ask SMTP_PORT "SMTP port" "$SMTP_PORT"
    valid_port "$SMTP_PORT" || die "SMTP port must be 1-65535"
    ask SMTP_USER "SMTP user (blank for none)" "$SMTP_USER"
    [[ -n "$SMTP_USER" ]] && ask SMTP_PASSWORD "SMTP password" "$SMTP_PASSWORD" secret
    ask SMTP_FROM "From address" "$SMTP_FROM"
fi

FARGLOW_DEBUG="$(current FARGLOW_DEBUG false)"
if [[ $ASK == 1 ]]; then
    dbg_def=n; [[ "$FARGLOW_DEBUG" == true ]] && dbg_def=y
    if confirm "  Development mode (ticks every 5 minutes instead of hourly)?" "$dbg_def"; then FARGLOW_DEBUG=true; else FARGLOW_DEBUG=false; fi
fi

# ---------------------------------------------------------------------------- secrets + DNS
if [[ "$SETTINGS" == fresh ]] && ! docker volume inspect "${FARGLOW_PROJECT}_db-data" >/dev/null 2>&1; then
    SECRET_KEYS=" "                # no database yet: a fresh start gets new secrets and a new seed
fi
POSTGRES_PASSWORD="$(current POSTGRES_PASSWORD "")"
if [[ -z "$POSTGRES_PASSWORD" ]] && docker volume inspect "${FARGLOW_PROJECT}_db-data" >/dev/null 2>&1; then
    die "the database volume ${FARGLOW_PROJECT}_db-data exists but .env has no POSTGRES_PASSWORD.
       Restore .env from a backup (./restore.sh --with-secrets), or remove the old data with ./uninstall.sh --purge"
fi
[[ -z "$POSTGRES_PASSWORD" ]] && POSTGRES_PASSWORD="$(random_secret 24)"
# shellcheck disable=SC2034  # written to .env through ${!k}
FARGLOW_SECRET_KEY="$(current FARGLOW_SECRET_KEY "$(random_secret 32)")"
# shellcheck disable=SC2034
FARGLOW_LINK_SIGNING_KEY="$(current FARGLOW_LINK_SIGNING_KEY "$(random_secret 32)")"
# shellcheck disable=SC2034
FARGLOW_GALAXY_SEED="$(current FARGLOW_GALAXY_SEED "$(random_seed)")"
read -r FARGLOW_DNS_1 FARGLOW_DNS_2 _ <<< "$(detect_dns_servers) 1.1.1.1 9.9.9.9" || true
FARGLOW_DNS_1="$(current FARGLOW_DNS_1 "$FARGLOW_DNS_1")"
FARGLOW_DNS_2="$(current FARGLOW_DNS_2 "$FARGLOW_DNS_2")"

# ---------------------------------------------------------------------------- write .env
KEYS=(FARGLOW_DOMAIN FARGLOW_PUBLIC_URL FARGLOW_HTTP_PORT FARGLOW_HTTPS_PORT FARGLOW_TLS_DIR
      FARGLOW_ADMIN_EMAIL FARGLOW_IMAGE_SOURCE FARGLOW_REGISTRY FARGLOW_IMAGE_TAG
      FARGLOW_AI_TIER FARGLOW_LLM_ENDPOINT FARGLOW_LLM_MODEL FARGLOW_LLM_API_KEY
      SMTP_HOST SMTP_PORT SMTP_SECURITY SMTP_USER SMTP_PASSWORD SMTP_FROM
      FARGLOW_DEBUG FARGLOW_DNS_1 FARGLOW_DNS_2
      POSTGRES_PASSWORD FARGLOW_SECRET_KEY FARGLOW_LINK_SIGNING_KEY FARGLOW_GALAXY_SEED)
# Optional advanced keys survive a re-run if the operator set them by hand.
EXTRA_KEYS=(FARGLOW_BIND FARGLOW_TICK_SECONDS FARGLOW_LOG_LEVEL FARGLOW_WEB_WORKERS FARGLOW_LLM_TIMEOUT
            FARGLOW_BACKUP_HOUR FARGLOW_BACKUP_KEEP FARGLOW_RESTORE_POINTS_KEEP)
for k in "${KEYS[@]}"; do
    v="${!k}"
    [[ "$v" == *"'"* || "$v" == *$'\n'* ]] && die "$k contains a single quote or newline, which .env cannot hold"
done

tmp="$(mktemp "$(dirname "$ENV_FILE")/.env.XXXXXX")"
chmod 600 "$tmp"
{
    echo "# Farglow server settings, written by install.sh $(date -u +%Y-%m-%dT%H:%M:%SZ) for ${VERSION}."
    echo "# Mode 600: holds secrets. Re-run ./install.sh to change answers; edit by hand only if"
    echo "# you know what a key does (see .env.example). Values are single-quoted (no \$ expansion)."
    for k in "${KEYS[@]}"; do printf "%s='%s'\n" "$k" "${!k}"; done
    for k in "${EXTRA_KEYS[@]}"; do
        v="$(current "$k" "")"
        [[ -n "$v" ]] && printf "%s='%s'\n" "$k" "$v"
    done
    printf "FARGLOW_INSTALLED_VERSION='%s'\n" "$VERSION"
} > "$tmp"
[[ -f "$ENV_FILE" ]] && cp -p "$ENV_FILE" "$ENV_FILE.previous"
mv "$tmp" "$ENV_FILE"
chmod 600 "$ENV_FILE"
ok "wrote .env (mode 600)"

if [[ $START == 0 ]]; then
    ok "--no-start: nothing pulled or started. Next: docker compose up -d"
    exit 0
fi

# ---------------------------------------------------------------------------- images + start
echo
if [[ "$FARGLOW_IMAGE_SOURCE" == local ]]; then
    info "building images locally"
    "$FARGLOW_ROOT/build.sh" --local --registry "$FARGLOW_REGISTRY"
else
    info "pulling ${FARGLOW_REGISTRY}/farglow-*:${FARGLOW_IMAGE_TAG}"
    if ! compose pull --quiet; then
        warn "pull failed: ${FARGLOW_REGISTRY}/farglow-*:${FARGLOW_IMAGE_TAG} is not published, or is private
       (private images need: docker login ghcr.io with a token that has read:packages)"
        if [[ $INTERACTIVE == 1 ]] && confirm "Build the images on this machine instead?" y; then
            FARGLOW_IMAGE_SOURCE=local FARGLOW_IMAGE_TAG=local
            env_set FARGLOW_IMAGE_SOURCE local "$ENV_FILE"
            env_set FARGLOW_IMAGE_TAG local "$ENV_FILE"
            info "building images locally"
            "$FARGLOW_ROOT/build.sh" --local --registry "$FARGLOW_REGISTRY"
        else
            die "nothing was started. Install from source with: ./install.sh --source local"
        fi
    fi
fi

info "starting the stack"
compose up -d --remove-orphans
info "waiting for every service to become healthy"
if ! wait_healthy 300; then
    compose ps
    die "the stack did not become healthy. Look at: docker compose logs --tail 100"
fi
ok "all services healthy"

# ---------------------------------------------------------------------------- checks
if [[ -n "$SMTP_HOST" && $MAIL_TEST == 1 ]]; then
    info "sending a test email to $FARGLOW_ADMIN_EMAIL"
    if compose exec -T mailer python -m farglow mail test --to "$FARGLOW_ADMIN_EMAIL"; then
        ok "test email sent: check the inbox (and spam folder) of $FARGLOW_ADMIN_EMAIL"
    else
        warn "the test email failed. Fix the SMTP answers by re-running ./install.sh; the game runs without mail meanwhile"
    fi
elif [[ -z "$SMTP_HOST" ]]; then
    warn "mail is off: there will be no morning Dispatch email until SMTP is configured"
fi

if [[ "$FARGLOW_AI_TIER" != T0 ]]; then
    info "asking the LLM gateway for a test proposal at $FARGLOW_AI_TIER"
    out="$(compose exec -T llm-gateway python - <<'PY' 2>&1 || true
import json, urllib.request
req = urllib.request.Request("http://127.0.0.1:8100/v1/propose", method="POST",
      data=json.dumps({"task": "advisor.greeting", "prompt": "Reply {\"text\": \"ready\"}"}).encode(),
      headers={"Content-Type": "application/json"})
print(json.loads(urllib.request.urlopen(req, timeout=120).read()))
PY
)"
    if [[ "$out" == *"'fallback': False"* ]]; then ok "AI tier $FARGLOW_AI_TIER answered"; else warn "AI tier $FARGLOW_AI_TIER did not answer; the game falls back to T0. Gateway said: $out"; fi
fi

tick_line="$(compose exec -T tick python -m farglow engine hash 2>/dev/null || true)"
echo
ok "Farglow is running: ${FARGLOW_PUBLIC_URL}"
echo "   engine: tick ${tick_line%% *}, $( [[ "$FARGLOW_DEBUG" == true ]] && echo 'ticks every 5 minutes (development mode)' || echo 'ticks hourly')"
echo "   status: docker compose ps · logs: docker compose logs -f · backup: ./backup.sh"
