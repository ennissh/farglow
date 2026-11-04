# Releasing Farglow

Releases are **manual**. There is no CI: the person releasing runs `build.sh`, and `build.sh` runs the tests.

## Version marker
- `VERSION` (one line, SemVer `X.Y.Z` or `X.Y.Z-rc.N`) is the only version marker. Images, `install.sh` and backups all read it.
- Images carry `FARGLOW_BUILD=X.Y.Z-N+<git>` (a build) or `X.Y.Z+<git>` (a release), plus OCI labels (version, revision, created, `licenses=BUSL-1.1`).

| Change | Bump |
|---|---|
| Breaking change for hosts (manual upgrade step, incompatible backup) | major (minor before 1.0) |
| New features, new migrations | minor |
| Fixes only | patch |

## Builds and releases (the rapax-cloud numbering)

`VERSION` holds the **release line** (`X.Y.Z`). What gets pushed:

| Command | Pushes | When |
|---|---|---|
| `./build.sh` | the next build **`X.Y.Z-N`** and `:latest` | any time: N is picked automatically from the tags already on GHCR (`scripts/versions.py`: always new and higher) |
| `./build.sh --no-latest` | `X.Y.Z-N` only | to try a build on a test server (`./install.sh --tag X.Y.Z-N`) before players get it |
| `./build.sh --release` | **`X.Y.Z`** and `:latest`, plus `releases/vX.Y.Z.manifest` | once per release, after bumping `VERSION` to a new X.Y.Z |
| `./build.sh --dry-run` | nothing | shows the number the next push would use |
| `./build.sh --local` | nothing (local Docker, `:local`) | development; `install.sh --source local` uses it |

Rules every push follows: `X.Y.Z-N` sorts after `X.Y.Z` (builds are the fixes after a release). An existing number is never reused unless you pass `--version X.Y.Z-N --replace-version`. A `VERSION` behind the registry is refused, so bump it or pull. Every push needs a clean git tree and a passing `./test.sh`, and is built for `linux/amd64` and `linux/arm64` with SBOM and provenance attestations. Images inside carry `FARGLOW_BUILD=X.Y.Z-N+<git12>`.

Servers: `./install.sh` (GHCR) runs the release if it's published, else `latest`. To pin a build: `./install.sh --tag X.Y.Z-N`.

## Steps for a release
1. **Prepare** on a release branch:
   - set `VERSION` to the new `X.Y.Z`;
   - move `## [Unreleased]` in `CHANGELOG.md` to `## [X.Y.Z] - YYYY-MM-DD`;
   - update README "Current release";
   - check `THIRD_PARTY_NOTICES.md` against the pins.
2. **Merge** to `main`, then check out `main` with a clean tree. Run `./test.sh --stack`.
3. **Publish.** One-time setup on the build machine: `docker run --privileged --rm tonistiigi/binfmt --install all`, then `docker login ghcr.io`. Then run `./build.sh --release`.
4. **Record:**
   - commit `releases/vX.Y.Z.manifest`;
   - `git tag -a vX.Y.Z -m "Farglow X.Y.Z"`, then `git push origin main vX.Y.Z`.
5. **Verify from scratch** on a clean Ubuntu 26.04 VPS: `./install.sh --source ghcr --tag X.Y.Z`. Then upgrade a copy of the previous release using a real backup (UPGRADE.md).

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

## Trying a build before players get it
Run `./build.sh --no-latest`, install the printed `X.Y.Z-N` on a test server with `./install.sh --tag X.Y.Z-N`, then move `latest` by pushing the next build without `--no-latest`.
