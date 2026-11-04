#!/bin/bash
###############################################################################
# build.sh - build the Farglow images (one per containers/<service>/Dockerfile) and push them
#
#   ./build.sh              next build X.Y.Z-N: amd64 + arm64, pushed to GHCR as :X.Y.Z-N and :latest
#   ./build.sh --release    the release X.Y.Z itself (the VERSION file): pushed once, as :X.Y.Z and :latest
#   ./build.sh --local      this machine only, loaded into local Docker as :local (nothing pushed)
#
# Build numbers (as in rapax-cloud): VERSION holds the release line (X.Y.Z). Every pushed build
# is X.Y.Z-N, and N is picked AUTOMATICALLY: the registry's tags are read and the next free
# number is used. A pushed number is always new and higher than everything already there
# (scripts/versions.py), so installs that follow :latest always get the newest build.
#
# Options:
#   --version X.Y.Z-N  push this build number instead of the next free one (still checked)
#   --replace-version  allow --version to overwrite an existing build on purpose
#   --no-latest        don't move :latest (test a build before players get it)
#   --service NAME     only this service (repeatable, or comma separated)
#   --registry REG     image prefix (default: ghcr.io/${GHCR_OWNER:-ennissh})
#   --platforms LIST   push platforms (default: linux/amd64,linux/arm64)
#   --no-cache         build without the layer cache
#   --dry-run          show the version this push would use, then stop (no tests, no build)
#   -h, --help         this help
#
# There is no CI. A push refuses unless the git tree is clean and ./test.sh passes. A release
# writes releases/vX.Y.Z.manifest (digests): commit it and tag vX.Y.Z (RELEASE.md).
#
# Registry login: GHCR_USER + GHCR_TOKEN (a token with write:packages), or an earlier
# `docker login ghcr.io`. One-time setup for arm64 on an amd64 host:
#   docker run --privileged --rm tonistiigi/binfmt --install all
# Environment: FARGLOW_BUILDX_BUILDER (default farglow-builder), FARGLOW_BUILD_CA_FILE (extra
# CA bundle for pip behind a TLS-intercepting proxy).
###############################################################################
set -euo pipefail
# shellcheck source=scripts/lib/common.sh
source "$(dirname "${BASH_SOURCE[0]}")/scripts/lib/common.sh"

usage() { print_usage "$0"; }

MODE=build NO_CACHE="" LATEST=1 REPLACE=0 WANT="" DRY=0
VERSION="$(farglow_version)"
REGISTRY="${FARGLOW_REGISTRY:-ghcr.io/${GHCR_OWNER:-ennissh}}"
PLATFORMS="${FARGLOW_BUILD_PLATFORMS:-linux/amd64,linux/arm64}"
SELECTED=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --local) MODE=local ;;
        --push) MODE=build ;;                 # the default; kept for older instructions
        --release) MODE=release ;;
        --service) [[ $# -ge 2 ]] || die "--service needs a name"; IFS=, read -r -a s <<< "$2"; SELECTED+=("${s[@]}"); shift ;;
        --version) [[ $# -ge 2 ]] || die "--version needs X.Y.Z-N"; WANT="$2"; shift ;;
        --replace-version) REPLACE=1 ;;
        --dry-run) DRY=1 ;;
        --registry) [[ $# -ge 2 ]] || die "--registry needs a value"; REGISTRY="${2%/}"; shift ;;
        --platforms) [[ $# -ge 2 ]] || die "--platforms needs a list"; PLATFORMS="$2"; shift ;;
        --no-cache) NO_CACHE="--no-cache" ;;
        --no-latest) LATEST=0 ;;
        -h|--help) usage; exit 0 ;;
        *) die "unknown option: $1 (see --help)" ;;
    esac
    shift
done

