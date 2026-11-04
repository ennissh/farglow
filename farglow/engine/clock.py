"""The tick service: advances the galaxy on a fixed clock.

* One engine per database (pg advisory lock); a second copy waits as a standby.
* Ticks are aligned to the interval (top of the hour; every 5 minutes in DEBUG). If the
  engine was down, it runs ONE catch-up tick and re-aligns; it does not burst through
  missed hours (a deliberate choice: players should not wake to 8 ticks at once).
* Each tick, in one transaction: advance the state, write the tick row and a restore point,
  prune old restore points, enqueue 'tick.completed' for the worker.
* Pause/resume is a row flag, so operators (CLI, restore.sh, host admin) can set it.
"""
from __future__ import annotations

import logging
import signal
import socket
import time
from datetime import datetime, timedelta, timezone

from psycopg.types.json import Jsonb

from .. import __version__, config, db, queue
from .. import log as flog
from . import state as st

ENGINE_LOCK = 0x5449434B  # "TICK"
HEARTBEAT_FILE = "/tmp/farglow-heartbeat"
log = logging.getLogger("farglow.tick")


def next_boundary(now: datetime, interval_s: int) -> datetime:
    epoch = int(now.timestamp())
    return datetime.fromtimestamp((epoch // interval_s + 1) * interval_s, tz=timezone.utc)


def ensure_state(conn, settings: config.Settings) -> dict:
    row = conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
    if row:
        if settings.galaxy_seed and row["galaxy_seed"] != settings.galaxy_seed:
            log.warning("FARGLOW_GALAXY_SEED differs from the database; the database wins",
                        extra={"db_seed": row["galaxy_seed"]})
        if row["tick_seconds"] != settings.tick_seconds:
            conn.execute("UPDATE engine_state SET tick_seconds = %s, next_tick_at = %s, updated_at = now() WHERE id = 1",
                         (settings.tick_seconds, next_boundary(datetime.now(timezone.utc), settings.tick_seconds)))
            row = conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
        return row
    if not settings.galaxy_seed:
        raise RuntimeError("FARGLOW_GALAXY_SEED is not set (install.sh generates it)")
    g = st.genesis(settings.galaxy_seed)
    h = st.state_hash(g)
    nxt = next_boundary(datetime.now(timezone.utc), settings.tick_seconds)
    with conn.transaction():
        conn.execute(
            "INSERT INTO engine_state (galaxy_seed, tick, state_hash, tick_seconds, next_tick_at) "
            "VALUES (%s, 0, %s, %s, %s)",
            (settings.galaxy_seed, h, settings.tick_seconds, nxt),
        )
        conn.execute("INSERT INTO restore_points (tick, state_hash, snapshot) VALUES (0, %s, %s)", (h, Jsonb(g)))
        conn.execute("INSERT INTO engine_events (tick, kind, detail) VALUES (0, 'genesis', %s)",
                     (Jsonb({"state_hash": h}),))
    log.info("genesis", extra={"tick": 0, "state_hash": h})
    return conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()


def run_tick(conn, settings: config.Settings, force: bool = False) -> dict | None:
    """Advance one tick if due (or forced). Returns the new engine row, or None."""
    started = datetime.now(timezone.utc)
    t0 = time.monotonic()
    with conn.transaction():
        row = conn.execute("SELECT * FROM engine_state WHERE id = 1 FOR UPDATE").fetchone()
        if row["paused"] or (not force and row["next_tick_at"] > started):
            return None
        rp = conn.execute("SELECT snapshot, state_hash FROM restore_points WHERE tick = %s",
                          (row["tick"],)).fetchone()
        if rp is None or rp["state_hash"] != row["state_hash"]:
            raise RuntimeError(f"no restore point matching tick {row['tick']}: refusing to tick")
        orders = [r["body"] for r in conn.execute(
            "SELECT body FROM orders WHERE for_tick = %s ORDER BY seq", (row["tick"] + 1,)).fetchall()]
        new = st.advance(rp["snapshot"], orders)
        h = st.state_hash(new)
        ms = int((time.monotonic() - t0) * 1000)
        conn.execute(
            "INSERT INTO ticks (tick, state_hash, prev_hash, orders_hash, started_at, duration_ms) "
            "VALUES (%s, %s, %s, %s, %s, %s)",
            (new["tick"], h, row["state_hash"], st.orders_hash(orders), started, ms),
        )
        conn.execute("INSERT INTO restore_points (tick, state_hash, snapshot) VALUES (%s, %s, %s)",
                     (new["tick"], h, Jsonb(new)))
        conn.execute("DELETE FROM restore_points WHERE tick <= %s", (new["tick"] - settings.restore_points_keep,))
        interval = timedelta(seconds=row["tick_seconds"])
        nxt = row["next_tick_at"] + interval
        if nxt <= started:  # we were down: one catch-up tick, then re-align
            nxt = next_boundary(started, row["tick_seconds"])
        conn.execute(
            "UPDATE engine_state SET tick = %s, state_hash = %s, last_tick_at = %s, next_tick_at = %s, "
            "updated_at = now() WHERE id = 1",
            (new["tick"], h, started, nxt),
        )
        queue.enqueue(conn, "worker", "tick.completed", {"tick": new["tick"], "state_hash": h},
                      dedupe_key=f"tick.completed:{new['tick']}:{h[:16]}")
    log.info("tick", extra={"tick": new["tick"], "state_hash": h, "duration_ms": ms, "orders": len(orders)})
    return {"tick": new["tick"], "state_hash": h, "next_tick_at": nxt}


def set_paused(conn, paused: bool, reason: str | None = None, actor: str = "cli") -> None:
    with conn.transaction():
        row = conn.execute("SELECT tick, tick_seconds FROM engine_state WHERE id = 1 FOR UPDATE").fetchone()
        if row is None:
            raise RuntimeError("engine not initialised yet (start the tick service once)")
        if paused:
            conn.execute("UPDATE engine_state SET paused = true, pause_reason = %s, updated_at = now() WHERE id = 1",
                         (reason or "paused",))
        else:
            # Resume on the next boundary: no burst of missed ticks.
            conn.execute(
                "UPDATE engine_state SET paused = false, pause_reason = NULL, next_tick_at = %s, updated_at = now() "
                "WHERE id = 1",
                (next_boundary(datetime.now(timezone.utc), row["tick_seconds"]),),
            )
        conn.execute("INSERT INTO engine_events (tick, kind, detail) VALUES (%s, %s, %s)",
                     (row["tick"], "pause" if paused else "resume", Jsonb({"reason": reason, "actor": actor})))


def verify_chain(conn) -> tuple[bool, str]:
    """Replay from genesis with the stored orders and compare every stored tick hash."""
    eng = conn.execute("SELECT * FROM engine_state WHERE id = 1").fetchone()
    if eng is None:
        return False, "engine not initialised"
    stored = {r["tick"]: r["state_hash"] for r in conn.execute("SELECT tick, state_hash FROM ticks").fetchall()}
    orders: dict[int, list] = {}
    for r in conn.execute("SELECT for_tick, body FROM orders ORDER BY for_tick, seq").fetchall():
        orders.setdefault(r["for_tick"], []).append(r["body"])
    state = st.genesis(eng["galaxy_seed"])
    for t in range(1, eng["tick"] + 1):
        state = st.advance(state, orders.get(t, []))
        h = st.state_hash(state)
        if t in stored and stored[t] != h:
            return False, f"tick {t}: stored {stored[t][:12]} != replayed {h[:12]}"
    final = st.state_hash(state)
    if final != eng["state_hash"]:
        return False, f"head tick {eng['tick']}: stored {eng['state_hash'][:12]} != replayed {final[:12]}"
    return True, f"tick {eng['tick']} hash {final} reproduced from seed {eng['galaxy_seed']}"


class TickService:
    def __init__(self, settings: config.Settings, poll_s: float = 2.0):
        self.settings = settings
        self.poll_s = poll_s
        self.stopping = False

    def _stop(self, *_):
        self.stopping = True

    def run(self) -> None:
        signal.signal(signal.SIGTERM, self._stop)
        signal.signal(signal.SIGINT, self._stop)
        db.wait_for_db(self.settings)
        with db.connect(self.settings, autocommit=True) as conn:
            while not self.stopping:
                if conn.execute("SELECT pg_try_advisory_lock(%s) AS ok", (ENGINE_LOCK,)).fetchone()["ok"]:
                    break
                log.info("another tick engine holds the lock; standing by")
                _touch()
                time.sleep(10)
            row = ensure_state(conn, self.settings)
            log.info("tick engine started", extra={"tick": row["tick"], "paused": row["paused"],
                                                   "tick_seconds": row["tick_seconds"],
                                                   "next_tick_at": row["next_tick_at"].isoformat()})
            last_beat = 0.0
            while not self.stopping:
                try:
                    run_tick(conn, self.settings)
                except Exception:  # noqa: BLE001 - log and keep the clock alive
                    log.exception("tick failed")
                    time.sleep(min(30, self.settings.tick_seconds))
                if time.monotonic() - last_beat > 30:
                    eng = conn.execute("SELECT tick, paused FROM engine_state WHERE id = 1").fetchone()
                    db.heartbeat(conn, "tick", socket.gethostname(), __version__,
                                 {"tick": eng["tick"], "paused": eng["paused"]})
                    last_beat = time.monotonic()
                _touch()
                time.sleep(self.poll_s)
        log.info("tick engine stopped")


def _touch() -> None:
    with open(HEARTBEAT_FILE, "w", encoding="utf-8") as fh:
        fh.write(str(int(time.time())))


def main() -> int:
    settings = config.load("tick")
    flog.setup("tick", settings.log_level)
    TickService(settings).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
