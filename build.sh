#!/bin/bash
###############################################################################
# build.sh - build the Farglow images, one per containers/<service>/Dockerfile
#
#   ./build.sh --local              build for this machine, load into local Docker (default)
#   ./build.sh --push               run ./test.sh, then build amd64+arm64 and push to GHCR
#
# Options:
#   --service NAME     only this service (repeatable, or comma separated)
#   --version X.Y.Z    version to build (default: the VERSION file)
#   --registry REG     image prefix (default: ghcr.io/${GHCR_OWNER:-ennissh})
#   --platforms LIST   push platforms (default: linux/amd64,linux/arm64)
#   --no-cache         build without the layer cache
#   --no-latest        --push only: do not move the :latest tag
#   --force            --push only: overwrite an already-published :X.Y.Z tag
#   -h, --help         this help
#
# Tags. --local: :local and :X.Y.Z-<git>. --push: :X.Y.Z, :X.Y.Z-<git> and :latest, all in
# ONE `buildx build --push` per image (a multi-platform result never enters the local
# image store, so it cannot be tagged or pushed afterwards). After a push, the digests go to
# releases/vX.Y.Z.manifest (commit it). There is no CI: --push refuses unless ./test.sh
# passes and the git tree is clean.
#
# Environment: GHCR_USER + GHCR_TOKEN (optional; else use an existing `docker login ghcr.io`),
# FARGLOW_BUILDX_BUILDER (default farglow-builder), FARGLOW_BUILD_CA_FILE (extra CA bundle
# for pip behind a TLS-intercepting proxy).
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"

usage() { print_usage "$0"; }

MODE=local NO_CACHE="" LATEST=1 FORCE=0
VERSION="$(farglow_version)"
REGISTRY="${FARGLOW_REGISTRY:-ghcr.io/${GHCR_OWNER:-ennissh}}"
PLATFORMS="${FARGLOW_BUILD_PLATFORMS:-linux/amd64,linux/arm64}"
SELECTED=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --local) MODE=local ;;
        --push) MODE=push ;;
        --service) [[ $# -ge 2 ]] || die "--service needs a name"; IFS=, read -r -a s <<< "$2"; SELECTED+=("${s[@]}"); shift ;;
        --version) [[ $# -ge 2 ]] || die "--version needs X.Y.Z"; VERSION="$2"; shift ;;
        --registry) [[ $# -ge 2 ]] || die "--registry needs a value"; REGISTRY="${2%/}"; shift ;;
        --platforms) [[ $# -ge 2 ]] || die "--platforms needs a list"; PLATFORMS="$2"; shift ;;
        --no-cache) NO_CACHE="--no-cache" ;;
        --no-latest) LATEST=0 ;;
        --force) FORCE=1 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+(-[0-9A-Za-z.-]+)?$ ]] || die "version '$VERSION' is not semver X.Y.Z[-pre]"
