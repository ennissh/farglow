# Releasing Farglow

Releases are **manual**. There is no CI: the person releasing runs `build.sh`, and `build.sh` runs the tests.

## Version marker
- `VERSION` (one line, SemVer `X.Y.Z` or `X.Y.Z-rc.N`) is the only version marker. Images, `install.sh` and backups all read it.
- Images carry `FARGLOW_BUILD=X.Y.Z+<git>` and OCI labels (version, revision, created, `licenses=BUSL-1.1`).

| Change | Bump |
|---|---|
| Breaking change for hosts (manual upgrade step, incompatible backup) | major (minor before 1.0) |
| New features, new migrations | minor |
| Fixes only | patch |

## Image tags
| Tag | Moves? | Made by |
|---|---|---|
| `X.Y.Z` | Never: `build.sh --push` refuses to overwrite it without `--force` | `build.sh --push` |
| `X.Y.Z-<git12>` | Never | `build.sh --push` |
| `latest` | Yes, unless `--no-latest` | `build.sh --push` |
| `local`, `X.Y.Z-<git12>` (local store only) | n/a | `build.sh --local` |

Images go to `ghcr.io/ennissh/farglow-<service>` for nine services, built for `linux/amd64` and `linux/arm64`, with SBOM and provenance attestations.

## Steps
1. **Prepare.** Make sure `main` is green, then on a release branch:
   - set `VERSION`;
   - move `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`, leaving a fresh, empty `[Unreleased]` above it;
   - update README "Current release";
   - check `THIRD_PARTY_NOTICES.md` against the pins.
2. **Merge** to `main`, then check out `main` with a clean tree.
3. **Stack test:** `./test.sh --stack` (install, backup, wipe, restore on real containers).
4. **Publish.** One-time setup on the build machine: `docker run --privileged --rm tonistiigi/binfmt --install all`, then:
   ```bash
   GHCR_USER=<user> GHCR_TOKEN=<token with write:packages> ./build.sh --push
   ```
   It refuses to run on a dirty tree, refuses if `./test.sh` fails, and refuses if `X.Y.Z` is already published. It writes `releases/vX.Y.Z.manifest`.
5. **Record:**
   - commit `releases/vX.Y.Z.manifest` (`Release vX.Y.Z`);
   - `git tag -a vX.Y.Z -m "Farglow X.Y.Z"`, then `git push origin main vX.Y.Z`.
6. **Verify from scratch** on a clean Ubuntu 26.04 VPS: `./install.sh --source ghcr --tag X.Y.Z`. Then upgrade a copy of the previous release using a real backup (UPGRADE.md).

## Manifest format (`releases/vX.Y.Z.manifest`)
```
# Farglow release vX.Y.Z
# Created: 2026-11-04T12:00:00Z
# Git-Commit: <full sha>
# Registry: ghcr.io/ennissh
# Platforms: linux/amd64,linux/arm64
#
# Format: service image:tag@sha256:digest (install with FARGLOW_IMAGE_TAG=X.Y.Z)
api farglow-api:X.Y.Z@sha256:…
```
- The digests are the multi-arch index digests.
- **Proposal (not built):** an `install.sh --manifest` that runs by digest instead of by tag.

## Pre-releases
Use `X.Y.Z-rc.N` in `VERSION` with `./build.sh --push --no-latest`, so `latest` stays on the last real release.
