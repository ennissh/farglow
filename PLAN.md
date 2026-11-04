# Farglow plan: blank repo to `v1.0.0`

This plan takes Farglow from an empty repository to its first public release. There are three proofs of concept (PoCs) on the way, each a tagged, playable release. Each phase lists its **scope**, its **exit criteria**, and the **tests that must pass** before the next phase starts.

> **No dates yet.** Phase sizes are relative (S / M / L / XL), because team size and hours per week haven't been decided. Once they are, this plan gets a calendar. Each phase ends when its exit criteria pass, not on a date.

| Phase | Release | Size | Theme |
|---|---|---|---|
| 0 · Foundations | `v0.0.x` | M | The empty stack installs, runs, ticks, backs up and restores |
| 1 · First Light | `v0.1.0` | L | One civilization, a full day-one-to-day-80 economy, the advisor, the Dispatch |
| 2 · First Contact | `v0.2.0` | XL | Other civilizations: diplomacy, combat, guilds, messaging and moderation |
| 3 · The Wide Galaxy | `v0.3.0` | L | Real-scale galaxy, placement, naming, Galactic Events, host operations, scale |
| 4 · Beta | `v0.9.x` | L | Hardening: security, self-host polish, migrations, legal, outside playtest |
| 5 · Release | `v1.0.0` | S | Release criteria met; public repository and farglow.gg |

---

## Ground rules for every phase

- **Definition of done:**
  - The code is merged.
  - Tests are written and passing in `test.sh`.
  - The config is in `config/*.yaml`, not hard-coded.
  - The docs and the decision log are updated.
- **Determinism is never broken.** Every engine change keeps the replay test green: same seed and orders, same state hash.
- **AI is optional at every step.** Each feature must work at tier T0 (no AI) before it gets an AI-enhanced version.
- **Balance is measured, not guessed.** Any change to an economy number re-runs `tools/sim.py` against the pacing targets.
- **Releases:**
  - `build.sh` tags each release as `VERSION` + git hash.
  - `test.sh` must pass before `--push`.
  - Images are multi-arch (amd64 and arm64).
  - There is no GitHub Actions CI.
- **Every release is installable from scratch** on a clean Ubuntu 26.04 VPS with `install.sh`, and **upgradable** from the previous release with a real backup.

---

## Phase 0 · Foundations → `v0.0.x` (M)

> **Status (4 Nov 2026):** items 1–4 and 6 are built, as is the outbound part of 7 (SMTP, signed single-use links, the `install.sh` test send). `./test.sh --stack` passes the backup → wipe → restore hash check. Items 5 (accounts) and 7's link pages, plus a clean-VPS install, remain. See `CHANGELOG.md`.

**Goal:** a working, empty stack. Nothing fun yet, but everything after it builds on solid ground.

**Scope**
1. **Repository:**
   - layout from the README
   - `VERSION`
   - `.env.example`
   - `config/` holding the five PoC YAML files
   - `docs/` holding the advisor spec and the decision log
   - `tools/` holding `sim.py`, the tech-tree builder and the art build scripts
2. **Containers:** one `containers/<service>/Dockerfile` each for nginx, api, tick, worker, db, migrate, llm-gateway, mailer and backup. `compose.yaml` wires them together.
3. **Scripts:**
   - `build.sh` (`--local`, `--push`, multi-arch)
   - `install.sh` (asks for domain, admin, image source, AI tier, SMTP; writes `.env`)
   - `test.sh`
   - `backup.sh` / `restore.sh` (single `.tar.gz`; secrets only with `--with-secrets`; restore starts paused)
4. **Platform:**
   - Flask app skeleton with Jinja + htmx and the design system CSS
   - migrations
   - Postgres job queue
   - structured logging
   - health endpoints
5. **Accounts:**
   - sign-up with stated age (month and year; under-13s refused; under-18 rules flagged)
   - email verification
   - sign-in
   - account deletion
6. **Tick engine skeleton:**
   - hourly clock (5 minutes in `DEBUG`)
   - pause and resume
   - restore point each tick
   - state hash
7. **Mail:** outbound SMTP, signed single-use links, and a test send from `install.sh`.

**Exit criteria**
- [ ] `./install.sh` on a clean Ubuntu 26.04 VPS brings the whole stack up healthy, using both GHCR images and local builds.
- [ ] Sign-up → verify email → sign in → delete account works end to end.
- [ ] Empty ticks run on schedule; pause and resume work; a restore point is written each tick.
- [ ] `backup.sh` → wipe → `restore.sh` gives an identical state hash.

**Tests:** unit (platform, api); functional (sign-up, account deletion, backup/restore round trip); determinism (empty-galaxy hash); security baseline (dependency and static scans in `test.sh`).

---

## Phase 1 · First Light → `v0.1.0` (L)

**Goal:** one player and one civilization, playable from day one to the end of the tech tree, five minutes a day.

**Scope**
1. **Galaxy (single cell):**
   - seed-based generation of one 10 pc cell
   - surveying
   - fog of war
   - the Galaxy map (interactive JS) and the System view, using procedural planets and building chips