[[ ${#SELECTED[@]} -eq 0 ]] && SELECTED=("${FARGLOW_SERVICES[@]}")
for s in "${SELECTED[@]}"; do
    [[ -f "$FARGLOW_ROOT/containers/$s/Dockerfile" ]] || die "no containers/$s/Dockerfile"
done

require_docker
docker buildx version >/dev/null 2>&1 || die "docker buildx is required (docker-buildx-plugin)"

REV="$(farglow_git_rev)"
FULL_REV="$(git -C "$FARGLOW_ROOT" rev-parse HEAD 2>/dev/null || echo nogit)"
CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BUILD_ARGS=(--build-arg "FARGLOW_BUILD=${VERSION}+${REV}" --build-arg "FARGLOW_REVISION=${FULL_REV}"
            --build-arg "FARGLOW_CREATED=${CREATED}")
# Behind a TLS-intercepting proxy, pip needs its CA: passed as a BuildKit secret (never in a layer).
if [[ -n "${FARGLOW_BUILD_CA_FILE:-}" ]]; then
    [[ -s "$FARGLOW_BUILD_CA_FILE" ]] || die "FARGLOW_BUILD_CA_FILE=$FARGLOW_BUILD_CA_FILE is missing or empty"
    BUILD_ARGS+=(--secret "id=build_ca,src=$FARGLOW_BUILD_CA_FILE")
fi

build_local() {
    local svc="$1" img="$REGISTRY/farglow-$1"
    info "building $svc (local, $(uname -m))"
    # shellcheck disable=SC2086
    docker buildx build $NO_CACHE --load \
        -f "$FARGLOW_ROOT/containers/$svc/Dockerfile" \
        "${BUILD_ARGS[@]}" \
        -t "$img:local" -t "$img:${VERSION}-${REV}" \
        "$FARGLOW_ROOT"
}

ensure_builder() {
    local b="${FARGLOW_BUILDX_BUILDER:-farglow-builder}"
    if ! docker buildx inspect "$b" >/dev/null 2>&1; then
        info "creating buildx builder '$b' (docker-container driver, needed for multi-arch)"
        docker buildx create --name "$b" --driver docker-container --bootstrap >/dev/null \
            || { docker buildx rm "$b" >/dev/null 2>&1 || true; die "could not create builder '$b'"; }
    fi
    local have p
    have="$(docker buildx inspect --bootstrap "$b" | sed -n 's/^ *Platforms: *//p' | tr -d ' ')"
    for p in ${PLATFORMS//,/ }; do
        [[ ",$have," == *",$p"[,/]* ]] || die "builder '$b' cannot build $p. Register QEMU first:
    docker run --privileged --rm tonistiigi/binfmt --install all"
    done
    BUILDER="$b"
}

build_push() {
    local svc="$1" img="$REGISTRY/farglow-$1" tags
    tags=(-t "$img:$VERSION" -t "$img:${VERSION}-${REV}")
    [[ $LATEST == 1 ]] && tags+=(-t "$img:latest")
    info "building and pushing $svc ($PLATFORMS)"
    # shellcheck disable=SC2086
    docker buildx build --builder "$BUILDER" $NO_CACHE --push \
        --platform "$PLATFORMS" --provenance=mode=max --sbom=true \
        -f "$FARGLOW_ROOT/containers/$svc/Dockerfile" \
        "${BUILD_ARGS[@]}" "${tags[@]}" \
        "$FARGLOW_ROOT"
}

if [[ $MODE == local ]]; then
    for s in "${SELECTED[@]}"; do build_local "$s"; done
    ok "built ${#SELECTED[@]} image(s) as $REGISTRY/farglow-<service>:local"
    echo "   Run them with FARGLOW_IMAGE_TAG=local (install.sh sets this for local builds)."
    exit 0
fi

# ---- push: the gate that replaces CI ---------------------------------------------------
[[ -z "$(git -C "$FARGLOW_ROOT" status --porcelain)" ]] || die "--push needs a clean git tree (commit or stash first)"
info "running ./test.sh (a push is refused unless it passes)"
"$FARGLOW_ROOT/test.sh" || die "test.sh failed: nothing was pushed"

if [[ -n "${GHCR_USER:-}" && -n "${GHCR_TOKEN:-}" ]]; then
    info "logging in to ${REGISTRY%%/*} as $GHCR_USER"
    printf '%s' "$GHCR_TOKEN" | docker login "${REGISTRY%%/*}" -u "$GHCR_USER" --password-stdin >/dev/null
fi

if [[ $FORCE == 0 ]]; then
    for s in "${SELECTED[@]}"; do
        if docker buildx imagetools inspect "$REGISTRY/farglow-$s:$VERSION" >/dev/null 2>&1; then
            die "$REGISTRY/farglow-$s:$VERSION is already published. Bump VERSION, or --force to overwrite."
        fi
    done
fi

ensure_builder
for s in "${SELECTED[@]}"; do build_push "$s"; done

mkdir -p "$FARGLOW_ROOT/releases"
MANIFEST="$FARGLOW_ROOT/releases/v${VERSION}.manifest"
{
    echo "# Farglow release v${VERSION}"
    echo "# Created: ${CREATED}"
    echo "# Git-Commit: ${FULL_REV}"
    echo "# Registry: ${REGISTRY}"
    echo "# Platforms: ${PLATFORMS}"
    echo "#"
    echo "# Format: service image:tag@sha256:digest (install with FARGLOW_IMAGE_TAG=${VERSION})"
    for s in "${FARGLOW_SERVICES[@]}"; do
        d="$(docker buildx imagetools inspect "$REGISTRY/farglow-$s:$VERSION" --format '{{.Manifest.Digest}}' 2>/dev/null)" \
            || { warn "farglow-$s:$VERSION not found in the registry (not part of this build?)"; continue; }
        echo "$s farglow-$s:${VERSION}@${d}"
    done
} > "$MANIFEST"
ok "pushed. Digests written to ${MANIFEST#"$FARGLOW_ROOT"/}: commit it and tag v${VERSION} (see RELEASE.md)"
