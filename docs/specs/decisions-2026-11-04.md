# Decision log: 4 November 2026 (Phase 0 groundwork)

Continues the design pack's decision log of 3 Nov 2026. That file was **not in the uploaded pack** (see open question Q1), so this log starts at D-0001.

**Status values:**
- **DECIDED** (by the owner);
- **PROPOSED** (made while building, awaiting review; easy to reverse);
- **OPEN** (needs the owner).

| ID | Decision | Status | Notes |
|---|---|---|---|
| D-0001 | The fixed decisions in the kickoff brief: no hosted CI; root scripts; `containers/<service>/`; Python, Flask and Postgres 16 only; BUSL with no enforcement; a deterministic engine; English only; a lean CLAUDE.md | DECIDED | Owner, kickoff brief |
| D-0002 | `uninstall.sh` is a sixth root script. The default keeps data and `.env`; `--purge` deletes them after offering a final backup and asking you to type `delete farglow` | PROPOSED | Owner asked for `uninstall.sh`; the safe default is a proposal |
| D-0003 | **Secrets stay in `.env` (600).** Rapax's encrypted vault (Fernet, key from machine-id + hostname) is *not* adopted. The code also accepts `<NAME>_FILE` (Docker secrets), so moving later needs no code change | OPEN | Vault pros: secrets aren't in plain text on disk or in `docker inspect`. Cons: key tied to the host (breaks moves and restores; Rapax needs a re-encrypt command), more code, and the "key" sits on the same disk. **Recommendation:** keep `.env` for now; consider Docker secrets files (`secrets/*.txt`, 600) before beta so values leave `docker inspect` |
| D-0004 | Python **3.13** (README says 3.12+) | PROPOSED | Current stable slim image; all pins have wheels |
| D-0005 | **Fonts and htmx are self-hosted** in `static/`, not loaded from Google Fonts or a CDN | PROPOSED | Privacy (players' IPs don't go to Google), a strict CSP (`'self'` only), works offline. The design-system README says Google Fonts; this departs from it |
| D-0006 | **Tick catch-up:** after downtime the engine runs **one** tick and re-aligns; it doesn't replay the missed hours | PROPOSED | Players shouldn't wake to 8 ticks at once. Owner to confirm (it affects game pacing) |
| D-0007 | Ticks align to interval boundaries (top of the hour; :00/:05/… in DEBUG) | PROPOSED | Predictable "next tick in 42 min" |
| D-0008 | Engine state is JSON with **integers only** (floats raise); randomness only via `rng(seed, *keys)` from SHA-256 | PROPOSED | Determinism across amd64/arm64 (PLAN Phase 3 exit) |
| D-0009 | Restore points stored as full state snapshots in Postgres (`restore_points`, newest 72) | PROPOSED | Tiny in Phase 0. Revisit (deltas or partitioning) when the galaxy has real state (Phase 1/3 scale) |
| D-0010 | `restore.sh` takes a safety backup, checks the restored tick and hash against the manifest, runs migrations, and **always restarts paused** | DECIDED (brief) + PROPOSED details | |
| D-0011 | Backup format `farglow-backup/1`: `db.dump` (pg_dump -Fc), `config/`, `VERSION`, `manifest.json` (SHA-256 per file), optional `secrets.env.enc` (openssl AES-256-CBC, PBKDF2 600k iterations) | PROPOSED | openssl is on every Ubuntu host; age/gpg are alternatives. CBC has no built-in integrity, but the manifest SHA-256 covers the file and a wrong passphrase fails the padding check |
| D-0012 | Nightly `pg_dump` in the `backup` service (03:00 UTC, keep 7) in addition to per-tick restore points | PROPOSED | README: "restore points every tick … and nightly backups" |
| D-0013 | `build.sh --push` also needs a clean git tree, refuses to overwrite a published `X.Y.Z` (unless `--force`), and writes `releases/vX.Y.Z.manifest` | PROPOSED | Reproducible, immutable releases without CI |
| D-0014 | Image tags: `X.Y.Z`, `X.Y.Z-<git12>`, `latest`; local builds tag `:local`. `FARGLOW_BUILD=X.Y.Z+<git12>` inside the image | PROPOSED | PLAN: "tags each release as VERSION + git hash" |
| D-0015 | TLS: nginx serves HTTPS when `tls/fullchain.pem` + `privkey.pem` exist, else HTTP. **No Let's Encrypt automation yet** | OPEN | Options: certbot sidecar, Caddy instead of nginx (conflicts with the nginx decision), or document an external proxy. Needed before any public server |
| D-0016 | The db image runs Postgres as the `postgres` user (not root via gosu); all images use compose hardening (`no-new-privileges`, `cap_drop: ALL`, read-only root for Python) | PROPOSED | |
| D-0017 | `install.sh --non-interactive` (answers from `FARGLOW_*` env) exists now, earlier than PLAN Phase 4 | PROPOSED | The stack test needs it |
| D-0018 | The PG job queue: `jobs` table, `FOR UPDATE SKIP LOCKED`, `LISTEN/NOTIFY` wake-up, exponential backoff, `dead` after `max_attempts`, stale requeue after 15 min, optional `dedupe_key` | PROPOSED | |
| D-0019 | Email links: HMAC-SHA256 token + nonce row; single-use via an atomic `UPDATE … RETURNING`; revocable by tick (for rollback) | PROPOSED | README email-safety rules |
| D-0020 | The design pack is unpacked from the uploaded `design/` folder (no zip existed). The two identical `farglow-art.js` copies become one in `static/art/`, plus a shim in `tools/art/` | PROPOSED | |