2. **Civilization:** founding flow, 32 civilization sets, six attributes, starting state from `balance.poc.yaml`.
3. **Economy:**
   - population → action credits → allocation
   - minerals, energy, research, stability, reputation
   - mineral storage cap
4. **Research:** the 32-node PoC tree with drawbacks, doctrines, knowledge tax and repeatables. Research screen.
5. **Expansion and building:** outposts, colonies, in-system claims, 9 building types, 12-tick build time, Colony screen.
6. **Charters:** board, slots, holding, light penalties, retry wait. Tutorial Charters can't fail.
7. **Advisor:**
   - setup (name, traits, backstory, or AI-generated)
   - the *First Light* walkthrough
   - Codex Q&A with a JSON output schema
   - "act after confirm"
   - AI activity log
   - tiers T0 and T2
8. **Codex:** the 20 authored articles PoC 1 needs.
9. **Dispatch:** in-game news and the morning email, with decisions you can act on through signed links.
10. **Settings:** profile, theme, swearing filter (on by default; locked on for under-18s), email preferences.

**Exit criteria**
- [ ] `sim.py` and a real game both hit the pacing targets:
  - first tech on day 1
  - first new system on days 2–4
  - first colony on days 4–8
  - Lattice open by days 10–16
  - Concord open by days 40–60
  - tree complete by days 80–110
- [ ] The mineral pile-up around day 50 is solved: building upgrades or a sink chosen and simulated.
- [ ] The advisor answers its top 25 questions correctly, citing the Codex, at T0 (templates) and T2 (Ollama).
- [ ] At least 5 internal playtesters play 2 weeks at about 5 minutes a day and say the morning Dispatch is enough to play.

