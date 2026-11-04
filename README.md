# Farglow

**Every star counts.** *A Generative Distractions game.* · farglow.gg

Farglow is a grounded sci-fi 4X MMO you play in about five minutes a day. You guide a young civilization from its first steps into interstellar space across a galaxy of 100–400 billion procedurally generated stars, shared with friends and AI rivals.

The galaxy moves on an hourly clock whether you're watching or not. Each morning the **Dispatch** (an email, or the in-game news) tells you what happened overnight and which decisions are waiting. Your **AI advisor** helps with the rest. There is no winning: you explore, settle, trade, argue, ally, and one day transcend.

Farglow is self-hosted on the **Minecraft model**. Anyone can run a server for their friends or community at no charge. Running it as a paid service needs a commercial license; see [License](#license).

---

## Current release

| | |
|---|---|
| **Version** | `0.0.0`, pre-alpha. **First playable demo:** sign up, found a civilization, run its economy and research, survey, settle and build, with the advisor and the Dispatch. It's a PoC 1 vertical slice on the Phase 0 platform. |
| **Next release** | `v0.1.0` "First Light" (proof of concept 1): one civilization, the economy, research, colonies, the advisor walkthrough and the Dispatch email |
| **Roadmap** | [PLAN.md](PLAN.md): blank repo → PoC 1 → PoC 2 → PoC 3 → beta → `v1.0.0` |
| **Design pack** | Unpacked into `docs/design/`, `config/`, `tools/` and `farglow/web/static/` (index: [docs/design/README.md](docs/design/README.md)) |

---

## What you can do in Farglow

Features are listed by the release that delivers them (see [PLAN.md](PLAN.md)).

### PoC 1 · First Light (`v0.1`)
- **Found a civilization.** Name it, choose one of 32 civilization sets (emblem, colours, banner, ship livery), and set six attributes: curiosity, industry, growth, cohesion, martial, openness. Attributes run −3 to +3, must sum to 0, and each point is worth ±5%.
- **Run the economy.** Population produces **action credits**. You spend them across expansion, research, social, economic and military. Other resources: minerals, energy, research, stability and reputation.
- **Research.** The PoC tech tree has 32 nodes across three tiers (Reach, Lattice, Concord). Every node has a drawback, and each tier has one doctrine choice that locks out the alternatives. Research costs rise with how much you already know.
- **Settle systems and build** (MOO2-style System view): outposts and colonies; one of each of 9 building types per body; a 12-tick build time.
- **Meet your advisor.** You name it and give it traits and a backstory, or let the AI write one. It walks you through *First Light*, answers questions from the Codex (the rules handbook), and can act for you, but only after you confirm.
- **Read the morning Dispatch.** Everything that happened overnight, with decisions you can act on from the email through signed, single-use links.
- **Complete Charters.** Personal tasks with small rewards and light penalties. The tutorial Charters can't be failed.

### PoC 2 · First Contact (`v0.2`)
- **Meet other civilizations:** players, plus one AI rival per player. Fog of war means you, and your advisor, only know what your civilization has discovered.
- **Diplomacy:** treaties, trade, reputation (−100 to +100), and war.
- **Fleets and combat:** command lag, readiness, and deterministic battles.
- **Guilds and messaging:** player messages in-game and, optionally, by email. Every message is moderated before delivery.
- **Triumphs:** timed civilization feats. Every civilization can attempt them, and each grants a temporary boon plus a permanent bonus that caps out.
- **Ask your advisor by email:** reply to the Dispatch with a question.

### PoC 3 · The Wide Galaxy (`v0.3`)
- **A real-scale galaxy, generated lazily.** Sector (1 kpc) → subsector (100 pc) → cell (10 pc, about 100 systems near the Sun). Positions use galactocentric coordinates, with a real stellar density model.
- **Choose where to start:** a hyper-dense, medium or remote cell. The host picks the server's first cell.
- **Name what you find.** The first player civilization to survey a system names it, and the name stays in the galactic catalogue for good.
- **Galactic Events:** server-wide story arcs, such as the Grey Bloom plague, solved together through coalitions.
- **Host operations:** rollback to a tick, bans, capacity and density monitoring, logs.

### Later (after `v1.0`)
Transcendence and lineage (Starfield-style New Game+), Honors and Titles, seasons, wormholes, Exotics, mobile, localization, accessibility.

---

## Architecture

```
                 players (browser)            players (email)
                        │                          │
                 ┌──────▼──────┐            ┌──────▼──────┐
                 │    nginx    │            │   mailer    │◄── SMTP in/out
                 └──────┬──────┘            └──────┬──────┘
                        │                          │
                 ┌──────▼──────┐                   │
                 │     api     │ Flask + Gunicorn: Jinja/htmx pages, JSON API, JS star map
                 └──────┬──────┘                   │
                        │                          │
   ┌────────────┐ ┌─────▼──────┐  ┌─────────────┐  │
   │    tick    │ │     db     │  │   worker    │◄─┘   jobs: Dispatch, moderation, advisor, news
   │  engine    ├─►PostgreSQL 16◄──┤(PG job queue)│
   └────────────┘ └─────▲──────┘  └──────┬──────┘
                        │                │
                 ┌──────┴─────┐   ┌──────▼──────┐
                 │  backup    │   │ llm-gateway │──► Ollama (Mac Studio, over Tailscale)
                 └────────────┘   └─────────────┘    or the host's API key, or the Relay
```

| Service | Job |
|---|---|
| `nginx` | TLS, static files, reverse proxy |
| `api` | Flask app: server-rendered pages (Jinja + htmx), the JSON API, the interactive star map |
| `tick` | The **deterministic** simulation. Advances the galaxy every hour (every 5 minutes in `DEBUG`). |
| `worker` | Background jobs from a Postgres-native queue (no Redis): Dispatch emails, moderation, advisor answers, news |
| `db` | PostgreSQL 16: the single source of truth |
| `migrate` | One-shot schema migrations at install and upgrade |
| `llm-gateway` | One door to every AI tier, with fallback and logging |
| `mailer` | Outbound Dispatch email and inbound replies (questions to the advisor) |
| `backup` | Restore points every tick (kept 72 ticks) and nightly backups |

### Design rules the code must keep
- **The engine owns every number.** AI models only *propose* JSON, such as an advisor plan, a news story or a Charter's wording. The engine validates it, and the engine decides outcomes.
- **Determinism:** the same seed and the same orders produce the same galaxy. AI outputs are stored, so replays (and rollbacks with replay) give identical results.
- **Fog of war applies to the AI too.** The advisor only sees what your civilization knows.
- **Email safety:**
  - Links are signed and single-use.
  - A `GET` request never changes anything.
  - Email replies can only ask questions; actions need a link or a signed-in confirmation.
- **Nothing is stored until it's discovered.** Stars and planets are generated from `hash(galaxy_seed, cell_id)`, and planets are drawn from their seed.
- **Moderation runs on everything people or AI write:** messages, names (civilizations, systems, advisors), advisor answers, news.

### AI tiers (chosen by the host)

| Tier | What runs | Notes |
|---|---|---|
| T0 | No AI | Templates and word lists only. The game is fully playable. |
| T1 | Small local model | CPU-friendly |
| T2 | Strong local model | e.g. Ollama on a Mac Studio, reached over Tailscale |
| T3 | The host's own API key | Includes OpenAI's free moderation endpoint |
| T4 | Generative Distractions Relay | Paid |

### Technology
Python 3.12+ · Flask · Gunicorn · Jinja2 + htmx · vanilla JS star map · PostgreSQL 16 · Docker Compose · Ubuntu 26.04 LTS. Images are built for amd64 and arm64, and published to GHCR or kept local. There is no GitHub Actions CI: `test.sh` gates every push by `build.sh`.

---

## Repository layout (target)

```
containers/<service>/Dockerfile   one directory per service (nginx, api, tick, worker, …)
farglow/                          Python package: engine/, api/, web/, worker/, llm/, mail/, moderation/
farglow/web/static/art/           farglow-art.js (icons, civ sets, procedural planets and stars)
config/                           *.poc.yaml: tech tree, balance, objectives, moderation, galaxy
migrations/                       schema migrations
tests/                            unit/ functional/ scale/ security/
tools/                            sim.py (economy simulator), tech-tree PDF builder, art build scripts
docs/                             advisor spec, decision log, design-pack index
compose.yaml  .env.example  VERSION
install.sh  uninstall.sh  build.sh  test.sh  backup.sh  restore.sh
```

---

## Running a server

> Phase 0 versions of these scripts work today (see [CHANGELOG.md](CHANGELOG.md)). Every script has `--help`.

```bash
./install.sh              # interactive (re-run: use saved settings as is, review each, or start fresh): domain, admin email, GHCR pull or local build,
                          # AI tier + Ollama URL or API key, SMTP settings (sends a test email)
./build.sh --local        # build every containers/<service>/Dockerfile into local Docker
./build.sh                # run test.sh, then push the next build X.Y.Z-N (number picked from GHCR) for amd64+arm64
./build.sh --release      # push the release X.Y.Z from VERSION (once)
./backup.sh               # one file: farglow-backup-<host>-T<tick>-<date>.tar.gz
./backup.sh --with-secrets   # also include .env, encrypted with a passphrase
./restore.sh <file>       # verify, take a safety backup, restore, migrate, restart PAUSED
./uninstall.sh            # stop and remove containers (data and .env kept); --purge deletes data
./test.sh                 # local checks + tests; --stack runs the install/backup/restore round trip
```

**Playing the demo:** open the server's address, create an account (the host admin email becomes the host admin), and found a civilization. On a development server (`FARGLOW_DEBUG=true`), ticks run every 5 minutes, tech costs are a tenth of normal, and every player has an **Advance the clock** button. On a normal server only the host admin has it, under *Host admin*.

Day-to-day operator commands run inside a container:

```bash
docker compose ps                                          # health of every service
docker compose exec tick python -m farglow engine status   # tick, hash, paused?
docker compose exec tick python -m farglow engine pause --reason "maintenance"
docker compose exec tick python -m farglow engine resume
docker compose exec tick python -m farglow engine verify   # replay from the seed, compare hashes
```

- **Requirements:** Docker with Compose v2 on Linux (tested target: Ubuntu 26.04 LTS), a domain name, and SMTP credentials. An AI backend is optional (tier T0 needs none).
- **Configuration:** `install.sh` writes `.env` (permissions 600) and generates the secrets. Game rules live in `config/*.yaml`; every number there is data, never code.
- **Admin:** the host admin panel covers players, moderation, the tick engine, services and backups. Its Operations section covers capacity, galaxy density, rollback to a tick, bans and logs.

---

## Testing

| Suite | Covers |
|---|---|
| **Unit** | platform, api, ui, ai |
| **Functional** | sign-up, simple start (first 10 ticks), the advisor's top 25 use cases, account deletion, two-civilization combat to the death, backup/restore round trip |
| **Determinism** | same seed + orders → same state hash; replay after rollback matches |
| **Balance** | `tools/sim.py` checks the pacing targets (first tech in day 1, Lattice by days 10–16, tree done by days 80–110) |
| **Scale** | concurrent players, 500 NPC civilizations, tick time under budget |
| **Security** | OWASP ZAP, OWASP Top 10 review, static code scanning, signed-link replay and expiry |

`./test.sh` runs everything that applies locally; `build.sh` refuses to push if it fails.

---

## Design

- **Visual direction:**
  - "Clean scientific", desktop-first, dense and data-rich.
  - Light and dark themes.
  - Inter Tight for text, IBM Plex Mono for numbers.
  - **Blue means you; orange means others.**
- **Logo:** *F-Horizon*, a monogram whose top stroke is a horizon and whose crossbar is a pair of suns rising.
- **Art in code:** 60 icons, 32 civilization sets, and procedural planets, stars and belts, all drawn by one script (`farglow-art.js`).
- **Mockups:** 19 screens in the design pack:
  - sign-in, Galaxy, System view, Governor, Research, Dispatch (in-game and email), Diplomacy, Colony, Fleet orders, Guilds
  - advisor setup, First Light, AI activity log, settings
  - self-host setup wizard, host admin (overview and operations)
  - logo concepts
- **Scope for the first release:** English only. Accessibility work comes later. Colour contrast is already met.

---

## Contributing
Not open to outside contributions yet. When it is, a Contributor License Agreement (CLA) will be required: it lets Citus Technologies offer commercial licenses and convert versions to Apache 2.0 on schedule. See [CONTRIBUTING.md](CONTRIBUTING.md).

## License
**Business Source License 1.1** with an Additional Use Grant: free to self-host and run for others as long as it isn't a paid hosting service. Each version converts to **Apache 2.0** four years after release. Farglow is *source-available*, not OSI open source. The names and logos are trademarks and are not licensed. See [LICENSE.md](LICENSE.md). *(Draft: needs legal review before the repository goes public.)*

© 2026 Citus Technologies, LLC. Generative Distractions is a brand of Citus Technologies, LLC.
