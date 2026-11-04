# CLAUDE.md: working on Farglow

Conventions and pointers for anyone (human or agent) changing this repository. Keep this file **under 400 lines**: it holds rules, not history. History lives in `CHANGELOG.md`, decisions in `docs/specs/decisions-*.md`, plans in `PLAN.md`.

## Sources of truth (in priority order)
1. `README.md` (what Farglow is, its architecture and rules), `PLAN.md` (phases and exit criteria), `LICENSE.md`.
2. `docs/specs/decisions-*.md`: the decision log. Add new decisions there.
3. `docs/design/` (design pack: mockups, brand, design-system docs) and `config/*.poc.yaml` (game data).
4. `docs/reference/rapax-patterns.md`: which house-style practices we follow, and why.

If two sources disagree, **ask the owner**. Don't pick one.

## Fixed decisions (don't relitigate)
- **Stack:** Python 3.13 · Flask + Gunicorn · Jinja + htmx · vanilla-JS star map · **PostgreSQL 16 only**, with a Postgres-native job queue. No Redis, Kafka, OpenSearch or MariaDB. Docker Compose on Ubuntu 26.04 LTS.
- **No GitHub Actions / hosted CI.** `./test.sh` is the gate; `./build.sh --push` refuses to push unless it passes. GHCR is the registry.
- **No license enforcement,** host IDs, Cython or obfuscation. Source-available under BUSL 1.1.
- **The engine is deterministic:**
  - The same seed and orders give the same state hash.
  - AI only *proposes* JSON; the engine validates it and decides.
  - Every feature works at AI tier **T0**.
- **English only.** No accessibility work beyond the design system's colour contrast.
- **Secrets:** `.env`, mode 600, written by `install.sh`. Never in git, argv, logs or images.

## Layout
```
containers/<service>/   Dockerfile + healthcheck + requirements.txt, one per service:
                        nginx api tick worker db migrate llm-gateway mailer backup
farglow/                Python package (one codebase, every Python image copies it)
  config.py log.py db.py      settings from env, JSON logging, psycopg helpers
  migrate.py queue.py links.py schema migrations, PG job queue, signed single-use links
  engine/state.py             canonical JSON, state hash, advance() dispatch (schema 1 kept for replay)
  engine/game.py              PURE game rules for schema 2: validate(order) and step(state, orders)
  engine/rules.py galaxy.py   config YAML -> integers; the procedural cell (generated, never stored)
  engine/store.py             current state + queue_order/submit (the ONLY way to change the galaxy)
  engine/clock.py             tick service (python -m farglow.engine.clock)
  play/                       fog-of-war views, Dispatch text, the advisor (suggestions + Codex Q&A)
  api/auth.py api/game.py     accounts (age gate, verify link, sessions, CSRF) and the game pages
  api/ web/                   Flask app, Jinja templates, static (design system, art, fonts)
  worker/ mail/ llm/          job consumers, SMTP mailer, LLM gateway
  cli.py                      operator CLI: python -m farglow engine|queue|mail|migrate
migrations/NNNN_name.sql      forward-only, never edited once shipped (checksummed)
config/*.poc.yaml             game data (+ codex.poc.yaml): every number is data, never code
tests/unit|db|determinism|stack   see TESTING.md
tools/                  sim.py, techtree/, art/, design/build_tokens_css.py
scripts/                check-*.py|sh, new-service.sh, lib/common.sh (shared bash)
docs/                   design/, specs/, reference/
install.sh uninstall.sh build.sh test.sh backup.sh restore.sh   (each has --help)
```

## Containers (the contract `scripts/check-dockerfiles.py` enforces)
- `FROM image:tag@sha256:<index digest>`. Refresh digests on purpose, in their own commit.
- **Python images:**
  - `pip install --only-binary=:all:` from an exact-pinned `requirements.txt`, then `pip uninstall -y pip`.
  - Every pin needs amd64 and arm64 wheels.
- **Non-root final `USER`:** `farglow` (uid 1000) for Python, `postgres` for db and backup, 101 for nginx.
- A `HEALTHCHECK` on every image. Python images check in Python: `urllib` against `/healthz`, or the age of the `/tmp/farglow-heartbeat` file. **Never install curl or wget.**
  - Exceptions, because these images have no Python: db (`pg_isready`), backup (bash heartbeat), nginx (busybox `wget` from the Alpine base).
