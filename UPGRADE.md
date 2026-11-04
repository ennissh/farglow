# Upgrading a Farglow server

Pre-1.0 releases may change the database between minor versions. **Back up first, every time.**

## The upgrade path (any release to a newer one)
```bash
./backup.sh --with-secrets               # 1. a restorable backup of the current state
git fetch --tags && git checkout vX.Y.Z  # 2. the new release's scripts and compose.yaml
./install.sh --settings saved --tag X.Y.Z   # 3. re-run with your saved answers (or pick 1 when asked)
```
`install.sh` pulls the new images and recreates the containers. The `migrate` service applies any new migrations before `api`, `tick`, `worker` and `mailer` start; it is one-shot, and the others wait for it to succeed. Then every service has to report healthy.

Check afterwards:
```bash
docker compose ps                                          # every service healthy
docker compose exec tick python -m farglow engine verify   # OK: replay matches
```

## What never happens
| Never | Why |
|---|---|
| Secrets regenerated | `install.sh` reuses the existing `.env`. The database password must not change under a live database. |
| Data deleted | Only `./uninstall.sh --purge` deletes volumes, and it asks you to type `delete farglow` first. |
| An edited migration applied | Migrations are checksummed. A changed file stops `migrate` and nothing starts. |
| Downgrades | `migrate` refuses a database that has migrations the release doesn't know. `restore.sh` refuses a backup from a newer version. |

## Rolling back a failed upgrade
```bash
git checkout v<previous>
./restore.sh backups/<the backup from step 1>.tar.gz    # verifies, safety-backs up, restores, starts PAUSED
./install.sh --tag <previous>
docker compose exec tick python -m farglow engine resume
```

## Moving to a new machine
On the old host, `./backup.sh --with-secrets`. On the new host:
1. Clone the repository at the same release.
2. Run `./install.sh --no-start` and answer the questions (they are replaced next).
3. Run `./restore.sh --with-secrets <file>`. It restores `.env` (the original seed and secrets) and the database.

## Version-specific notes
None yet. Every release that needs a manual step adds a section here and a `### Changed` CHANGELOG line marked **Upgrade note**.
