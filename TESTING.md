# Testing Farglow

| | |
|---|---|
| **Applies to** | Farglow `0.0.x` (Phase 0) onwards |
| **Status** | Layer 1 and the stack test are built. The `farglow-test` container (layer 2) is planned for Phase 1. |
| **Audience** | Developers, release managers, self-hosters checking their install |
| **Source of truth** | `test.sh`, `pytest.ini`, `tests/`, and (from Phase 1) `farglow-test/suites.json` |

There is **no hosted CI**. Testing happens in two layers, and the first one gates every release: `./build.sh --push` runs `./test.sh` and refuses to push if it fails.

## 1. Overview: two layers

| Layer | Where | What | When |
|---|---|---|---|
| **1. Local checks** (`./test.sh`) | Developer machine; needs no running server | Lint, contracts, pins, secrets, changelog, unit, determinism and database tests | Before every push; always before `build.sh --push` |
| **2. On-host suite** (`farglow-test` container) | An installed Farglow server | Functional, balance, scale and security suites against the live stack | After install or upgrade, before a release, and on demand |

The **stack test** (`./test.sh --stack`) bridges the two layers. It builds the images, installs an isolated copy of the stack (project `farglow-test` on ports 18080/18443), and runs the Phase 0 round trip on real containers.

## 2. Recommended regime

| Occasion | Command | Pass criteria |
|---|---|---|
| Every commit or push | `./test.sh` | All checks green |
| Without Docker (laptop, train) | `./test.sh --quick` | Green; DB tests skipped |
| Change to containers, scripts, compose, backup/restore | `./test.sh --stack` | Round trip identical |
| Release | `./build.sh --push` (runs `./test.sh`) + `./test.sh --stack` | Both green; see RELEASE.md |
| After installing or upgrading a server | `docker compose ps` (all healthy) + `docker compose exec tick python -m farglow engine verify` | Healthy; `OK` |

## 3. Layer 1: `./test.sh`

Checks run in this order. All of them run even if one fails, and the summary lists each failure.

| Check | Tool | Fails when |
|---|---|---|
| shellcheck | `shellcheck -S warning -x` on every tracked `*.sh` | Any warning |
| Dockerfile contract | `scripts/check-dockerfiles.py` | Unpinned `FROM`, root `USER`, no `HEALTHCHECK`, curl/wget installed, pip not wheels-only or not removed, a COPY outside the allowed paths, or the service missing from `compose.yaml` |
| Dependency pins | `scripts/check-pins.py` | A requirement not pinned with `==`, or the same package pinned at different versions in different images |
| Design tokens fresh | `tools/design/build_tokens_css.py --check` | `tokens.css` doesn't match `tokens.json` |
| Secrets | `scripts/check-secrets.sh` (pinned gitleaks with a verified SHA-256) | Any finding in tracked or new files |
| Changelog | `scripts/check-changelog.py` | Shipped files changed and `[Unreleased]` has no entry |
| Python compile | `compileall` | Syntax error |
| pytest | `tests/` | Any failure (JUnit XML goes to `test-reports/junit.xml`) |

**Toolchain:**
- `test.sh` creates `.venv-test` from `requirements-dev.txt` (exact pins) plus `shellcheck-py`, and rebuilds it when that file changes.
- Database tests run against a throwaway `postgres:16` container started from the **same digest** as `containers/db`. Each test gets a fresh, migrated database.

### Test suites in `tests/`

| Suite | Path | Covers today | Grows into |
|---|---|---|---|
| Unit: platform | `tests/unit/test_config.py`, `test_links.py`, `test_migration_files.py`, `test_mail.py` | Settings, signed links (tamper, expiry, purpose), migration naming, SMTP via an in-process sink | Accounts, age gate, moderation word lists |
| Unit: api | `tests/unit/test_api.py` | Health and readiness, security headers, 404, "no write routes on GET" | Every route, auth, CSRF |
| Unit: ai | `tests/unit/test_gateway.py` | T0 templates; T2/T4 fall back to T0 | Advisor JSON schema validation, evaluation set |
| Database | `tests/db/` | Migrations (idempotent, edited-file refusal), the job queue (SKIP LOCKED, retries, dead jobs, stale requeue), the tick engine (pause/resume, catch-up, pruning, tampering detected), single-use and revocable links | Every data path |
| Determinism | `tests/determinism/test_golden.py`, `tests/unit/test_state.py` | Same seed and orders give the same hash; golden hashes for seed 42; floats refused | Multi-civilization replays, rollback and replay, amd64 vs arm64 comparison |
| Stack | `tests/stack/stack-test.sh` | install → ticks → backup `--with-secrets` → `uninstall --purge` → fresh install → restore → identical tick and hash, verified replay, engine paused → resume | Upgrade from the previous release using a real backup |

