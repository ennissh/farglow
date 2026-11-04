"""Postgres-native job queue.

Producers call enqueue() inside their own transaction, so a job exists only if the work
that caused it committed. Consumers claim with FOR UPDATE SKIP LOCKED, so any number of
workers can share a queue. A trigger NOTIFYs 'farglow_jobs' on insert; consumers LISTEN
and fall back to polling.
"""
from __future__ import annotations

import logging
import os
import signal
import socket
import time
from typing import Callable, Iterable

from psycopg.types.json import Jsonb

from . import __version__, db
from .config import Settings

log = logging.getLogger(__name__)

Handler = Callable[[dict, Settings], None]
STALE_AFTER_S = 15 * 60


def enqueue(conn, queue: str, kind: str, payload: dict | None = None, *, priority: int = 0,
            delay_s: int = 0, max_attempts: int = 5, dedupe_key: str | None = None) -> int | None:
    row = conn.execute(
        """
        INSERT INTO jobs (queue, kind, payload, priority, run_at, max_attempts, dedupe_key)
        VALUES (%s, %s, %s, %s, now() + make_interval(secs => %s), %s, %s)
        ON CONFLICT (dedupe_key) DO NOTHING
        RETURNING id
        """,
        (queue, kind, Jsonb(payload or {}), priority, delay_s, max_attempts, dedupe_key),
    ).fetchone()
    return row["id"] if row else None


def claim(conn, queues: Iterable[str], worker_id: str) -> dict | None:
    return conn.execute(
        """
        UPDATE jobs SET status = 'running', locked_at = now(), locked_by = %s, attempts = attempts + 1
        WHERE id = (
            SELECT id FROM jobs
            WHERE status = 'queued' AND queue = ANY(%s) AND run_at <= now()
            ORDER BY priority DESC, run_at, id
            FOR UPDATE SKIP LOCKED
            LIMIT 1
        )
        RETURNING *
        """,
        (worker_id, list(queues)),
    ).fetchone()


def complete(conn, job_id: int) -> None:
    conn.execute(
        "UPDATE jobs SET status = 'done', finished_at = now(), locked_at = NULL WHERE id = %s",
        (job_id,),
    )


def backoff_seconds(attempts: int) -> int:
    return min(10 * 2 ** max(attempts - 1, 0), 3600)


def fail(conn, job: dict, error: str) -> str:
    dead = job["attempts"] >= job["max_attempts"]
    status = "dead" if dead else "queued"
    conn.execute(
        """
        UPDATE jobs SET status = %s, last_error = %s, locked_at = NULL, locked_by = NULL,
               run_at = now() + make_interval(secs => %s),
               finished_at = CASE WHEN %s THEN now() ELSE NULL END
        WHERE id = %s
        """,
        (status, error[:4000], backoff_seconds(job["attempts"]), dead, job["id"]),
    )
    return status


def requeue_stale(conn, older_than_s: int = STALE_AFTER_S) -> int:
    """Jobs left 'running' by a worker that died go back to the queue."""
    cur = conn.execute(
        """
        UPDATE jobs SET status = 'queued', locked_at = NULL, locked_by = NULL
        WHERE status = 'running' AND locked_at < now() - make_interval(secs => %s)
        """,
        (older_than_s,),
    )
    return cur.rowcount


def stats(conn) -> list[dict]:
    return conn.execute(
        "SELECT queue, status, count(*) AS n FROM jobs GROUP BY queue, status ORDER BY queue, status"
    ).fetchall()


class Runner:
    """A consumer loop for one or more queues. Used by the worker and mailer services."""

    def __init__(self, settings: Settings, service: str, queues: list[str],
                 handlers: dict[str, Handler], heartbeat_file: str = "/tmp/farglow-heartbeat"):
        self.settings = settings
        self.service = service
        self.queues = queues
        self.handlers = handlers
        self.heartbeat_file = heartbeat_file
        self.worker_id = f"{service}@{socket.gethostname()}:{os.getpid()}"
        self.stopping = False

    def _stop(self, *_):
        self.stopping = True

    def _touch(self) -> None:
        with open(self.heartbeat_file, "w", encoding="utf-8") as fh:
            fh.write(str(int(time.time())))

    def run_one(self, conn) -> bool:
        with conn.transaction():
            job = claim(conn, self.queues, self.worker_id)
        if not job:
            return False
        handler = self.handlers.get(job["kind"])
        try:
            if handler is None:
                raise LookupError(f"no handler for job kind {job['kind']!r}")
            handler(job, self.settings)
        except Exception as exc:  # noqa: BLE001 - every failure is recorded on the job
            with conn.transaction():
                status = fail(conn, job, f"{type(exc).__name__}: {exc}")
            log.warning("job failed", extra={"job_id": job["id"], "kind": job["kind"],
                                             "attempt": job["attempts"], "now": status, "error": str(exc)})
        else:
            with conn.transaction():
                complete(conn, job["id"])
            log.info("job done", extra={"job_id": job["id"], "kind": job["kind"]})
        return True

    def run(self, idle_wait_s: float = 5.0) -> None:
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        db.wait_for_db(self.settings)
        log.info("consumer started", extra={"queues": self.queues, "worker": self.worker_id})
        with db.connect(self.settings, autocommit=True) as listen_conn, db.connect(self.settings, autocommit=True) as conn:
            listen_conn.execute("LISTEN farglow_jobs")
            last_beat = 0.0
            while not self.stopping:
                now = time.monotonic()
                if now - last_beat > 30:
                    self._touch()
                    db.heartbeat(conn, self.service, socket.gethostname(), __version__)
                    requeue_stale(conn)
                    last_beat = now
                if self.run_one(conn):
                    continue
                for _ in listen_conn.notifies(timeout=idle_wait_s, stop_after=1):
                    pass
        log.info("consumer stopped")
