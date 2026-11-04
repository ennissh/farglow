"""Job handlers for the 'worker' queue. Each takes (job, settings) and raises on failure.

tick.completed  -> write the tick's events to each player's Dispatch, and every
                   FARGLOW_DISPATCH_EVERY_TICKS ticks (24 = once a day) queue the morning
                   Dispatch email to players who want it.
"""
from __future__ import annotations

import logging
import os

from psycopg.types.json import Jsonb

from .. import db, queue
from ..config import Settings
from ..engine import rules as rules_mod
from ..play import dispatch

log = logging.getLogger("farglow.worker")


def _every(settings: Settings) -> int:
    default = 12 if settings.debug else 24
    try:
        return max(1, int(os.environ.get("FARGLOW_DISPATCH_EVERY_TICKS", default)))
    except ValueError:
        return default


def tick_completed(job: dict, settings: Settings) -> None:
    tick = int(job["payload"]["tick"])
    with db.connect(settings) as conn:
        rp = conn.execute("SELECT snapshot FROM restore_points WHERE tick = %s", (tick,)).fetchone()
        if rp is None:
            log.warning("tick snapshot already pruned; no Dispatch for it", extra={"tick": tick})
            return
        state = rp["snapshot"]
        if state.get("schema", 1) < 2:
            return
        user_of = {cid: int(c["user"]) for cid, c in state["civs"].items()}
        known = {r["id"] for r in conn.execute("SELECT id FROM users").fetchall()}
        with conn.transaction():
            # idempotent: a retried job must not duplicate the tick's news
            conn.execute("DELETE FROM dispatch_items WHERE tick = %s", (tick,))
            for ev in state.get("log", []):
                uid = user_of.get(ev.get("civ")) or (int(ev["user"]) if str(ev.get("user", "")).isdigit() else None)
                if uid is None or uid not in known:
                    continue
                data = {k: v for k, v in ev.items() if k not in ("civ", "kind")}
                conn.execute("INSERT INTO dispatch_items (user_id, civ_id, tick, kind, data) VALUES (%s, %s, %s, %s, %s)",
                             (uid, ev.get("civ") or "", tick, ev["kind"], Jsonb(data)))
            if tick % _every(settings) == 0:
                _queue_emails(conn, settings, state, tick)
    log.info("dispatch written", extra={"tick": tick, "events": len(state.get("log", []))})


def _queue_emails(conn, settings: Settings, state: dict, tick: int) -> None:
    rules = rules_mod.load()
    users = conn.execute("SELECT id, email, display_name FROM users WHERE dispatch_email AND email_verified_at IS NOT NULL"
                         ).fetchall()
    for u in users:
        cid = state["users"].get(str(u["id"]))
        civ = state["civs"].get(cid) if cid else None
        if not civ or not civ["alive"]:
            continue
        rows = conn.execute("SELECT id, tick, kind, data FROM dispatch_items WHERE user_id = %s AND NOT emailed "
                            "ORDER BY id", (u["id"],)).fetchall()
        lines = []
        for r in rows:
            rendered = dispatch.render({"kind": r["kind"], **r["data"]}, state, rules, civ)
            if rendered:
                lines.append(f"T{r['tick']:,}  {rendered[0]}" + (f"\n        {rendered[1]}" if rendered[1] else ""))
        if not lines:
            continue
        last = civ.get("last") or {}
        text = (
            f"The Meridian Dispatch for {civ['name']}, tick {tick:,}\n\n" + "\n".join(lines[-40:]) +
            f"\n\nYour civilization: population {last.get('pop', 0) / 1000:.1f}, stability {civ['stability'] / 1000:.0f}, "
            f"minerals {civ['minerals'] // 1000:,}, {last.get('ac_net', 0) / 1000:.0f} AC a tick.\n\n"
            f"Play: {settings.public_url}/play\n"
            f"Stop these emails: {settings.public_url}/account (sign in, then untick the Dispatch)\n"
        )
        queue.enqueue(conn, "mail", "mail.send", {"to": u["email"], "subject": f"The Dispatch · {civ['name']} · tick {tick:,}",
                                                  "text": text},
                      dedupe_key=f"dispatch:{u['id']}:{tick}")
        conn.execute("UPDATE dispatch_items SET emailed = true WHERE user_id = %s AND id <= %s",
                     (u["id"], rows[-1]["id"]))


def noop(job: dict, settings: Settings) -> None:
    log.info("noop job", extra={"payload": job["payload"]})


HANDLERS = {
    "tick.completed": tick_completed,
    "noop": noop,
}
