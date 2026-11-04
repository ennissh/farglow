#!/bin/bash
###############################################################################
# check-secrets.sh - scan the checkout for committed secrets with gitleaks (blocking)
#
#   scripts/check-secrets.sh            scan tracked + new (non-ignored) files
#   scripts/check-secrets.sh --history  also scan every commit
#
# Uses a pinned gitleaks release, downloaded once and verified by SHA-256 into
# ~/.cache/farglow/ (an installed gitleaks of the same version is used as is).
# Exit 0 clean, 1 secrets found, 2 gitleaks could not run.
# A finding is fixed (move the value to .env), not allow-listed. .gitleaks.toml holds only
# narrow, reviewed false positives.
###############################################################################
set -uo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VER=8.28.0
declare -A SUMS=(
    [linux_x64]=a65b5253807a68ac0cafa4414031fd740aeb55f54fb7e55f386acb52e6a840eb
    [linux_arm64]=eff65261156100e5d94a6b3dec313d532fddfe19ae1590bf7a2b4f2699128356
    [darwin_x64]=edf5a507008b0d2ef4959575772772770586409c1f6f74dabf19cbe7ec341ced
    [darwin_arm64]=d942f3ad147250c9edbaab3fed9e482f98d3b59ba10ae97b8d75647e3ade492c
)

gl=""
if command -v gitleaks >/dev/null 2>&1 && [[ "$(gitleaks version 2>/dev/null)" == *"$VER"* ]]; then
    gl="$(command -v gitleaks)"
else
    os="$(uname -s | tr '[:upper:]' '[:lower:]')"
    case "$(uname -m)" in x86_64|amd64) arch=x64 ;; aarch64|arm64) arch=arm64 ;; *) arch=unknown ;; esac
    key="${os}_${arch}"
    [[ -n "${SUMS[$key]:-}" ]] || { echo "check-secrets: no pinned gitleaks for $key" >&2; exit 2; }
    cache="${XDG_CACHE_HOME:-$HOME/.cache}/farglow/gitleaks-$VER"
    gl="$cache/gitleaks"
    if [[ ! -x "$gl" ]]; then
        mkdir -p "$cache"
        tgz="$cache/gitleaks.tar.gz"
        url="https://github.com/gitleaks/gitleaks/releases/download/v${VER}/gitleaks_${VER}_${key}.tar.gz"
        echo "check-secrets: downloading gitleaks $VER ($key)"
        curl -fsSL -o "$tgz" "$url" || { echo "check-secrets: download failed: $url" >&2; exit 2; }
        if command -v sha256sum >/dev/null 2>&1; then got="$(sha256sum "$tgz" | cut -d' ' -f1)"; else got="$(shasum -a 256 "$tgz" | cut -d' ' -f1)"; fi
        [[ "$got" == "${SUMS[$key]}" ]] || { rm -f "$tgz"; echo "check-secrets: checksum mismatch for gitleaks" >&2; exit 2; }
        tar -xzf "$tgz" -C "$cache" gitleaks && rm -f "$tgz"
    fi
fi

cd "$ROOT" || exit 2
rc=0
# Tracked + new files that are not ignored (so .env, backups/ and tls/ are never read).
list="$(mktemp -d)"
trap 'rm -rf "$list"' EXIT
git ls-files -z --cached --others --exclude-standard | while IFS= read -r -d '' f; do
    [[ -f "$f" ]] && mkdir -p "$list/$(dirname "$f")" && cp -p "$f" "$list/$f"
done
"$gl" dir --no-banner --redact --config "$ROOT/.gitleaks.toml" "$list" || rc=$?
if [[ "${1:-}" == "--history" ]]; then
    "$gl" git --no-banner --redact --config "$ROOT/.gitleaks.toml" "$ROOT" || rc=$?
fi
case $rc in
    0) echo "check-secrets: clean" ;;
    1) echo "check-secrets: SECRETS FOUND - remove them before committing" >&2 ;;
    *) echo "check-secrets: gitleaks failed (exit $rc)" >&2; rc=2 ;;
esac
exit $rc
