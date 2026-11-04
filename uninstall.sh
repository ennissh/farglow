#!/bin/bash
###############################################################################
# uninstall.sh - stop and remove Farglow from this machine
#
#   ./uninstall.sh            stop and remove the containers and networks. Game data
#                             (database, nightly backups) and .env are KEPT, so
#                             ./install.sh brings the same galaxy back.
#   ./uninstall.sh --purge    also DELETE the game data volumes and .env, after offering
#                             a final backup. This cannot be undone.
#
# Options:
#   --purge          delete volumes (database, nightly backups) and .env as well
#   --images         also remove the farglow-* images from local Docker
#   --no-backup      --purge only: skip the final backup offer
#   --yes            no questions (with --purge: no final backup unless FARGLOW_BACKUP_FIRST=1)
#   -h, --help       this help
#
# Never touched: the backups/ directory (your backup files), tls/, and this checkout.
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"
usage() { print_usage "$0"; }

PURGE=0 IMAGES=0 BACKUP=1 YES=0
while [[ $# -gt 0 ]]; do
    case "$1" in
        --purge) PURGE=1 ;;
        --images) IMAGES=1 ;;
        --no-backup) BACKUP=0 ;;
        --yes) YES=1; export FARGLOW_ASSUME_YES=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done
require_docker

# compose needs the .env variables to parse compose.yaml; without .env use placeholders.
if [[ ! -f "$FARGLOW_ENV" ]]; then
    export POSTGRES_PASSWORD=x FARGLOW_SECRET_KEY=x FARGLOW_LINK_SIGNING_KEY=x FARGLOW_GALAXY_SEED=1
fi

running="$(compose ps -q 2>/dev/null | wc -l)"
info "Farglow uninstall: $running running container(s)"
if [[ $PURGE == 1 ]]; then
    warn "--purge DELETES the game database and nightly backups (volumes ${FARGLOW_PROJECT}_db-data, ${FARGLOW_PROJECT}_backups) and .env"
    if [[ $BACKUP == 1 && -n "$(compose ps -q db 2>/dev/null)" ]]; then
        if { [[ $YES == 0 ]] && confirm "Make a final backup first (backups/, includes encrypted secrets)?" y; } \
           || [[ "${FARGLOW_BACKUP_FIRST:-0}" == 1 ]]; then
            "$FARGLOW_ROOT/backup.sh" --with-secrets || die "the final backup failed; nothing was removed"
        fi
    fi
    if [[ $YES == 0 ]]; then
        read -r -p "Type 'delete farglow' to delete all game data: " answer
        [[ "$answer" == "delete farglow" ]] || die "cancelled; nothing was removed"
    fi
    compose down --volumes --remove-orphans
    rm -f "$FARGLOW_ENV" "$FARGLOW_ENV.previous" "$FARGLOW_ENV.pre-restore"
    ok "containers, networks, volumes and .env removed"
else
    confirm "Stop and remove the Farglow containers (data and .env are kept)?" y || die "cancelled"
    compose down --remove-orphans
    ok "containers and networks removed; data volumes and .env kept (./install.sh restarts this galaxy)"
fi

if [[ $IMAGES == 1 ]]; then
    mapfile -t imgs < <(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '/farglow-(nginx|api|tick|worker|db|migrate|llm-gateway|mailer|backup):' || true)
    if [[ ${#imgs[@]} -gt 0 ]]; then
        docker image rm "${imgs[@]}" >/dev/null && ok "removed ${#imgs[@]} image(s)"
    else
        ok "no farglow images to remove"
    fi
fi
[[ -d "$FARGLOW_ROOT/backups" ]] && echo "   Your backup files are still in backups/."
exit 0
