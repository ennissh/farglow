import pytest

from farglow import db, queue

pytestmark = pytest.mark.db


def test_enqueue_claim_complete(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        jid = queue.enqueue(conn, "worker", "noop", {"a": 1})
        job = queue.claim(conn, ["worker"], "t1")
        assert job["id"] == jid and job["status"] == "running" and job["attempts"] == 1
        assert queue.claim(conn, ["worker"], "t2") is None  # nothing else ready
        queue.complete(conn, jid)
        assert conn.execute("SELECT status FROM jobs WHERE id=%s", (jid,)).fetchone()["status"] == "done"


def test_dedupe_key(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        assert queue.enqueue(conn, "worker", "noop", dedupe_key="k") is not None
        assert queue.enqueue(conn, "worker", "noop", dedupe_key="k") is None


def test_skip_locked_gives_each_worker_a_different_job(pg_settings):
    with db.connect(pg_settings, autocommit=True) as c0:
        queue.enqueue(c0, "worker", "noop")
        queue.enqueue(c0, "worker", "noop")
    with db.connect(pg_settings) as a, db.connect(pg_settings) as b:
        ja = queue.claim(a, ["worker"], "a")  # transaction stays open: row locked
        jb = queue.claim(b, ["worker"], "b")
        assert ja and jb and ja["id"] != jb["id"]


def test_failure_retries_then_dead(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        jid = queue.enqueue(conn, "worker", "noop", max_attempts=2)
        job = queue.claim(conn, ["worker"], "t")
        assert queue.fail(conn, job, "boom") == "queued"
        conn.execute("UPDATE jobs SET run_at = now() WHERE id=%s", (jid,))
        job = queue.claim(conn, ["worker"], "t")
        assert queue.fail(conn, job, "boom again") == "dead"


def test_runner_runs_handler(pg_settings):
    seen = []
    with db.connect(pg_settings, autocommit=True) as conn:
        queue.enqueue(conn, "mail", "mail.send", {"to": "x"})
        r = queue.Runner(pg_settings, "test", ["mail"], {"mail.send": lambda job, s: seen.append(job["payload"])})
        assert r.run_one(conn) is True
        assert r.run_one(conn) is False
    assert seen == [{"to": "x"}]


def test_requeue_stale(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        jid = queue.enqueue(conn, "worker", "noop")
        queue.claim(conn, ["worker"], "dead-worker")
        conn.execute("UPDATE jobs SET locked_at = now() - interval '1 hour' WHERE id=%s", (jid,))
        assert queue.requeue_stale(conn) == 1
