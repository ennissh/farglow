# Rapax patterns: what Farglow adopts

The house style comes from `ennissh/rapax-cloud` (read-only reference, studied 4 Nov 2026 at commit `ca01550`). Rapax is a different product: no Rapax code, text or history is copied into Farglow. This table records which **practices** Farglow follows.

**Adopt** = same practice. **Adapt** = same idea, changed for Farglow. **Reject** = not used. ⚠ = conflicts with a fixed Farglow decision; the Farglow decision wins and is flagged for review.

| # | Pattern | Where it lives in rapax-cloud | Farglow | Why |
|---|---|---|---|---|
| 1 | One directory per image, build context = repo root | `integration-*/`, CLAUDE.md "Container Conventions" | **Adapt** → `containers/<service>/` | Fixed Farglow decision. Shared code lives in `farglow/` and is copied in. Rapax's per-image `bin/`, `etc/`, `html/` aren't needed. |
| 2 | Base images pinned `tag@sha256` | `scripts/base-images.py`, CLAUDE.md | **Adopt** | `scripts/check-dockerfiles.py` enforces it. A `refresh` command (Rapax has one) is a Phase 0 follow-up. |
| 3 | Exact `==` pins for the whole dependency tree | CLAUDE.md "Python dependency pins" | **Adopt** | `scripts/check-pins.py` also enforces one version per package across every image. |
| 4 | Every pin has amd64 and arm64 wheels | `scripts/check-arm64-wheels.sh` | **Adapt** | Images install with `--only-binary=:all:`, so a missing wheel fails the arm64 build itself. A pre-flight wheel audit is a follow-up. |
| 5 | Non-root uid 1000; pid and socket files in `/tmp` | CLAUDE.md "Non-root" | **Adopt** | Python images run as `farglow` (1000). db and backup run as `postgres`, nginx as 101. Compose adds `read_only`, `cap_drop: ALL` and `no-new-privileges`. |
| 6 | No curl or wget in runtime images; Python health checks | CLAUDE.md, `check-healthcheck-tools.sh` | **Adopt**, with documented exceptions | Python images use `urllib` or a heartbeat-file check. The non-Python images (db, backup, nginx) use `pg_isready`, bash, or busybox `wget` from their base. Nothing is installed for this. |
| 7 | Remove pip from runtime images | `integration-skeleton/image/Dockerfile` | **Adopt** | Smaller attack surface; nothing installs at run time. |
| 8 | supervisord installed from pip, never apt | CLAUDE.md "Supervisor from pip" | **Adopt as a rule, unused** | Every Farglow service is one process. The rule applies if a service ever needs two. |
| 9 | Multi-arch `docker buildx`, every tag in one `--push`, `--local` loads the native platform | `installers/lib/build-helpers.sh` | **Adapt** → `build.sh` | One root script for all images instead of a `build-and-push.sh` per image. Same flags: `--local`, `--push`, `--no-cache`, `--version`. |
| 10 | Cython compilation, license and host-ID enforcement, debug-push guard | `build-helpers.sh`, `rapax-license/`, `rapax-hostid.sh` | **Reject** | Farglow is source-available under BUSL 1.1. There is no enforcement. |
| 11 | GHCR login retried with backoff, before the build | `build-helpers.sh` | **Adopt** (simplified) | `GHCR_USER`/`GHCR_TOKEN` login happens before the build, or an existing `docker login` is used. |
| 12 | SBOM and provenance attestations on pushed images | `build-helpers.sh` (`--sbom`, `--provenance`) | **Adopt** | Free with buildx. Cosign signing is deferred. |
| 13 | DNS inheritance into containers | `installers/lib/manifest-helpers.sh` | **Adopt** | `install.sh` detects the host's DNS servers. `mailer` and `llm-gateway` use them, so Ollama on the LAN or Tailscale resolves. |
| 14 | Release manifest pinned by digest (`releases/vX.Y.Z.manifest`) | `snapshot-release.sh`, `releases/` | **Adapt** | `build.sh --push` writes it directly. There is no separate tag/snapshot step, because Farglow builds each version once and never re-tags. |
| 15 | `tag-release`, `show-versions`, `upgrade-container`, `update-containers` | `installers/` | **Reject for now** | `install.sh` re-run with a new tag is the upgrade path (UPGRADE.md). Revisit at Phase 4 (upgrades). |
| 16 | GitHub Actions: changelog check, build-v2, scans | `.github/workflows/` | **Reject** ⚠ | Fixed decision: no GitHub-hosted CI. The same checks run in `./test.sh`, and `build.sh --push` refuses unless it passes and the tree is clean. |
| 17 | Layer-1 build checks before every push | TESTING.md §1, §8 | **Adopt** → `./test.sh` | Covers shellcheck, the container contract, pins, design tokens, gitleaks, the changelog check, and pytest (unit, determinism, database). |
| 18 | Layer-2 on-host suite in a throwaway test container, with a suite registry (`suites.json`: areas, requires, timeouts, `live_impact`, resource locks, `release_only`) and `report.html` + `summary.json` | `rapax-test/` | **Adapt, phased** | Phase 0 ships `tests/stack/stack-test.sh`: an isolated `farglow-test` project running install → tick → backup → wipe → restore. The `farglow-test` container and its registry come in Phase 1 (TESTING.md). |
| 19 | Test-host gating for scale, concurrency and active ZAP | TESTING.md §4.3 | **Adopt (planned)** | Same rule: the operator marks a host, it is never set automatically, and it is audited. Needed when scale and security suites arrive. |
| 20 | Test data prefixed and cleaned up, SMTP sink, mail loopback | `rapax-test/lib/`, TESTING.md §10 | **Adopt** | `tests/lib/smtp_sink.py` exists. A prefix rule (`ftest-`) is added when the test container arrives. |
| 21 | Keep a Changelog + SemVer + the `[Unreleased]` rule | CHANGELOG.md, `scripts/check-changelog.py` | **Adopt, stricter** | Farglow's check also requires the `[Unreleased]` section to have entries. It runs locally, not in CI. |
| 22 | Version marker in RELEASE.md | RELEASE.md `RAPAX_RELEASE_VERSION` | **Adapt** → `VERSION` file | One plain file that build scripts and images read. |
| 23 | gitleaks blocks the build; narrow allowlists only | `.gitleaks.toml`, `scripts/check-secrets.sh` | **Adopt** | Pinned gitleaks with a verified SHA-256. Scans tracked and new files, never ignored ones. |
| 24 | Image and repo vulnerability scans (Trivy, pip-audit, Bandit) | `scripts/v2-scan.sh` | **Adapt, later** | Phase 0 exit needs "dependency and static scans in `test.sh`". Proposal: add pip-audit and Bandit to `test.sh`, and Trivy to `build.sh --push`. |
| 25 | Encrypted credentials vault (Fernet, key from machine-id + hostname) | CLAUDE.md "Credentials Vault" | **Decision for owner** | Farglow uses `.env` (mode 600) by fixed decision. The code accepts `<NAME>_FILE` (Docker secrets) to keep a later move open. Trade-offs are in the decision log, D-0003. |
| 26 | Scaffold for new components | `scripts/new-integration.sh`, `integration-skeleton/` | **Adopt** → `scripts/new-service.sh` | Produces a service that passes the container contract on day one. |
| 27 | Big CLAUDE.md holding history and incident notes | CLAUDE.md (≈200 KB) | **Reject** | Farglow's CLAUDE.md holds conventions and pointers only (< 400 lines). History goes in CHANGELOG.md and the decision log. |
| 28 | "Common issues" entries: Symptom / Root cause / Fix / Prevention | CLAUDE.md | **Adopt** (in `docs/troubleshooting.md` once there are entries) | It's a good format, but it belongs in docs, not CLAUDE.md. |
| 29 | PLAN.md backlog tables with stable numbers; dated owner decisions; resolved items struck through, not deleted | PLAN.md | **Adopt** | Farglow's PLAN.md open-items table plus `docs/specs/decisions-*.md`. |
| 30 | TESTING.md metadata table, standalone for operators | TESTING.md | **Adopt** | |
| 31 | LICENSES.md (third-party inventory) | LICENSES.md | **Adapt** → `THIRD_PARTY_NOTICES.md` | Rapax's version numbers had gone stale, so Farglow's is checked against the pins at release time (RELEASE.md checklist). |
| 32 | Transactional install, rollback asked and never automatic | CLAUDE.md "v2 Install Cycle" | **Adapt** | `restore.sh` always takes a safety backup first and restarts paused. Install-time rollback arrives with upgrades (Phase 4). |

## Conflicts flagged

- **#16 CI:** Rapax relies on Actions for its changelog gate and builds. Farglow replaces both with local scripts. The risk is that a contributor skips `./test.sh`. The mitigation is that only `build.sh --push` publishes, and it runs the tests itself.
- **#25 secrets:** see decision D-0003. Not adopted silently.
- **#6 health-check tools:** three non-Python images can't follow "Python health checks" literally. The exceptions are listed in `CLAUDE.md`.
