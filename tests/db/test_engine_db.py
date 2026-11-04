from datetime import datetime, timedelta, timezone

import pytest

from farglow import db, links
from farglow.engine import clock
from farglow.engine import state as st

pytestmark = pytest.mark.db


def _force_due(conn):
    conn.execute("UPDATE engine_state SET next_tick_at = now() - interval '1 second'")


def test_genesis_then_ticks_match_pure_replay(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        clock.ensure_state(conn, pg_settings)
        for _ in range(5):
            _force_due(conn)
            assert clock.run_tick(conn, pg_settings) is not None
        row = conn.execute("SELECT tick, state_hash FROM engine_state").fetchone()
        assert row["tick"] == 5
        assert row["state_hash"] == st.replay(pg_settings.galaxy_seed, {}, 5)[-1]
        ok, msg = clock.verify_chain(conn)
        assert ok, msg
        # every tick enqueued exactly one tick.completed job
        assert conn.execute("SELECT count(*) AS n FROM jobs WHERE kind='tick.completed'").fetchone()["n"] == 5


def test_not_due_does_not_tick(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        clock.ensure_state(conn, pg_settings)
        conn.execute("UPDATE engine_state SET next_tick_at = now() + interval '1 hour'")
        assert clock.run_tick(conn, pg_settings) is None


def test_pause_blocks_ticks_and_resume_realigns(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        clock.ensure_state(conn, pg_settings)
        clock.set_paused(conn, True, "test")
        _force_due(conn)
        assert clock.run_tick(conn, pg_settings) is None
        clock.set_paused(conn, False)
        nxt = conn.execute("SELECT next_tick_at FROM engine_state").fetchone()["next_tick_at"]
        assert nxt > datetime.now(timezone.utc)
        kinds = [r["kind"] for r in conn.execute("SELECT kind FROM engine_events ORDER BY id").fetchall()]
        assert kinds == ["genesis", "pause", "resume"]


def test_restore_points_are_pruned(pg_settings):
    from dataclasses import replace
    s = replace(pg_settings, restore_points_keep=3)
    with db.connect(s, autocommit=True) as conn:
        clock.ensure_state(conn, s)
        for _ in range(6):
            _force_due(conn)
            clock.run_tick(conn, s)
        ticks = [r["tick"] for r in conn.execute("SELECT tick FROM restore_points ORDER BY tick").fetchall()]
        assert ticks == [4, 5, 6]


def test_catch_up_is_one_tick_then_realign(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        clock.ensure_state(conn, pg_settings)
        conn.execute("UPDATE engine_state SET next_tick_at = now() - interval '5 hours'")
        clock.run_tick(conn, pg_settings)
        assert clock.run_tick(conn, pg_settings) is None  # no burst
        nxt = conn.execute("SELECT next_tick_at FROM engine_state").fetchone()["next_tick_at"]
        assert nxt <= datetime.now(timezone.utc) + timedelta(seconds=pg_settings.tick_seconds)


def test_tampered_history_is_detected(pg_settings):
    with db.connect(pg_settings, autocommit=True) as conn:
        clock.ensure_state(conn, pg_settings)
        _force_due(conn)
        clock.run_tick(conn, pg_settings)
        conn.execute("UPDATE ticks SET state_hash = repeat('0', 64) WHERE tick = 1")
        ok, _ = clock.verify_chain(conn)
        assert not ok


def test_links_are_single_use_and_revocable(pg_settings):
    key = pg_settings.link_signing_key
    with db.connect(pg_settings, autocommit=True) as conn:
        t1 = links.issue(conn, key, "dispatch.decide", "civ:1", 600, tick=1)
        assert links.consume(conn, key, t1, "dispatch.decide")["s"] == "civ:1"
        with pytest.raises(links.LinkError):
            links.consume(conn, key, t1, "dispatch.decide")
        t2 = links.issue(conn, key, "dispatch.decide", "civ:1", 600, tick=9)
        assert links.revoke_after_tick(conn, 5) == 1
        with pytest.raises(links.LinkError):
            links.consume(conn, key, t2, "dispatch.decide")


def test_status_shows_latest_heartbeat_per_service(pg_settings):
    from farglow.api.app import engine_status
    with db.connect(pg_settings, autocommit=True) as conn:
        conn.execute("INSERT INTO service_heartbeats (service, instance, version, seen_at) VALUES "
                     "('tick', 'old-container', '0.0.0+a', now() - interval '1 hour'), "
                     "('tick', 'new-container', '0.0.0+b', now())")
    services = engine_status(pg_settings)["services"]
    assert [(s["service"], s["version"]) for s in services] == [("tick", "0.0.0+b")]
