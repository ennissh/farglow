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
- **First playable demo: PoC 1 "First Light" vertical slice.**
  - **Accounts.** Sign-up asks the month and year of birth; under-13s are refused, nothing is kept, and the browser is locked out for 24 hours. Email verification uses a signed single-use link (the GET shows a confirm page; only the POST verifies). Then sign-in, sign-out, settings (the Dispatch email on or off) and account deletion: the civilization retires at the next tick. The first account with `FARGLOW_ADMIN_EMAIL` becomes the host admin. Without SMTP, accounts are ready at once.
  - **Engine schema 2** (`farglow/engine/game.py`, `rules.py`, `galaxy.py`, `store.py`). A seeded galaxy cell of about 100 stars, never stored. Founding a civilization (name, one of 32 civ sets, six attributes summing to 0). The `tools/sim.py` economy in fixed-point integers: population → action credits → allocation; minerals, energy, stability, storage caps and energy shortage. The 32-node tech tree with drawbacks, doctrines, the knowledge tax and the half-done first tech. Survey missions, outposts and colonies that travel at fold speed, buildings with a 12-tick build time, body development, system naming by the discoverer, tutorial Charters, and fog of war.
  - **Every action is an order**, validated by the API and again by the tick (`engine/store.py`).
  - **Screens** from the mockups: landing and sign-in, founding, Galaxy (a vanilla-JS SVG star map plus the system panel), Governor, Research (tree, details, queue), the Meridian Dispatch, a First Light walkthrough rail, Charters, pending orders and host admin. Development servers get an "Advance the clock" button.
  - **The advisor**: rule-based suggestions, each with an order the player confirms in one click. Q&A from the Codex (`config/codex.poc.yaml`) at T0, or through the LLM gateway at T1–T3 with a fog-of-war summary and fallback to T0. Every answer is logged.
  - **The Dispatch**: each tick's events become news items, and a morning email goes out every `FARGLOW_DISPATCH_EVERY_TICKS` ticks (24, or 12 on development servers).
  - Migration `0002_accounts_and_game.sql`: users, the order sequence, `dispatch_items` and `advisor_log`.
  - Tests: 25 new ones, 78 in total. They cover parity with `sim.py` (the first tech lands on the same tick), order validation, missions, buildings, doctrines, fog of war, the advisor (T0, T2 and fallback), the 0.0.x upgrade path on a real database, and a functional run from sign-up through verification, founding, ticks, play, the Dispatch email, admin and deletion.

### Changed
- **New galaxies start at engine schema 2**, so `tests/determinism/test_golden.py` has new v2 golden values; this change is intentional. Galaxies from 0.0.x keep their schema-1 history (the `GOLDEN_V1` hashes are unchanged) and upgrade through one `engine.upgrade` order. **Upgrade note:** there is nothing to do; the tick service queues it.
- `config/balance.poc.yaml` gains `expansion.survey_ac`, `survey_minerals`, `max_reach_ly` and `buildings.build_ticks`. `config/objectives.poc.yaml` gains `charters.tutorial.reward_minerals`. All are marked proposed.
- The api, tick and worker images now carry `config/` and PyYAML 6.0.3.
- The header can wrap onto two rows on narrow windows instead of overflowing.
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