[[ "$VERSION" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]] || die "VERSION must be a release number X.Y.Z, got '$VERSION'"
[[ -n "$WANT" && $MODE != build ]] && die "--version is for builds (X.Y.Z-N); a release always uses the VERSION file"
[[ ${#SELECTED[@]} -eq 0 ]] && SELECTED=("${FARGLOW_SERVICES[@]}")
for s in "${SELECTED[@]}"; do
    [[ -f "$FARGLOW_ROOT/containers/$s/Dockerfile" ]] || die "no containers/$s/Dockerfile"
done

require_docker
docker buildx version >/dev/null 2>&1 || die "docker buildx is required (docker-buildx-plugin)"

REV="$(farglow_git_rev)"
FULL_REV="$(git -C "$FARGLOW_ROOT" rev-parse HEAD 2>/dev/null || echo nogit)"
CREATED="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BUILD_ARGS=()
build_args() {   # build_args VERSION-LABEL : the args baked into every image
    BUILD_ARGS=(--build-arg "FARGLOW_BUILD=${1}+${REV}" --build-arg "FARGLOW_REVISION=${FULL_REV}"
                --build-arg "FARGLOW_CREATED=${CREATED}")
    if [[ -n "${FARGLOW_BUILD_CA_FILE:-}" ]]; then
        BUILD_ARGS+=(--secret "id=build_ca,src=$FARGLOW_BUILD_CA_FILE")
    fi
}
# Behind a TLS-intercepting proxy, pip needs its CA: passed as a BuildKit secret (never in a layer).
if [[ -n "${FARGLOW_BUILD_CA_FILE:-}" ]]; then
    [[ -s "$FARGLOW_BUILD_CA_FILE" ]] || die "FARGLOW_BUILD_CA_FILE=$FARGLOW_BUILD_CA_FILE is missing or empty"
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
    local svc="$1" img="$REGISTRY/farglow-$1" tags=() t
    for t in "${PUSH_TAGS[@]}"; do tags+=(-t "$img:$t"); done
    info "building and pushing $svc ($PLATFORMS) as ${PUSH_TAGS[*]}"
    # shellcheck disable=SC2086
    docker buildx build --builder "$BUILDER" $NO_CACHE --push \
        --platform "$PLATFORMS" --provenance=mode=max --sbom=true \
        -f "$FARGLOW_ROOT/containers/$svc/Dockerfile" \
        "${BUILD_ARGS[@]}" "${tags[@]}" \
        "$FARGLOW_ROOT"
}

if [[ $MODE == local ]]; then
    build_args "$VERSION"
    for s in "${SELECTED[@]}"; do build_local "$s"; done
    ok "built ${#SELECTED[@]} image(s) as $REGISTRY/farglow-<service>:local"
    echo "   Run them with FARGLOW_IMAGE_TAG=local (install.sh sets this for local builds)."
    exit 0
fi

# ---- push: fast checks first, then the test gate that replaces CI, then the build --------
if [[ $DRY == 0 ]]; then
    [[ -z "$(git -C "$FARGLOW_ROOT" status --porcelain)" ]] || die "a push needs a clean git tree (commit or stash first)"
fi
[[ "$REGISTRY" == ghcr.io/* ]] || die "pushes go to GHCR (ghcr.io/<owner>), got $REGISTRY"
require_cmd python3

if [[ -n "${GHCR_USER:-}" && -n "${GHCR_TOKEN:-}" ]]; then
    info "logging in to ghcr.io as $GHCR_USER"
    printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin >/dev/null \
        || die "GHCR refused the login: GHCR_TOKEN needs write:packages"
fi

info "reading the tags already on $REGISTRY/farglow-api"
if [[ -n "${FARGLOW_TEST_TAGS+x}" ]]; then        # tests only: a fake tag list instead of GHCR
    TAGS="$FARGLOW_TEST_TAGS"
else TAGS="$(python3 "$FARGLOW_ROOT/scripts/ghcr-tags.py" "$REGISTRY" farglow-api)" \
    || die "can't read GHCR's tags, so the next build number is unknown. Log in first:
       docker login ghcr.io -u <github user>      (password: a token with write:packages)
       or export GHCR_USER and GHCR_TOKEN"
fi

if [[ $MODE == release ]]; then
    msg="$(printf '%s\n' "$TAGS" | python3 "$FARGLOW_ROOT/scripts/versions.py" release "$VERSION" 2>&1)" || die "$msg"
    TAG="$VERSION"
elif [[ -n "$WANT" ]]; then
    replace=(); [[ $REPLACE == 1 ]] && replace=(--replace)
    msg="$(printf '%s\n' "$TAGS" | python3 "$FARGLOW_ROOT/scripts/versions.py" check "$WANT" "${replace[@]}" 2>&1)" || die "$msg"
    [[ "${WANT%-*}" == "$VERSION" ]] || die "--version $WANT is not on the VERSION line ($VERSION)"
    TAG="$WANT"
else
    TAG="$(printf '%s\n' "$TAGS" | python3 "$FARGLOW_ROOT/scripts/versions.py" next "$VERSION" 2>&1)" || die "$TAG"
fi
PUSH_TAGS=("$TAG")
[[ $LATEST == 1 ]] && PUSH_TAGS+=(latest)
ok "this push is ${C_GRN}${TAG}${C_RST}$( [[ $LATEST == 1 ]] && echo ' (and :latest)')"
[[ $DRY == 1 ]] && { echo "   --dry-run: stopping before the tests and the build"; exit 0; }

ensure_builder
info "running ./test.sh (nothing is pushed unless it passes)"
"$FARGLOW_ROOT/test.sh" || die "test.sh failed: nothing was pushed"

build_args "$TAG"
for s in "${SELECTED[@]}"; do build_push "$s"; done

digests() {
    local s d
    for s in "${FARGLOW_SERVICES[@]}"; do
        d="$(docker buildx imagetools inspect "$REGISTRY/farglow-$s:$TAG" --format '{{.Manifest.Digest}}' 2>/dev/null)" \
            || { warn "farglow-$s:$TAG not found in the registry (not part of this push?)"; continue; }
        echo "$s farglow-$s:${TAG}@${d}"
    done
}

if [[ $MODE == release ]]; then
    mkdir -p "$FARGLOW_ROOT/releases"
    MANIFEST="$FARGLOW_ROOT/releases/v${TAG}.manifest"
    {
        echo "# Farglow release v${TAG}"
        echo "# Created: ${CREATED}"
        echo "# Git-Commit: ${FULL_REV}"
        echo "# Registry: ${REGISTRY}"
        echo "# Platforms: ${PLATFORMS}"
        echo "#"
        echo "# Format: service image:tag@sha256:digest (install with FARGLOW_IMAGE_TAG=${TAG})"
        digests
    } > "$MANIFEST"
    ok "released ${TAG}. Digests in ${MANIFEST#"$FARGLOW_ROOT"/}: commit it and tag v${TAG} (see RELEASE.md)"
else
    digests | sed 's/^/   /'
    ok "pushed build ${TAG}. Servers pick it up with: ./install.sh --tag ${TAG}$( [[ $LATEST == 1 ]] && echo ' (or --tag latest)')"
fi
