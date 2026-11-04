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