## First playable demo (PoC 1 slice), later on 4 Nov 2026

| ID | Decision | Status | Notes |
|---|---|---|---|
| D-0021 | **Everything a player does is an order for the next tick.** The API checks it against the current state (instant feedback) and the tick checks it again. The `orders` table is the replay history and is never deleted, even when the account is | PROPOSED | Keeps "same seed + same orders = same hash" true for every feature. Orders keep the numeric user id; no email or name |
| D-0022 | **Engine schema 2** with a pure `game.step()`. Galaxies from 0.0.x (schema 1) upgrade through one recorded `engine.upgrade` order, so their old ticks still replay. `GOLDEN_V1` must never change | PROPOSED | Tested on a real DB (`test_a_0_0_x_galaxy_upgrades_in_place_and_still_verifies`) |
| D-0023 | **Fixed-point integers**: amounts ×1000, distances in milli-ly, rates in ppm; the YAML is converted exactly with Decimal. Integer square and n-th roots | PROPOSED | No float reaches the state (D-0008). Parity check: the engine's first tech lands on the same tick as `tools/sim.py` (tick 22) |
| D-0024 | **The galaxy is never stored**: the cell (85–115 systems in 32.6 × 32.6 ly, face-on) is generated from the seed. Only discoveries, ownership, names and buildings go in the state | PROPOSED | A 2D projection for the PoC: the distances players see are the ones the engine uses. Real 3D cells arrive in Phase 3 |
| D-0025 | **Home placement**: the first civ starts nearest the cell centre; each later civ takes the free system farthest from existing homes. Homes become a K or G star with the standard five bodies (rocky, verdant capital, gas giant, belt, ice) | PROPOSED | A simple stand-in for `galaxy.poc.yaml` placement (breathing room, density classes) |
| D-0026 | **Owning a system gives all its bodies' yields** (as `sim.py` does). Body-by-body claims (the mockup's "Outpost" and "Unclaimed" per body) are later | PROPOSED | |
| D-0027 | **Surveys**: systems within survey range are revealed for free. Beyond that, a survey mission costs 150 expansion AC and travels at fold speed. Surveys and ships reach 12 ly from your systems. New config keys: `expansion.survey_ac`, `survey_minerals`, `max_reach_ly`; `buildings.build_ticks: 12` | PROPOSED | Numbers to tune with `sim.py` |
| D-0028 | **Tutorial Charters**: first tech, first survey, first building, first outpost. They can't fail and each pays 400 minerals (`objectives…tutorial.reward_minerals`). `first_dispatch_reply` waits for email replies (Phase 2) | PROPOSED | |
| D-0029 | **Military AC builds hull automatically** (as in `sim.py`), and the fleet only costs upkeep until fleets and combat arrive in Phase 2 | PROPOSED | |
| D-0030 | **Development servers use the tech tree's `debug_cost_multiplier` (0.1)**, fixed into the galaxy at genesis, and every player gets an "Advance the clock" button. On production servers only the host admin has it | PROPOSED | So a demo reaches Lattice in a session. A production galaxy never changes this |
| D-0031 | **No SMTP means accounts are verified at sign-up** (a LAN server); with SMTP, email verification is required | PROPOSED | |
| D-0032 | **The Codex is data** (`config/codex.poc.yaml`, 15 short articles). At T0 the advisor quotes the best match, or lists its own suggestions for "what should I do" questions. At T1+ the model gets the matching articles and a fog-of-war summary and must answer as JSON; any failure falls back to T0. The full Q&A goes to `advisor_log` (the AI activity log) | PROPOSED | The PLAN asks for 20 Codex articles (open item); these 15 are a first draft for review |
| D-0033 | **Walkthrough step 7 is "Order your first building"**, not the mockup's "Set your standing orders" (standing orders aren't built yet) | PROPOSED | |
| D-0034 | **GETs never write, even bookkeeping**: walkthrough "seen" steps are a POST fired on page load; "last seen" updates only on POSTs | PROPOSED | Rule from README "Email safety" applied everywhere |
| D-0035 | **Sessions**: signed Flask cookie with a per-user `session_version` (bump it to sign someone out everywhere), CSRF token on every POST, scrypt password hashes (Werkzeug). No sign-in rate limit yet | PROPOSED · gap | Rate limiting is a Phase 4 security item; listed in PLAN open items |
| D-0036 | **Build numbering follows rapax-cloud.** `VERSION` = release line `X.Y.Z`. `./build.sh` pushes the next `X.Y.Z-N` (read from GHCR's tags) plus `:latest`; `--release` pushes `X.Y.Z` once. Numbers are always new and higher; a pushed number is reused only with `--replace-version` | DECIDED (owner, 4 Nov 2026) | Owner: "build needs to push too"; "automatically picking the next build with the current version". Supersedes D-0013/D-0014's tag list |
