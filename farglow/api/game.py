"""Game pages and actions. Every action is an order for the next tick (engine/store.py)."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for
from psycopg.types.json import Jsonb

from .. import db
from ..engine import clock, game, store
from ..engine import rules as rules_mod
from ..engine.rules import ALLOCATION_KEYS
from ..play import advisor, dispatch, view
from .auth import admin_required, login_required

bp = Blueprint("game", __name__)

WALKTHROUGH = [
    ("found", "Meet your civilization", "Name it and choose who you are."),
    ("dispatch", "Read your first Dispatch", "What happened since the last tick."),
    ("home", "Explore your home system", "See what each body gives you per tick."),
    ("research", "Choose your first research", "Queue a tech on the Research screen."),
    ("allocation", "Split your action credits", "Set your shares in the Governor."),
    ("survey", "Send a survey", "Pick an unknown star on the map."),
    ("build", "Order your first building", "One building per body you own."),
    ("tick", "Advance the clock", "Your orders happen at the next tick."),
]


def settings():
    return current_app.config["FARGLOW_SETTINGS"]


def _ctx(conn):
    """(state, civ, rules) for the signed-in player; civ is None before founding."""
    state = store.current_state(conn)
    if state is None or state.get("schema") != game.SCHEMA:
        return state, None, rules_mod.load()
    return state, view.civ_of(state, g.user["id"]), rules_mod.load()


def _engine(conn):
    return conn.execute("SELECT tick, paused, pause_reason, next_tick_at, tick_seconds FROM engine_state").fetchone()


def _mark(conn, step: str):
    conn.execute("UPDATE users SET walkthrough = walkthrough || %s WHERE id = %s",
                 (Jsonb({step: True}), g.user["id"]))


def _walkthrough(conn, state, civ):
    seen = conn.execute("SELECT walkthrough FROM users WHERE id = %s", (g.user["id"],)).fetchone()["walkthrough"]
    done = dict(seen)
    if civ:
        done["found"] = True
        done["research"] = done.get("research") or bool(civ["research"]["queue"] or civ["research"]["done"])
        done["allocation"] = done.get("allocation") or civ["allocation"] != rules_mod.load().start["allocation"]
        done["survey"] = civ["charters"].get("first_survey", {}).get("status") == "completed" or any(
            m["kind"] == "survey" for m in civ["missions"])
        done["build"] = bool(civ["building_counts"])
        done["tick"] = state["tick"] > civ["founded"]
    steps = [{"id": k, "title": t, "hint": h, "done": bool(done.get(k))} for k, t, h in WALKTHROUGH]
    current = next((s["id"] for s in steps if not s["done"]), None)
    return {"steps": steps, "current": current, "count": sum(s["done"] for s in steps),
            "hidden": bool(seen.get("skip"))}


def _page(template, conn, state, civ, rules, **kw):
    eng = _engine(conn)
    now = datetime.now(timezone.utc)
    pend = store.pending(conn, g.user["id"])
    unread = conn.execute("SELECT count(*) AS n FROM dispatch_items WHERE user_id = %s AND id > %s",
                          (g.user["id"], int(conn.execute("SELECT walkthrough FROM users WHERE id = %s",
                                                           (g.user["id"],)).fetchone()["walkthrough"]
                                             .get("dispatch_seen", 0)))).fetchone()["n"]
    return render_template(
        template, state=state, civ=civ, rules=rules, eng=eng, pending=pend, unread=unread,
        next_in=max(0, int((eng["next_tick_at"] - now).total_seconds())), hdr=view.header(state, civ, rules),
        walkthrough=_walkthrough(conn, state, civ), debug=settings().debug, n=view.n, **kw)


def _submit(conn, body, ok_msg):
    ok, msg, tick = store.submit(conn, g.user["id"], body)
    conn.commit()
    if ok:
        flash(f"{ok_msg} Happens at tick {tick:,}.", "ok")
    else:
        flash(f"Not possible: {msg}.", "error")
    return ok


def _back(default="game.play"):
    ref = request.form.get("back") or ""
    return redirect(ref if ref.startswith("/") and not ref.startswith("//") else url_for(default))


# ---------------------------------------------------------------------------- pages
@bp.get("/play")
@login_required
def play():
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if state is None or state.get("schema") != game.SCHEMA:
            return render_template("game/waiting.html", reason="The galaxy is being prepared. Check back after the next tick.")
        if civ is None:
            if any(o.get("kind") == "found" for o in store.pending(conn, g.user["id"])):
                return _page("game/founding_wait.html", conn, state, None, rules, tab="galaxy")
            return redirect(url_for("game.found"))
        sid = request.args.get("system") or civ["home"]
        if sid not in game.galaxy.by_id(state["galaxy_seed"], state["cell"]):
            sid = civ["home"]
        return _page("game/galaxy.html", conn, state, civ, rules, tab="galaxy", system=view.system_detail(state, civ, rules, sid),
                     tips=advisor.suggestions(state, civ, rules))


@bp.get("/play/system/<sid>")
@login_required
def system_panel(sid):
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if civ is None or sid not in game.galaxy.by_id(state["galaxy_seed"], state["cell"]):
            abort(404)
        return render_template("game/_system.html", system=view.system_detail(state, civ, rules, sid), civ=civ,
                               state=state, n=view.n, pending=store.pending(conn, g.user["id"]))


@bp.get("/api/v1/map")
@login_required
def map_json():
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if civ is None:
            abort(404)
        return jsonify(view.map_data(state, civ, rules))


@bp.route("/found", methods=["GET", "POST"])
@login_required
def found():
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if civ is not None:
            return redirect(url_for("game.play"))
        if request.method == "POST":
            f = request.form
            try:
                attrs = {a: int(f.get(f"attr_{a}", "0")) for a in rules.attributes}
                body = {"kind": "found", "name": f.get("name", "").strip(), "set": int(f.get("set", "-1")),
                        "attributes": attrs, "home_name": f.get("home_name", "").strip() or None,
                        "advisor_name": f.get("advisor_name", "").strip() or None}
            except ValueError:
                flash("Not possible: check the form.", "error")
                return redirect(url_for("game.found"))
            body = {k: v for k, v in body.items() if v is not None}
            if _submit(conn, body, f"{body['name']} will be founded."):
                return redirect(url_for("game.play"))
        return render_template("game/found.html", rules=rules, form=request.form, start=rules.start["attributes"],
                               debug=settings().debug)


@bp.get("/governor")
@login_required
def governor():
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if civ is None:
            return redirect(url_for("game.play"))
        return _page("game/governor.html", conn, state, civ, rules, tab="governor", keys=ALLOCATION_KEYS,
                     tips=advisor.suggestions(state, civ, rules))


@bp.get("/research")
@login_required
def research():
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if civ is None:
            return redirect(url_for("game.play"))
        sel = request.args.get("tech")
        rv = view.research_view(state, civ, rules)
        selected = None
        if sel in rules.techs:
            t = rules.techs[sel]
            node = next(nd for tier in rv["tiers"] for nd in tier["nodes"] if nd["id"] == sel)
            selected = {**node, "effects_text": [view.effect_text(e) for e in t["effects"]],
                        "drawbacks_text": [view.effect_text(e) for e in t["drawbacks"]],
                        "group_names": [x["name"] for x in rules.techs.values() if t["group"] and x["group"] == t["group"]
                                        and x["id"] != sel]}
        return _page("game/research.html", conn, state, civ, rules, tab="research", rv=rv, selected=selected)


@bp.get("/dispatch")
@login_required
def dispatch_page():
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        rows = conn.execute("SELECT * FROM dispatch_items WHERE user_id = %s ORDER BY id DESC LIMIT 200",
                            (g.user["id"],)).fetchall()
        items = []
        for r in rows:
            rendered = dispatch.render({"kind": r["kind"], **r["data"]}, state, rules) if state else None
            if rendered:
                items.append({"tick": r["tick"], "kind": r["kind"], "headline": rendered[0], "detail": rendered[1]})
        if civ is None:
            return redirect(url_for("game.play"))
        return _page("game/dispatch.html", conn, state, civ, rules, tab="dispatch", items=items,
                     newest=rows[0]["id"] if rows else 0)


@bp.get("/partials/clock")
@login_required
def clock_partial():
    with db.connect(settings()) as conn:
        eng = _engine(conn)
    seen = request.args.get("tick", type=int)
    resp = current_app.make_response(render_template(
        "game/_clock.html", eng=eng, next_in=max(0, int((eng["next_tick_at"] - datetime.now(timezone.utc)).total_seconds()))))
    if seen is not None and eng["tick"] != seen:
        resp.headers["HX-Refresh"] = "true"      # a tick happened: reload the page with the new state
    return resp


# ---------------------------------------------------------------------------- actions (POST only)
@bp.post("/act/<kind>")
@login_required
def act(kind):
    f = request.form
    with db.connect(settings()) as conn:
        state, civ, rules = _ctx(conn)
        if civ is None:
            abort(400)
        sid = f.get("system")
        body_i = f.get("body", type=int)
        if kind == "survey":
            _submit(conn, {"kind": "survey", "system": sid}, "Survey wing ordered.")
        elif kind == "claim":
            body = {"kind": "claim", "system": sid}
            if body_i is not None:
                body["body"] = body_i
            _submit(conn, body, "Ship ordered.")
        elif kind == "build":
            _submit(conn, {"kind": "build", "system": sid, "body": body_i, "building": f.get("building")},
                    "Construction ordered.")
        elif kind == "develop":
            _submit(conn, {"kind": "develop", "system": sid, "body": body_i}, "Development ordered.")
        elif kind == "name":
            _submit(conn, {"kind": "name_system", "system": sid, "name": f.get("name", "")}, "Name submitted.")
        elif kind == "allocation":
            try:
                alloc = {k: int(f.get(k, "")) for k in ALLOCATION_KEYS}
            except ValueError:
                flash("Not possible: shares must be whole numbers.", "error")
                return _back("game.governor")
            if _submit(conn, {"kind": "allocation", "allocation": alloc}, "New allocation set."):
                _mark(conn, "allocation")
                conn.commit()
        elif kind == "queue":
            q = [t for t in civ["research"]["queue"]]
            pend = [o for o in store.pending(conn, g.user["id"]) if o["kind"] == "research_queue"]
            if pend:
                q = list(pend[-1]["queue"])
            tid, op = f.get("tech"), f.get("op")
            if op == "add" and tid not in q:
                q.append(tid)
            elif op == "now" and tid:
                q = [tid] + [x for x in q if x != tid]
            elif op == "remove":
                q = [x for x in q if x != tid]
            elif op == "up" and tid in q and q.index(tid) > 0:
                i = q.index(tid)
                q[i - 1], q[i] = q[i], q[i - 1]
            if _submit(conn, {"kind": "research_queue", "queue": q}, "Research queue updated."):
                _mark(conn, "research")
                conn.commit()
        elif kind == "advice":
            import json as _json
            try:
                order = _json.loads(f.get("order", "{}"))
            except ValueError:
                abort(400)
            if not isinstance(order, dict) or order.get("kind") in (None, "found", "retire"):
                abort(400)
            _submit(conn, order, "Done: the advisor's suggestion is queued.")
        else:
            abort(404)
    return _back()


@bp.post("/advisor/ask")
@login_required
def ask():
    q = next((x.strip() for x in request.form.getlist("question") if x.strip()), "")[:500]
    s = settings()
    with db.connect(s) as conn:
        state, civ, rules = _ctx(conn)
        if civ is None or not q:
            abort(400)
        out = advisor.answer(q, state, civ, rules, s.llm_gateway_url, s.ai_tier)
        conn.execute("INSERT INTO advisor_log (user_id, role, text, tier) VALUES (%s, 'player', %s, NULL)",
                     (g.user["id"], q))
        conn.execute("INSERT INTO advisor_log (user_id, role, text, tier, fallback) VALUES (%s, 'advisor', %s, %s, %s)",
                     (g.user["id"], out["text"], out["tier"], out["fallback"]))
        conn.commit()
    return render_template("game/_advisor_answer.html", q=q, out=out, civ=civ)


@bp.post("/walkthrough/seen/<step>")
@login_required
def walkthrough_seen(step):
    """Fired by the page after it loads (hx-trigger="load"): GETs never write, so the
    walkthrough's 'you looked at it' steps are recorded by this small POST instead."""
    if step not in ("home", "dispatch"):
        abort(404)
    with db.connect(settings()) as conn:
        _mark(conn, step)
        newest = request.form.get("newest", type=int)
        if step == "dispatch" and newest:
            conn.execute("UPDATE users SET walkthrough = walkthrough || %s WHERE id = %s",
                         (Jsonb({"dispatch_seen": newest}), g.user["id"]))
        conn.commit()
    return ("", 204)


