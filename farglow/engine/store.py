"""Reading the current game state and queueing orders (used by the api, worker and CLI).

Orders are the only way anything changes in the galaxy. An order is checked against the
current state when it is queued (so the player gets an answer at once) and again by the
tick that applies it. The engine_state row is locked FOR SHARE while an order is queued, so
an order can never land on a tick that has already run.
"""
from __future__ import annotations

from psycopg.types.json import Jsonb

from . import game
from . import rules as rules_mod

_cache: dict = {"tick": None, "hash": None, "state": None}


def current_state(conn) -> dict | None:
    """The state after the latest tick (cached per tick: snapshots are immutable)."""
    row = conn.execute("SELECT tick, state_hash FROM engine_state WHERE id = 1").fetchone()
    if row is None:
        return None
    if _cache["tick"] == row["tick"] and _cache["hash"] == row["state_hash"]:
        return _cache["state"]
    rp = conn.execute("SELECT snapshot FROM restore_points WHERE tick = %s", (row["tick"],)).fetchone()
    if rp is None:
        return None
    _cache.update(tick=row["tick"], hash=row["state_hash"], state=rp["snapshot"])
    return rp["snapshot"]


def queue_order(conn, body: dict, user_id: int | None = None) -> int:
    """Insert an order for the next tick and return that tick. No validation here."""
    with conn.transaction():
        tick = conn.execute("SELECT tick FROM engine_state WHERE id = 1 FOR SHARE").fetchone()["tick"]
        conn.execute(
            "INSERT INTO orders (for_tick, seq, body, user_id) VALUES (%s, nextval('orders_seq'), %s, %s)",
            (tick + 1, Jsonb(body), user_id),
        )
    return tick + 1


def submit(conn, user_id: int, body: dict) -> tuple[bool, str, int | None]:
    """Validate against the current state, then queue. Returns (ok, message, for_tick)."""
    state = current_state(conn)
    if state is None:
        return False, "the galaxy has not started yet", None
    order = dict(body, user=int(user_id))
    err = game.validate(state, rules_mod.load(), order)
    if err:
        return False, err, None
    return True, "queued", queue_order(conn, order, user_id)


def pending(conn, user_id: int) -> list[dict]:
    tick = conn.execute("SELECT tick FROM engine_state WHERE id = 1").fetchone()["tick"]
    return [r["body"] for r in conn.execute(
        "SELECT body FROM orders WHERE user_id = %s AND for_tick > %s ORDER BY seq", (user_id, tick)).fetchall()]
