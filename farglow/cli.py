"""Operator CLI: `python -m farglow <command>` inside any app container, e.g.

    docker compose exec tick python -m farglow engine status
    docker compose exec tick python -m farglow engine pause --reason "maintenance"
    docker compose exec tick python -m farglow engine resume
    docker compose exec tick python -m farglow engine verify      # replay from genesis
    docker compose exec mailer python -m farglow mail test --to you@example.com
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from . import __version__, config, db, migrate, queue
from . import log as flog


def _print(obj) -> None:
    print(json.dumps(obj, indent=2, default=str))


def cmd_engine(args, settings) -> int:
    from .engine import clock
    with db.connect(settings, autocommit=True) as conn:
        if args.action == "status":
            row = conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
            _print(row or {"engine": "not initialised"})
            return 0 if row else 1
        if args.action == "hash":
            row = conn.execute("SELECT tick, state_hash FROM engine_state WHERE id = 1").fetchone()
            if not row:
                print("engine not initialised", file=sys.stderr)
                return 1
            print(f"{row['tick']} {row['state_hash']}")
            return 0
        if args.action == "pause":
            clock.set_paused(conn, True, args.reason or "paused by operator")
            print("paused")
            return 0
        if args.action == "resume":
            clock.set_paused(conn, False)
            print("resumed (next tick on the next boundary)")
            return 0
        if args.action == "tick-now":
            conn.execute("UPDATE engine_state SET next_tick_at = %s WHERE id = 1 AND NOT paused",
                         (datetime.now(timezone.utc),))
            print("next tick requested (the tick service runs it within a few seconds unless paused)")
            return 0
        if args.action == "verify":
            ok, msg = clock.verify_chain(conn)
            print(("OK " if ok else "MISMATCH ") + msg)
            return 0 if ok else 1
    return 2


def cmd_queue(args, settings) -> int:
    with db.connect(settings, autocommit=True) as conn:
        if args.action == "stats":
            _print(queue.stats(conn))
            return 0
        if args.action == "enqueue":
            job_id = queue.enqueue(conn, args.queue, args.kind, json.loads(args.payload))
            print(job_id)
            return 0
    return 2


def cmd_mail(args, settings) -> int:
    from .mail import smtp
    to = args.to or settings.admin_email
    if not to:
        print("no recipient: pass --to or set FARGLOW_ADMIN_EMAIL", file=sys.stderr)
        return 2
    try:
        mid = smtp.send(settings, to, "Farglow test email",
                        f"This is a test email from the Farglow server at {settings.public_url}.\n\n"
                        "If you can read this, outbound mail works.\n")
    except smtp.MailDisabled as exc:
        print(f"SKIPPED: {exc}")
        return 3
    except Exception as exc:  # noqa: BLE001 - report any SMTP failure to the operator
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    print(f"sent to {to} ({mid})")
    return 0


def cmd_migrate(args, settings) -> int:
    return migrate.main(["--status"] if args.status else [])


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="farglow", description=f"Farglow operator CLI ({__version__})")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("engine", help="tick engine: status, hash, pause, resume, tick-now, verify")
    e.add_argument("action", choices=["status", "hash", "pause", "resume", "tick-now", "verify"])
    e.add_argument("--reason")
    q = sub.add_parser("queue", help="job queue: stats, enqueue")
    q.add_argument("action", choices=["stats", "enqueue"])
    q.add_argument("--queue", default="worker")
    q.add_argument("--kind", default="noop")
    q.add_argument("--payload", default="{}")
    m = sub.add_parser("mail", help="mail test --to ADDRESS")
    m.add_argument("action", choices=["test"])
    m.add_argument("--to")
    mg = sub.add_parser("migrate", help="apply migrations (or --status)")
    mg.add_argument("--status", action="store_true")
    sub.add_parser("version", help="print the version")
    args = p.parse_args(argv)
    settings = config.load("cli")
    flog.setup("cli", "WARNING")
    if args.cmd == "version":
        print(__version__)
        return 0
    return {"engine": cmd_engine, "queue": cmd_queue, "mail": cmd_mail, "migrate": cmd_migrate}[args.cmd](args, settings)


if __name__ == "__main__":
    sys.exit(main())
