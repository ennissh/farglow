#!/bin/bash
###############################################################################
# new-service.sh - scaffold a new Farglow service that follows the container contract
#
#   scripts/new-service.sh NAME "One-line title" [--dry-run]
#
# Creates containers/NAME/ (Dockerfile, healthcheck.py, requirements.txt) and
# farglow/<module>/__main__.py from scripts/service-skeleton/, then prints the compose.yaml
# block and the remaining steps. NAME: lower case, digits and dashes. Never overwrites.
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

DRY=0 ARGS=()
for a in "$@"; do
    case "$a" in
        --dry-run) DRY=1 ;;
        -h|--help) print_usage "$0"; exit 0 ;;
        *) ARGS+=("$a") ;;
    esac
done
[[ ${#ARGS[@]} -eq 2 ]] || { print_usage "$0"; exit 2; }
NAME="${ARGS[0]}" TITLE="${ARGS[1]}"
[[ "$NAME" =~ ^[a-z][a-z0-9-]{1,30}$ ]] || die "NAME must be lower case letters, digits and dashes"
[[ "$TITLE" != *'|'* && "$TITLE" != *'"'* ]] || die "TITLE may not contain | or \""
MODULE="${NAME//-/_}"
SK="$FARGLOW_ROOT/scripts/service-skeleton"
CDIR="$FARGLOW_ROOT/containers/$NAME" MDIR="$FARGLOW_ROOT/farglow/$MODULE"
[[ -e "$CDIR" || -e "$MDIR" ]] && die "containers/$NAME or farglow/$MODULE already exists"
PYBASE="$(sed -n 's/^FROM \(python:[^ ]*\).*/\1/p' "$FARGLOW_ROOT/containers/api/Dockerfile" | head -1)"
[[ -n "$PYBASE" ]] || die "could not read the pinned Python base from containers/api/Dockerfile"

render() { sed -e "s|__NAME__|$NAME|g" -e "s|__TITLE__|$TITLE|g" -e "s|__MODULE__|$MODULE|g" -e "s|__PYBASE__|$PYBASE|g" "$1"; }

if [[ $DRY == 1 ]]; then
    info "would create containers/$NAME/{Dockerfile,healthcheck.py,requirements.txt} and farglow/$MODULE/"
    exit 0
fi
mkdir -p "$CDIR" "$MDIR"
render "$SK/Dockerfile" > "$CDIR/Dockerfile"
cp "$SK/healthcheck.py" "$CDIR/healthcheck.py" && chmod +x "$CDIR/healthcheck.py"
cp "$SK/requirements.txt" "$CDIR/requirements.txt"
printf '"""%s"""\n' "$TITLE" > "$MDIR/__init__.py"
render "$SK/__main__.py" > "$MDIR/__main__.py"
ok "created containers/$NAME/ and farglow/$MODULE/"
cat <<NEXT

Next steps:
  1. Add the service to compose.yaml (and to FARGLOW_SERVICES in scripts/lib/common.sh):

  $NAME:
    image: \${FARGLOW_REGISTRY:-ghcr.io/ennissh}/farglow-$NAME:\${FARGLOW_IMAGE_TAG:-latest}
    <<: *python
    environment:
      <<: [*db-env, *common-env]
    depends_on: *after-migrate
    networks: [core]

  2. Implement farglow/$MODULE/__main__.py and its tests under tests/.
  3. Add a CHANGELOG.md entry under [Unreleased], then ./test.sh and ./build.sh --local --service $NAME.
NEXT
