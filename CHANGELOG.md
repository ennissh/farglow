# Changelog

All notable changes to Farglow are recorded here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

**Rule:** every change to shipped code adds an entry under `## [Unreleased]` *before it is
pushed*. `./test.sh` runs `scripts/check-changelog.py` against `origin/main` and fails when
shipped files changed but this file did not. Top-level `*.md` files and `docs/` are exempt.
A release moves `[Unreleased]` into a dated `## [X.Y.Z] - YYYY-MM-DD` section and bumps `VERSION`.

Categories: Added, Changed, Deprecated, Removed, Fixed, Security.

## [Unreleased]

### Added
- **Phase 0 platform (`farglow/`).**
  - Settings from the environment, with `<NAME>_FILE` secrets.
  - JSON structured logging.
  - psycopg 3 helpers and service heartbeats.
  - Checksummed forward-only migrations (`migrations/0001_foundations.sql`).
  - A Postgres-native job queue: `SKIP LOCKED` claims, `LISTEN/NOTIFY` wake-up, backoff retries, dead jobs, stale requeue.
  - HMAC-signed single-use email links that can be revoked by tick.
- **Deterministic tick engine.**
  - A pure step function with an integer-only canonical-JSON state and a SHA-256 hash chain.
  - A seeded RNG helper.
  - The `tick` service: hourly, every 5 min in `DEBUG`, aligned to the interval, single engine via an advisory lock, one catch-up tick after downtime.
  - A restore point every tick (newest 72 kept), pause and resume, and replay verification (`engine verify`).
- **Services.**
  - Flask + Gunicorn `api`: `/healthz`, `/readyz`, `/api/v1/status`, and a server status page in the design system with htmx refresh, light and dark themes, and a strict `'self'` CSP.
  - `worker` and `mailer` consumers.
  - `llm-gateway` (T0 templates; T1/T2 Ollama, T3 an OpenAI-compatible API; T4 not yet available; always falls back to T0).
  - Operator CLI: `python -m farglow engine|queue|mail|migrate`.
- **Containers.**
  - `containers/<service>/` for nginx, api, tick, worker, db, migrate, llm-gateway, mailer and backup. Every base image is pinned by digest, dependencies are exact pins installed as wheels only, pip is removed, images run as non-root, and each has a health check.
  - `compose.yaml`: per-service environment, edge and core networks, and hardening (`no-new-privileges`, `cap_drop`, read-only roots).
  - Nightly `pg_dump` in the `backup` service.
- **Root scripts, each with `--help`:**
  - `install.sh`: interactive or `--non-interactive`; GHCR or local build; AI tier and endpoint; SMTP with a test send; DNS detection. It writes `.env` (mode 600), generates secrets, and never regenerates them.
  - `uninstall.sh`: keeps data by default; `--purge` deletes it after offering a final backup and asking you to type a confirmation.
  - `build.sh`: `--local`, or `--push` for multi-arch with SBOM and provenance. A push needs `test.sh` to pass and a clean tree, refuses to republish a version, and writes `releases/vX.Y.Z.manifest`.
  - `backup.sh` (`--with-secrets`, encrypted) and `restore.sh` (verify, safety backup, restore, migrate, hash check, restart paused).
  - `test.sh`.
- **Checks and tests.**
  - `scripts/check-dockerfiles.py`, `check-pins.py`, `check-changelog.py`, `check-secrets.sh` (pinned gitleaks), and `scripts/new-service.sh` with its skeleton.
  - 51 unit, database and determinism tests (golden hashes for seed 42).
  - `tests/stack/stack-test.sh`: install → tick → backup → wipe → restore gives an identical state hash.
- **Design system in the app.**
  - `tools/design/build_tokens_css.py` generates `static/ds/tokens.css` from `tokens.json`.
  - Self-hosted Inter Tight and IBM Plex Mono (OFL 1.1) and htmx 2.0.4 (0BSD).
- **Server status page screenshots** (`docs/design/poc-status-{light,dark}.png`).
- **Documents:** `CLAUDE.md`, `TESTING.md`, `RELEASE.md`, `UPGRADE.md`, `CONTRIBUTING.md`, `THIRD_PARTY_NOTICES.md`, `.env.example`, `VERSION`, `.gitignore`, `.dockerignore`, `.gitleaks.toml`, `docs/reference/rapax-patterns.md`, and the decision log `docs/specs/decisions-2026-11-04.md`.
- **Design pack unpacked into the repository layout.** Game configs to `config/*.poc.yaml`;
  `tools/sim.py`, `tools/techtree/` and `tools/art/`; mockups, explorations, brand and the
  design-system docs to `docs/design/`; tokens, `bundle.css` and SVG assets to
  `farglow/web/static/ds/`; the art library to `farglow/web/static/art/farglow-art.js`
  (one copy; `tools/art/farglow-art.js` is a shim so the build scripts still load it).
  Every file was checked by SHA-256 against the uploaded pack.

### Fixed
- `install.sh` no longer dead-ends when the chosen version isn't on GHCR (nothing has been pushed yet, or the packages are private).
  - The image-source default is "local" unless the version resolves on GHCR. A saved "ghcr" answer is checked again; an explicit `--source ghcr` is not.
  - When a pull fails, the interactive installer offers to build on this machine and records `FARGLOW_IMAGE_SOURCE='local'` in `.env`.
- The status page listed a service twice after its container was recreated (heartbeats are keyed by hostname); it now shows the latest heartbeat per service.

## [0.0.0] - 2026-11-04

### Added
- Repository created with `README.md`, `PLAN.md`, `LICENSE.md` (draft BUSL 1.1) and the design pack.