@bp.post("/walkthrough/skip")
@login_required
def skip_walkthrough():
    with db.connect(settings()) as conn:
        _mark(conn, "skip")
        conn.commit()
    return _back()


@bp.post("/clock/advance")
@login_required
def advance_clock():
    """Development servers (and the host admin) can run the next tick now."""
    if not (settings().debug or g.user["is_admin"]):
        abort(403)
    with db.connect(settings(), autocommit=True) as conn:
        conn.execute("UPDATE engine_state SET next_tick_at = now() WHERE id = 1 AND NOT paused")
        _mark(conn, "advanced")
    flash("The clock is advancing: the next tick runs in a few seconds.", "ok")
    return _back()


# ---------------------------------------------------------------------------- host admin
@bp.get("/admin")
@admin_required
def admin():
    with db.connect(settings()) as conn:
        state = store.current_state(conn)
        eng = conn.execute("SELECT * FROM engine_state").fetchone()
        users = conn.execute("SELECT id, email, display_name, is_admin, email_verified_at, created_at, last_seen_at "
                             "FROM users ORDER BY id").fetchall()
        ticks = conn.execute("SELECT tick, state_hash, duration_ms, finished_at FROM ticks ORDER BY tick DESC LIMIT 12").fetchall()
        jobs = conn.execute("SELECT queue, status, count(*) AS n FROM jobs GROUP BY 1, 2 ORDER BY 1, 2").fetchall()
        services = conn.execute("SELECT DISTINCT ON (service) service, version, extract(epoch FROM now() - seen_at)::int AS age "
                                "FROM service_heartbeats ORDER BY service, seen_at DESC").fetchall()
    civs = {}
    if state and state.get("schema") == game.SCHEMA:
        civs = {c["user"]: c for c in state["civs"].values() if c["alive"]}
    return render_template("game/admin.html", eng=eng, users=users, ticks=ticks, jobs=jobs, services=services,
                           civs=civs, state=state, n=view.n)


@bp.post("/admin/engine/<action>")
@admin_required
def admin_engine(action):
    with db.connect(settings(), autocommit=True) as conn:
        if action == "pause":
            clock.set_paused(conn, True, request.form.get("reason") or "paused by the host", actor=g.user["email"])
            flash("The clock is paused.", "ok")
        elif action == "resume":
            clock.set_paused(conn, False, actor=g.user["email"])
            flash("The clock resumes at the next boundary.", "ok")
        elif action == "tick":
            conn.execute("UPDATE engine_state SET next_tick_at = now() WHERE id = 1 AND NOT paused")
            flash("Running the next tick now.", "ok")
        elif action == "verify":
            ok, msg = clock.verify_chain(conn)
            flash(("Replay matches: " if ok else "REPLAY MISMATCH: ") + msg, "ok" if ok else "error")
        else:
            abort(404)
    return redirect(url_for("game.admin"))
