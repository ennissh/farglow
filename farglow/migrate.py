"""Schema migrations: numbered SQL files in migrations/, applied once, in order.

    python -m farglow.migrate            apply pending migrations
    python -m farglow.migrate --status   show applied / pending, exit 1 if pending

Each file runs in its own transaction. An applied file's SHA-256 is stored; editing a
migration after it shipped is refused (write a new one instead). A session advisory lock
makes concurrent runs safe.
"""
from __future__ import annotations

import hashlib
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from . import config, db
from . import log as flog

LOCK_ID = 0x46617267  # "Farg"
NAME_RE = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path

    @property
    def sql(self) -> str:
        return self.path.read_text(encoding="utf-8")

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.path.read_bytes()).hexdigest()


def migrations_dir() -> Path:
    for candidate in (Path(__file__).resolve().parent.parent / "migrations", Path("/app/migrations")):
        if candidate.is_dir():
            return candidate
    raise FileNotFoundError("migrations/ directory not found")


def discover(directory: Path | None = None) -> list[Migration]:
    directory = directory or migrations_dir()
    found = []
    for path in sorted(directory.glob("*.sql")):
        m = NAME_RE.match(path.name)
        if not m:
            raise ValueError(f"bad migration file name: {path.name} (want NNNN_name.sql)")
        found.append(Migration(int(m.group(1)), m.group(2), path))
    versions = [m.version for m in found]
    if len(set(versions)) != len(versions):
        raise ValueError("duplicate migration version numbers")
    return found


def _ensure_table(conn) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version    integer PRIMARY KEY,
            name       text NOT NULL,
            checksum   text NOT NULL,
            applied_at timestamptz NOT NULL DEFAULT now()
        )
        """
    )


def applied(conn) -> dict[int, dict]:
    _ensure_table(conn)
    rows = conn.execute("SELECT version, name, checksum, applied_at FROM schema_migrations").fetchall()
    return {r["version"]: r for r in rows}


def pending(conn, available: list[Migration]) -> list[Migration]:
    done = applied(conn)
    for m in available:
        if m.version in done and done[m.version]["checksum"] != m.checksum:
            raise RuntimeError(
                f"migration {m.path.name} changed after it was applied "
                "(write a new migration instead of editing a shipped one)"
            )
    unknown = sorted(set(done) - {m.version for m in available})
    if unknown:
        raise RuntimeError(
            f"database has migrations this release does not know: {unknown}. "
            "Is this an older release than the one that created the database?"
        )
    return [m for m in available if m.version not in done]


def head_version(available: list[Migration] | None = None) -> int:
    available = discover() if available is None else available
    return max((m.version for m in available), default=0)


def run(settings: config.Settings, directory: Path | None = None) -> int:
    available = discover(directory)
    with db.connect(settings, autocommit=True) as conn:
        conn.execute("SELECT pg_advisory_lock(%s)", (LOCK_ID,))
        try:
            todo = pending(conn, available)
            for m in todo:
                log.info("applying migration", extra={"version": m.version, "migration": m.name})
                with conn.transaction():
                    conn.execute(m.sql)
                    conn.execute(
                        "INSERT INTO schema_migrations (version, name, checksum) VALUES (%s, %s, %s)",
                        (m.version, m.name, m.checksum),
                    )
            log.info("schema up to date", extra={"applied_now": len(todo), "head": head_version(available)})
            return len(todo)
        finally:
            conn.execute("SELECT pg_advisory_unlock(%s)", (LOCK_ID,))


def status(settings: config.Settings) -> tuple[int, int, list[Migration]]:
    available = discover()
    with db.connect(settings, autocommit=True) as conn:
        todo = pending(conn, available)
        current = max(applied(conn), default=0)
    return current, head_version(available), todo


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    settings = config.load("migrate")
    flog.setup("migrate", settings.log_level)
    db.wait_for_db(settings)
    if "--status" in argv:
        current, head, todo = status(settings)
        print(f"current={current} head={head} pending={[m.path.name for m in todo]}")
        return 1 if todo else 0
    run(settings)
    return 0


if __name__ == "__main__":
    sys.exit(main())