**Tests:** functional (simple start: first 10 ticks; the advisor's top 25; Dispatch link safety); balance regression; advisor evaluation set (grounded answers only); determinism with stored AI outputs.

---

## Phase 2 · First Contact → `v0.2.0` (XL)

**Goal:** a shared galaxy: other players, AI rivals, and everything that happens when they meet.

**Scope**
1. **Multiple civilizations** in one cell: players plus one NPC rival per player. NPC behaviour is engine-driven, with AI used for flavour.
2. **Diplomacy:**
   - first contact
   - treaties: trade, non-aggression, research, alliance
   - breaking treaties (reputation −15 globally, −40 with the victim)
   - Diplomacy screen
3. **Fleets and combat:**
   - hulls, tonnage, upkeep, readiness, command lag
   - Fleet orders screen
   - Lanchester attrition battles
   - sieges
   - **combat simulated and balanced** (not done yet)
4. **Triumphs:** the 7 PoC Triumphs, each calibrated in the simulator (only *The Bright Ascent* is calibrated today). Permanent bonus categories with caps.
5. **Messaging and moderation:**
   - direct messages and guild chat
   - optional email delivery (never for under-18s)
   - checks before delivery: word lists, a classifier by AI tier, hold/block decisions
   - conduct ladder with reputation hits
   - appeals
   - host moderation queue
6. **Guilds:** invitations, a soft cap of 12, bonuses, guild projects, guild treaties.
7. **Email Q&A:** reply to the Dispatch to ask the advisor (questions only).
8. **Host admin overview:** players, moderation, tick engine, services, backups.

**Exit criteria**
- [ ] Two civilizations can fight to the death, deterministically, and the result matches the simulator.
- [ ] A 10-player internal server runs 3 weeks with NPC rivals, without manual fixes to the database.
- [ ] The moderation test set passes: the target block rate for abuse is hit and false positives stay below the agreed threshold. These thresholds are tuned with real data before any public use.
- [ ] Triumph targets are hit by focused civilizations and missed by unfocused ones, with about 20% margin.

**Tests:** functional (two-civilization combat to the death; diplomacy flows; message → moderation → delivery); moderation test set; determinism with multiple civilizations; security (authorization between civilizations; no fog-of-war leaks through the API or the advisor).

---

## Phase 3 · The Wide Galaxy → `v0.3.0` (L)

**Goal:** the real-scale galaxy, ready for many players, and the tools a host needs to run it.

**Scope**
1. **Galaxy structure** (`galaxy.poc.yaml`):
   - galactocentric frame
   - sector → subsector → cell
   - real stellar density model (disk, bar and bulge, arms, open clusters)
   - lazy generation
   - address format `41-07-02`
2. **Placement:**
   - the host picks the first cell in the Setup wizard (default: Sol's position)
   - players choose hyper-dense, medium or remote
   - breathing room
   - the next cell opens at 80% density
3. **Naming:** the first player civilization to survey a system names it; moderated; galactic catalogue credit.
4. **Galactic Events:** the Grey Bloom plague, with coalitions (temporary event guilds), a shared research pool, spread along trade lanes, and loss reduced by mitigation, then a recovery wave.
5. **Host operations:**
   - health and capacity ("room for players")
   - galaxy density
   - **rollback to a tick** (pause or replay mode; cancels email links issued after the restore point; tells players)
   - bans
   - log viewer and download
   - admin audit log
6. **Self-host Setup wizard:** the full first-run flow.

**Exit criteria**
- [ ] **Scale test:** 500 NPC civilizations plus a simulated concurrent-player load stay within the tick budget (p95 tick < 30 s) on the reference VPS (8 vCPU, 16 GB).
- [ ] Rollback in both modes gives the expected state hash, and players see the notice in the next Dispatch.
- [ ] The Grey Bloom completes on a test server, in both its success and failure branches.
- [ ] Cell generation is deterministic across machines and architectures (amd64 vs arm64).

**Tests:** scale (concurrency, 500 NPCs, galaxy generation); functional (rollback; ban; naming; event); determinism across architectures.

---

## Phase 4 · Beta → `v0.9.x` (L)

**Goal:** safe, stable and pleasant enough for strangers to self-host.

**Scope**
1. **Security testing:** OWASP ZAP against a staging server, an OWASP Top 10 review, static code scanning, secrets review, rate limits, signed-link expiry and replay. Fix everything rated high or critical.
2. **Upgrades:** migrations from `v0.3` using real backups; documented upgrade path; version compatibility checks in `restore.sh`.
3. **Self-host polish:**
   - `install.sh --non-interactive`
   - email deliverability guide (SPF, DKIM, DMARC)
   - AI tier guide
   - troubleshooting guide
4. **Legal:**
   - the license reviewed by a lawyer
   - trademark search on "Farglow" and the F-Horizon mark
   - Terms of Service and privacy policy templates for hosts and for the official server
   - COPPA and UK Online Safety Act review of the age and messaging rules
   - CLA for contributors
5. **Outside playtest:** one hosted beta server with invited players, and at least one community host running their own server.
6. **Performance and cost:** AI usage per tier per player per day, email volume, database growth.

**Exit criteria**
- [ ] No open high or critical security findings.
- [ ] Two consecutive beta releases upgrade cleanly from the one before.
- [ ] An outside host installs from the docs alone, without help.
- [ ] The legal items above are signed off.

---

## Phase 5 · Release → `v1.0.0` (S)

**Release criteria**
- [ ] Every phase's exit criteria still pass on the release candidate.
- [ ] `README.md`, `LICENSE.md`, `CONTRIBUTING.md`, `THIRD_PARTY_NOTICES.md` and the trademark policy are final.
- [ ] Images published to GHCR, the repository made public, farglow.gg live with install docs.
- [ ] Release notes and a known-issues list.

---

## After `v1.0`

Each item gets its own design pass first.

- **Transcendence and lineage** (Starfield-style New Game+): lineage perks with a cap, an heirloom, Elders, a speed floor for later runs. Friendships and guilds carry over.
- **Honors and Titles**, verified only on official servers.
- **Seasons**, one per quarter per server, shipped as content packs; hosts can turn them off.
- **Wormholes:** long-range links opened by late tech or Galactic Events.
- **Exotics:** a strategic resource.
- **Mobile**, **localization**, **accessibility**.

---

## Open items to settle (and the phase that needs each)

| Item | Needed by |
|---|---|
| Team size and weekly hours (to put dates on this plan) | Phase 0 start |
| Legal review of `LICENSE.md` (BUSL 1.1 + free-hosting grant); CLA wording | Before the repository goes **public**; CLA before the first outside contribution |
| Trademark search: "Farglow" and the F-Horizon mark | Phase 4, ideally sooner |
| Mineral sink after day 50 (building upgrades?) | Phase 1 |
| Codex: 20 articles written | Phase 1 |
| Advisor open decisions (memory retention, daily limits per tier) | Phase 1 |
| Doctrine per tier: confirm the assumed one-of-three lock | Phase 1 |
| Combat balance (not yet simulated) | Phase 2 |
| Calibrate the other 6 Triumphs | Phase 2 |
| Moderation thresholds tuned on real data; age-assurance needs for the UK | Phase 2 / Phase 4 |
| Naming rules: confirm the proposed defaults (72-tick window, 2–24 characters, no real people) | Phase 3 |
| Design-pack specs missing from the upload: advisor spec, the 3 Nov decision log, tech-tree PDF (`docs/specs/` was to hold them) | Phase 0 (now) |
| Secrets storage: keep `.env`, Docker secrets files, or an encrypted vault (decision D-0003) | Before beta (Phase 4) |
| Tick catch-up after downtime: one tick then re-align (proposed D-0006), or replay every missed tick | Phase 1 |
| TLS automation (Let's Encrypt): certbot sidecar vs documented external proxy (D-0015) | Before any public server |
| Layer-2 `farglow-test` container + suite registry (TESTING.md §4) | Phase 1 start |
| Dependency and static scans in `test.sh` (pip-audit, Bandit) and Trivy in `build.sh --push` | Phase 0 exit |
| Verify `install.sh` on a clean Ubuntu 26.04 VPS, with GHCR images (needs a first `build.sh --push`) and with a local build | Phase 0 exit |
| GHCR package visibility while the repo is private (hosts need `docker login`, or images public) | First push |
| Exotics timing | After 1.0 |
| Transcendence length and lineage rules | After 1.0 |