- Build context = repo root. COPY only from `containers/<svc>/`, `farglow/`, `migrations/`, `config/`, `VERSION`. `.dockerignore` allow-lists exactly these.
- **One process per container.** If a service ever needs two, use supervisord installed from **pip** (never apt), with pid and socket in `/tmp`.
- Compose hardening on every service: `no-new-privileges`, `cap_drop: ALL` (not db), `read_only` + tmpfs `/tmp` for Python services, json-file log rotation.
- **Environment variables:** each service gets only the variables it needs, mapped explicitly in `compose.yaml`. No shared `env_file`. Secrets may also come as `<NAME>_FILE`.
- **New service:** `scripts/new-service.sh NAME "Title"`. Then wire it into `compose.yaml` and `FARGLOW_SERVICES` in `scripts/lib/common.sh`.

## Engine rules
- **Every change to the galaxy is an order** (`store.submit`): validated by `game.validate` when queued and again
  when the tick applies it. Pages never write game state; GETs never write anything.
- `engine/state.py`, `game.py`, `rules.py`, `galaxy.py` stay **pure**: no I/O, clock, env or global RNG
  (rules are read from `config/` once; their hash is stored in the state).
  - State is JSON with **integers only**; floats raise `DeterminismError`.
  - Randomness only via `rng(seed, *keys)`.
- Each tick writes a `ticks` row (the hash chain) and a `restore_points` row (the newest 72 are kept). `engine verify` replays from genesis and must match.
- Changing the engine's output on purpose means updating `tests/determinism/test_golden.py` in the same commit, with a CHANGELOG line saying why.
- **Catch-up policy:** after downtime the engine runs one tick and re-aligns; it never bursts.
- **Pause/resume** is a row flag. `restore.sh` always leaves the engine paused.

## Web rules
- **A `GET` never changes anything.** Email actions use signed single-use links (`links.py`): `GET` shows a confirm page; the `POST` consumes the token.
- **CSP is `'self'` only:** no inline scripts or styles, no CDNs. htmx and the fonts are vendored under `static/`.
- **Compact density**: 12 px text, tables first, one-line rows, everything on one laptop screen (`tests/ui/budgets.json`). Floors: text 11 px, targets 24 px.
- **Design system:**
  - `static/ds/tokens.css` is generated from `tokens.json` (`python3 tools/design/build_tokens_css.py`); never edit it by hand.
  - Components are the `fg-` classes in `ds/components/bundle.css`.
  - Blue (`accent`) means you; orange (`signal`) means others.

## Database
- Every schema change is a new `migrations/NNNN_name.sql`. Each file runs in its own transaction, and `migrate` runs at every start. Never edit a shipped migration.
- **Job queue:** enqueue inside the producer's transaction (`queue.enqueue`).
  - Consumers use `queue.Runner`, which claims with `FOR UPDATE SKIP LOCKED` and wakes on `LISTEN farglow_jobs`.
  - Job handlers raise on failure; retries back off; jobs end `dead` after `max_attempts`.

## Scripts and logging
- Bash scripts:
  - `set -euo pipefail` and source `scripts/lib/common.sh`.
  - Usage is the header block between the `#####` rules (`print_usage`), and every script has `--help`.
  - shellcheck must be clean at `-S warning`.
- **Logs:** one JSON object per line on stdout (`farglow/log.py`). Pass context as `extra={...}`. Never log secrets (keys that look secret are redacted as a backstop).

## Testing (detail in TESTING.md)
- `./test.sh` before every push; `./test.sh --quick` without Docker; `./test.sh --stack` for the full install, backup, wipe and restore round trip; `./test.sh --ui` (headless browser: play-through, layout, density budgets) after any template, CSS or JS change.
- Behind a TLS-intercepting proxy, set `FARGLOW_BUILD_CA_FILE=/path/ca.pem` for `build.sh` and `test.sh`.

## Changelog, versions, git
- Every change to shipped files adds a `CHANGELOG.md` entry under `## [Unreleased]` before it's pushed (`scripts/check-changelog.py`). Top-level `*.md` and `docs/` are exempt.
- SemVer in `VERSION`. Images are tagged `X.Y.Z`, `X.Y.Z-<git>` and `latest`. Releases are manual (RELEASE.md).
- Small commits with clear messages. Run gitleaks (`scripts/check-secrets.sh`, part of `test.sh`) before every commit.
- One PR per item. Label gap-filling choices as **proposals** in the PR description.
- Never push to or change `ennissh/rapax-cloud`. It's a read-only reference, and nothing is copied from it without approval.

## Where to look
| Topic | File |
|---|---|
| Phases, exit criteria, open items | `PLAN.md` |
| Decisions | `docs/specs/decisions-*.md` |
| Tests, suites, gates | `TESTING.md` |
| Releasing | `RELEASE.md` · upgrading: `UPGRADE.md` |
| Settings | `.env.example` |
| Third-party licences | `THIRD_PARTY_NOTICES.md` |