Unit tests for the **ui** area (template rendering of each screen) start with the first Phase 1 screens.

## 4. Layer 2: the `farglow-test` container (Phase 1)

This is planned and not built yet. It follows the house pattern:

- **One throwaway container** (`containers/farglow-test/`, never part of a normal install), started by `./test.sh --host` on an installed server. It joins the stack's network and talks to nginx and the API like a player would.
- **Suite registry** `farglow-test/suites.json`, one entry per suite:
  - `id`, `title`, `areas` (`platform`, `api`, `ui`, `ai`, `functional`, `balance`, `scale`, `security`);
  - `cmd` (an argv list, never a shell string), `requires` (services), `timeout`;
  - `status` (`active`, `disabled` + `reason`, `deprecated`);
  - `live_impact` (a sentence saying what players would notice);
  - `resources` (locks such as `llm` or `exclusive`), `release_only`, `test_host_only`.
- **Gates:**
  - A suite whose required services are missing is SKIPPED, with the reason recorded.
  - `release_only` suites run only with `--profile release`.
- **Test hosts:** scale, concurrency and active ZAP scans run only on a host the operator has marked as a test system. The marker is set by hand from the command line, logged, and never set by install, restore or a job. The runner shows each suite's `live_impact` and asks before starting.
- **Test data safety:** everything a test creates is named `ftest-<run-id>-…`. Cleanup runs at start and at end, including on failure. Helpers refuse to delete anything without the prefix.
- **Mail:** an SMTP sink (`tests/lib/smtp_sink.py`) by default. On a real account, a loopback mailbox matched by a run-unique marker.
- **Reports:** `test-reports/<run-id>/report.html` (one self-contained page, light and dark, no scripts) and `summary.json` (schema `farglow-test-summary/1`: verdict, counts per area, skipped suites with reasons, versions, and per-check results). The last 20 runs are kept.

Planned suites, mapped to the README's test table:

| Area | Suite | Phase |
|---|---|---|
| functional | sign-up → verify → sign-in → delete account | 0 (needs accounts) |
| functional | backup/restore round trip on the live host (`live_impact`: engine paused briefly) | 0 |
| functional | simple start: first 10 ticks; the advisor's top 25 use cases; Dispatch link safety | 1 |
| balance | `tools/sim.py` pacing targets (first tech day 1 … tree complete days 80–110) | 1 |
| functional | two-civilization combat to the death; diplomacy; message → moderation → delivery | 2 |
| scale | concurrent players; 500 NPC civilizations; p95 tick < 30 s on 8 vCPU / 16 GB (test host only, release only) | 3 |
| determinism | cell generation identical on amd64 and arm64; rollback in both modes | 3 |
| security | OWASP ZAP baseline (passive) on any host; active scan on test hosts only; signed-link replay and expiry; authorization between civilizations; no fog-of-war leaks | 2–4 |

## 5. Security baseline

The Phase 0 exit needs "dependency and static scans in `test.sh`".
- **Built now:** gitleaks, pinned dependencies, CSP and security headers, and a test that no GET route writes.
- **Proposed next:** pip-audit against `requirements-dev.txt`, and Bandit on `farglow/`, both pinned in the test venv. Trivy image scans would run in `build.sh --push`.

## 6. Writing tests

- **Pure logic** goes in `tests/unit/`.
- Anything touching PostgreSQL goes in `tests/db/`, using the `pg_settings` fixture (a fresh migrated database), and is marked `pytestmark = pytest.mark.db`.
- An **intentional change to engine output** updates `tests/determinism/test_golden.py` in the same commit, with a CHANGELOG line.
- **No network** in layer 1: use the SMTP sink, and point AI tests at `127.0.0.1:1` to exercise the fallback.
- Behind a TLS-intercepting proxy, export `FARGLOW_BUILD_CA_FILE=/path/ca.pem` so the venv and image builds can reach PyPI.
