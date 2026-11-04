"""Farglow game rules for engine schema 2 (PoC 1 "First Light").

    step(state, orders, rules) -> new state       pure, deterministic, integers only
    validate(state, rules, order) -> None | str   the same checks the API runs before queueing

The economy follows tools/sim.py formula for formula (population -> action credits ->
allocation; minerals, energy, research, stability), in fixed point (see rules.py). The
decisions sim.py's heuristic player makes (what to build, where to expand, what to research)
are player orders here. Every order is checked twice: by the API when it is queued, and here
when the tick applies it, because the state may have moved on in between.
"""
from __future__ import annotations

import re
from math import gcd, isqrt

from . import galaxy
from .rules import ALLOCATION_KEYS, FP, HABITABLE, Rules, pct_mul

SCHEMA = 2
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 '\-]{0,30}[A-Za-z0-9.']$")
NAMING_WINDOW = 72
MAX_QUEUE = 12
EVENT_KINDS = (
    "founded", "tech_done", "research_started", "survey_done", "system_claimed", "colony_founded",
    "claim_failed", "building_started", "building_done", "developed", "charter_done", "named",
    "order_rejected", "allocation_set", "minerals_capped", "energy_short", "retired", "mission_started",
)


# ---------------------------------------------------------------------------- genesis / upgrade
def genesis(seed: int, rules: Rules, debug_costs: bool = False) -> dict:
    return {
        "schema": SCHEMA, "galaxy_seed": int(seed), "tick": 0, "prev_hash": "0" * 64,
        "cell": galaxy.DEFAULT_CELL, "rules_hash": rules.hash, "options": {"debug_costs": bool(debug_costs)},
        "civs": {}, "systems": {}, "users": {}, "next_civ": 1, "log": [],
    }


def upgrade_from_v1(state: dict, order: dict, rules: Rules) -> dict:
    new = genesis(state["galaxy_seed"], rules, bool(order.get("debug_costs")))
    new["tick"], new["prev_hash"] = state["tick"], state["prev_hash"]
    return new


# ---------------------------------------------------------------------------- small helpers
def _sys(state, sid):
    return state["systems"].setdefault(sid, {"owner": None, "name": None, "discovered_by": None,
                                             "discovered_tick": None, "bodies": {}})


def view(state, sid):
    return galaxy.system_view(state["galaxy_seed"], state["systems"], sid, state["cell"])


def owned_systems(state, cid):
    return sorted(sid for sid, s in state["systems"].items() if s.get("owner") == cid)


def mod_add(civ, key):
    return civ["mods"]["add"].get(key, 0)


def mod_pct(civ, key):
    return civ["mods"]["pct"].get(key, 0)


def _apply_effects(civ, effects, sign=1):
    for e in effects:
        if e.get("conditional"):
            continue
        bucket = civ["mods"]["pct" if e["op"] == "pct" else "add"]
        bucket[e["key"]] = bucket.get(e["key"], 0) + sign * e["value"]


def _event(state, cid, kind, **data):
    state["log"].append({"civ": cid, "kind": kind, **data})


def survey_range(civ, rules):
    curiosity = civ["attributes"].get("curiosity", 0)
    return mod_add(civ, "survey_range_ly") + 500 * curiosity    # +-0.5 ly per curiosity point


def ftl(civ):
    return max(100, pct_mul(mod_add(civ, "ftl_speed_ly_per_tick"), mod_pct(civ, "ftl_speed_ly_per_tick")))


def nearest_owned(state, cid, sid):
    """(distance in mly, from-system) to the nearest system the civ owns."""
    seed, cell = state["galaxy_seed"], state["cell"]
    target = galaxy.by_id(seed, cell)[sid]
    best = None
    for o in owned_systems(state, cid):
        d = galaxy.distance(target, galaxy.by_id(seed, cell)[o])
        if best is None or d < best[0]:
            best = (d, o)
    return best or (10**9, None)


def travel_ticks(civ, dist):
    speed = ftl(civ)
    return max(1, -(-dist // speed))


def pop_cap(civ, rules, kind, body):
    if kind == "ocean" and "outpost_ocean" not in civ["unlocked"]:
        return 0
    cap = rules.pop_capacity.get(kind, 0)
    if body.get("capital"):
        cap += rules.capital_bonus
    if kind in ("rocky", "super_earth"):
        cap += mod_add(civ, "pop_cap_rocky")
    if kind in ("super_earth", "ocean") and cap > 0:
        cap += cap * mod_add(civ, "habitability_step") // (4 * FP)
    if cap > 0 and body.get("building") == "habitat_ring" and body.get("ready"):
        cap += 4 * FP
    return cap


def admin_cost(rules, civ, n):
    if n <= 1:
        return 0
    e = max(1, rules.admin_exponent + mod_add(civ, "admin_cost_exponent"))   # milli, 1300 = ^1.3
    g = gcd(e, FP)
    p, q = e // g, FP // g
    target = n ** p * FP ** q
    lo, hi = 0, 1
    while hi ** q <= target:
        hi *= 2
    while lo < hi - 1:                 # integer q-th root of n^p, milli scaled
        mid = (lo + hi) // 2
        if mid ** q <= target:
            lo = mid
        else:
            hi = mid
    return rules.admin_base * lo // FP


def tech_available(civ, rules, tid):
    t = rules.techs.get(tid)
    if not t or t["repeatable"] or tid in civ["research"]["done"]:
        return False
    if not tier_open(civ, rules, t["tier"]):
        return False
    if any(r not in civ["research"]["done"] for r in t["requires"]):
        return False
    g = t["group"]
    if g and any(rules.techs[d]["group"] == g for d in civ["research"]["done"]):
        return False
    return True


def tier_open(civ, rules, tier):
    unlock = rules.tiers[tier].get("unlock")
    if not unlock:
        return True
    need = unlock["completed_in_tier"]
    return sum(1 for d in civ["research"]["done"] if rules.techs[d]["tier"] == need) >= int(unlock["count"])


def tech_cost(state, civ, rules, tid):
    known = len(rules.known_at_start) + len(civ["research"]["done"])
    return rules.tech_cost(tid, known, state["options"].get("debug_costs", False))


def building_cost(civ, rules, bid):
    spec = rules.buildings[bid]
    f = FP + rules.repeat_cost_growth * civ["building_counts"].get(bid, 0)
    return spec["minerals"] * f // FP, spec["ac"] * f // FP


def claim_cost(civ, rules, colony):
    ac = rules.colony_ac if colony else rules.outpost_ac
    ac = pct_mul(ac, mod_pct(civ, "expansion_cost") + mod_pct(civ, "colonize_cost"))
    return ac, (rules.colony_minerals if colony else rules.outpost_minerals)


def body_can_host(civ, rules, bid, kind, body):
    on = rules.buildings[bid]["on"]
    if on == "any":
        return True
    if on == "populated":
        return body.get("pop", 0) > 0
    return kind in on


# ---------------------------------------------------------------------------- validation
def validate(state: dict, rules: Rules, order: dict) -> str | None:
    """None if the order is allowed now, else a plain-English reason."""
    if state.get("schema") != SCHEMA:
        return "the galaxy is being upgraded; try again after the next tick"
    kind = order.get("kind")
    uid = str(order.get("user", ""))
    if kind == "found":
        return _validate_found(state, rules, order, uid)
    cid = state["users"].get(uid)
    civ = state["civs"].get(cid) if cid else None
    if not civ or not civ["alive"]:
        return "you have no civilization yet"
    if kind == "retire":
        return None
    if kind == "allocation":
        alloc = order.get("allocation") or {}
        if set(alloc) != set(ALLOCATION_KEYS):
            return "allocation needs exactly: " + ", ".join(ALLOCATION_KEYS)
        vals = list(alloc.values())
        if any(not isinstance(v, int) or v < 0 or v > 100 or v % 5 for v in vals):
            return "each share is 0-100 in steps of 5"
        if sum(vals) != 100:
            return "the shares must add up to 100 %"
        return None
    if kind == "research_queue":
        queue = order.get("queue")
        if not isinstance(queue, list) or len(queue) > MAX_QUEUE or len(set(queue)) != len(queue):
            return f"the queue is a list of up to {MAX_QUEUE} different techs"
        for tid in queue:
            if tid not in rules.techs or rules.techs[tid]["repeatable"]:
                return f"unknown tech {tid!r}"
            if tid in civ["research"]["done"]:
                return f"{rules.techs[tid]['name']} is already researched"
            g = rules.techs[tid]["group"]
            if g and any(rules.techs[d]["group"] == g for d in civ["research"]["done"]):
                return f"{rules.techs[tid]['name']} is locked by your doctrine choice"
        return None
    sid = order.get("system")
    if kind in ("survey", "claim", "build", "develop", "name_system"):
        if sid not in galaxy.by_id(state["galaxy_seed"], state["cell"]):
            return "unknown system"
    if kind == "survey":
        if sid in civ["surveyed"]:
            return "already surveyed"
        if any(m["kind"] == "survey" and m["target"] == sid for m in civ["missions"]):
            return "a survey is already on its way there"
        dist, _ = nearest_owned(state, cid, sid)
        if dist > rules.max_reach:
            return f"too far: surveys reach {rules.max_reach // FP} ly from your systems"
        if civ["ledger"]["expansion"] < rules.survey_ac:
            return f"needs {rules.survey_ac // FP} expansion AC (you have {civ['ledger']['expansion'] // FP})"
        return None
    if kind == "claim":
        return _validate_claim(state, rules, civ, cid, order)
    if kind in ("build", "develop"):
        s = state["systems"].get(sid) or {}
        if s.get("owner") != cid:
            return "you don't own that system"
        bodies = view(state, sid)["bodies"]
        bi = order.get("body")
        if not isinstance(bi, int) or not 0 <= bi < len(bodies):
            return "unknown body"
        body = s["bodies"].get(str(bi), {})
        kind_b = bodies[bi]
        if kind == "develop":
            if rules.mineral_yield.get(kind_b, 0) <= 0:
                return "only bodies that yield minerals can be developed"
            if body.get("dev", 0) >= rules.max_dev:
                return "already fully developed"
            need = rules.dev_cost_base * (body.get("dev", 0) + 1)
            if civ["ledger"]["economic"] < need:
                return f"needs {need // FP} economic AC (you have {civ['ledger']['economic'] // FP})"
            return None
        bid = order.get("building")
        if bid not in rules.buildings:
            return "unknown building"
        if body.get("building"):
            return "that body already has a building (one per body)"
        spec = rules.buildings[bid]
        if spec["requires"] and spec["requires"] not in civ["research"]["done"]:
            return f"needs {rules.techs[spec['requires']]['name']}"
        if not body_can_host(civ, rules, bid, kind_b, body):
            return "that building can't go on this kind of body"
        m, ac = building_cost(civ, rules, bid)
        if civ["minerals"] < m:
            return f"needs {m // FP} minerals (you have {civ['minerals'] // FP})"
        if civ["ledger"]["economic"] < ac:
            return f"needs {ac // FP} economic AC (you have {civ['ledger']['economic'] // FP})"
        return None
    if kind == "name_system":
        s = state["systems"].get(sid) or {}
        if s.get("discovered_by") != cid:
            return "only the civilization that discovered a system may name it"
        if s.get("name"):
            return "it already has a name"
        if state["tick"] - (s.get("discovered_tick") or 0) > NAMING_WINDOW:
            return f"the naming right lapsed ({NAMING_WINDOW} ticks after discovery)"
        return _validate_name(order.get("name"), state, "system")
    return f"unknown order {kind!r}"


def _validate_name(name, state, what):
    if not isinstance(name, str) or not NAME_RE.match(name.strip()):
        return f"a {what} name is 2-32 letters, digits, spaces, hyphens or apostrophes"
    low = name.strip().lower()
    taken = {(s.get("name") or "").lower() for s in state["systems"].values()} | \
            {c["name"].lower() for c in state["civs"].values()}
    if low in taken:
        return "that name is taken on this server"
    return None


def _validate_found(state, rules, order, uid):
    if not uid:
        return "no user"
    if uid in state["users"] and state["civs"][state["users"][uid]]["alive"]:
        return "you already lead a civilization"
    err = _validate_name(order.get("name"), state, "civilization")
    if err:
        return err
    if order.get("home_name") and _validate_name(order.get("home_name"), state, "system"):
        return _validate_name(order.get("home_name"), state, "system")
    if order.get("advisor_name") and not NAME_RE.match(str(order["advisor_name"]).strip()):
        return "the advisor's name is 2-32 letters, digits, spaces, hyphens or apostrophes"
    s = order.get("set")
    if not isinstance(s, int) or not 0 <= s < 32:
        return "pick one of the 32 civilization sets"
    attrs = order.get("attributes") or {}
    if set(attrs) != set(rules.attributes):
        return "set all six attributes"
    if any(not isinstance(v, int) or not rules.attr_min <= v <= rules.attr_max for v in attrs.values()):
        return f"attributes run {rules.attr_min} to +{rules.attr_max}"
    if sum(attrs.values()) != rules.attr_sum:
        return "attributes must sum to 0"
    return None


def _validate_claim(state, rules, civ, cid, order):
    sid = order["system"]
    if sid not in civ["surveyed"]:
        return "survey it first"
    s = state["systems"].get(sid) or {}
    bodies = view(state, sid)["bodies"]
    bi = order.get("body")
    if s.get("owner") not in (None, cid):
        return "another civilization holds that system"
    if any(m["kind"] == "claim" and m["target"] == sid and m.get("body") == bi for m in civ["missions"]):
        return "a ship is already on its way"
    colony = bi is not None
    if colony:
        if not isinstance(bi, int) or not 0 <= bi < len(bodies):
            return "unknown body"
        body = s.get("bodies", {}).get(str(bi), {})
        if pop_cap(civ, rules, bodies[bi], body) <= 0:
            return "that world can't hold a population (yet)"
        if body.get("pop", 0) > 0:
            return "already settled"
    elif s.get("owner") == cid:
        return "you already hold that system"
    dist, _ = nearest_owned(state, cid, sid)
    if dist > rules.max_reach:
        return f"too far: ships reach {rules.max_reach // FP} ly from your systems"
    ac, m = claim_cost(civ, rules, colony)
    if civ["ledger"]["expansion"] < ac:
        return f"needs {ac // FP} expansion AC (you have {civ['ledger']['expansion'] // FP})"
    if civ["minerals"] < m:
        return f"needs {m // FP} minerals (you have {civ['minerals'] // FP})"
    return None


# ---------------------------------------------------------------------------- applying orders
def _apply_order(state, rules, order):
    err = validate(state, rules, order)
    uid = str(order.get("user", ""))
    cid = state["users"].get(uid)
    if err:
        _event(state, cid, "order_rejected", order=order.get("kind"), reason=err, user=uid)
        return
    kind = order["kind"]
    if kind == "found":
        _found(state, rules, order, uid)
        return
    civ = state["civs"][cid]
    t = state["tick"]
    if kind == "retire":
        civ["alive"] = False
        for sid in owned_systems(state, cid):
            state["systems"][sid]["owner"] = None
        del state["users"][uid]
        _event(state, cid, "retired")
    elif kind == "allocation":
        civ["allocation"] = {k: order["allocation"][k] for k in ALLOCATION_KEYS}
        _event(state, cid, "allocation_set", allocation=civ["allocation"])
    elif kind == "research_queue":
        civ["research"]["queue"] = list(order["queue"])
        cur = civ["research"]["current"]
        if cur and cur not in order["queue"] and order["queue"] and tech_available(civ, rules, order["queue"][0]):
            civ["research"]["paused"][cur] = civ["research"]["progress"]       # keep progress if you switch
            civ["research"]["current"] = None
    elif kind == "survey":
        civ["ledger"]["expansion"] -= rules.survey_ac
        dist, _ = nearest_owned(state, cid, order["system"])
        eta = t + travel_ticks(civ, dist)
        civ["missions"].append({"kind": "survey", "target": order["system"], "arrive": eta})
        _event(state, cid, "mission_started", mission="survey", system=order["system"], arrive=eta)
    elif kind == "claim":
        colony = order.get("body") is not None
        ac, m = claim_cost(civ, rules, colony)
        civ["ledger"]["expansion"] -= ac
        civ["minerals"] -= m
        dist, _ = nearest_owned(state, cid, order["system"])
        eta = t + travel_ticks(civ, dist)
        civ["missions"].append({"kind": "claim", "target": order["system"], "body": order.get("body"),
                                "arrive": eta, "paid_ac": ac, "paid_m": m})
        _event(state, cid, "mission_started", mission="colony" if colony else "outpost", system=order["system"],
               arrive=eta)
    elif kind == "build":
        m, ac = building_cost(civ, rules, order["building"])
        civ["minerals"] -= m
        civ["ledger"]["economic"] -= ac
        civ["building_counts"][order["building"]] = civ["building_counts"].get(order["building"], 0) + 1
        body = state["systems"][order["system"]]["bodies"].setdefault(str(order["body"]), {})
        body.update(building=order["building"], ready=False, done_tick=t + rules.build_ticks)
        _event(state, cid, "building_started", system=order["system"], body=order["body"],
               building=order["building"], done=t + rules.build_ticks)
    elif kind == "develop":
        body = state["systems"][order["system"]]["bodies"].setdefault(str(order["body"]), {})
        need = rules.dev_cost_base * (body.get("dev", 0) + 1)
        civ["ledger"]["economic"] -= need
        body["dev"] = body.get("dev", 0) + 1
        _event(state, cid, "developed", system=order["system"], body=order["body"], level=body["dev"])
    elif kind == "name_system":
        state["systems"][order["system"]]["name"] = order["name"].strip()
        _event(state, cid, "named", system=order["system"], name=order["name"].strip())


def _found(state, rules, order, uid):
    cid = f"c{state['next_civ']}"
    state["next_civ"] += 1
    homes = [c["home"] for c in state["civs"].values()]
    home = galaxy.pick_home(state["galaxy_seed"], state["systems"], homes, state["cell"])
    st = rules.start
    civ = {
        "id": cid, "name": order["name"].strip(), "set": order["set"], "user": uid,
        "attributes": {k: order["attributes"][k] for k in rules.attributes},
        "advisor": (order.get("advisor_name") or "Tamsin Vey").strip(),
        "founded": state["tick"], "alive": True, "home": home,
        "minerals": st["minerals"], "energy": st["energy"], "stability": st["stability"],
        "fleet_tons": st["fleet_tons"],
        "ledger": {"expansion": 0, "economic": 0, "military": 0},
        "allocation": dict(st["allocation"]),
        "research": {"done": [], "queue": [], "current": None, "progress": 0, "paused": {}, "first": True},
        "mods": {"add": {}, "pct": {}}, "unlocked": sorted(set(rules.start_unlocks)),
        "surveyed": [home], "missions": [], "building_counts": {},
        "charters": {c: {"status": "active", "tick": None} for c in rules.tutorial_charters},
        "last": {},
    }
    _apply_effects(civ, rules.start_effects)
    state["civs"][cid] = civ
    state["users"][uid] = cid
    s = _sys(state, home)
    home_name = (order.get("home_name") or "").strip()
    if not home_name:
        taken = {(x.get("name") or "").lower() for x in state["systems"].values()}
        home_name = next(n for n in ("Hearth", "Lantern", "Ember", "Threshold", "Harbour", "Cradle", "Waymark",
                                     f"{civ['name'][:24]} Prime", galaxy.by_id(state["galaxy_seed"])[home]["designation"])
                         if n.lower() not in taken)
    s.update(owner=cid, name=home_name, discovered_by=cid,
             discovered_tick=state["tick"], override=galaxy.home_override(state["galaxy_seed"], home))
    s["bodies"] = {"1": {"pop": st["population"], "capital": True}}
    _passive_survey(state, rules, cid)
    _event(state, cid, "founded", system=home, name=civ["name"])


# ---------------------------------------------------------------------------- the tick
def step(state: dict, orders: list[dict], rules: Rules) -> dict:
    state["log"] = []
    for order in orders:
        if isinstance(order, dict):
            _apply_order(state, rules, order)
    for cid in sorted(state["civs"], key=lambda c: int(c[1:])):
        civ = state["civs"][cid]
        if civ["alive"]:
            _civ_tick(state, rules, cid, civ)
    return state


def _civ_tick(state, rules, cid, civ):
    t = state["tick"]
    attrs = civ["attributes"]
    owned = owned_systems(state, cid)
    seed = state["galaxy_seed"]

    # buildings finishing this tick
    for sid in owned:
        for bi, body in sorted(state["systems"][sid]["bodies"].items()):
            if body.get("building") and not body.get("ready") and body.get("done_tick", 0) <= t:
                body["ready"] = True
                _event(state, cid, "building_done", system=sid, body=int(bi), building=body["building"])
                _charter(state, rules, civ, cid, "first_building")

    # population growth (logistic) per habitable body
    g = rules.growth_ppm * (FP + rules.per_point * attrs.get("growth", 0)) // FP
    g = pct_mul(g, mod_pct(civ, "pop_growth"))
    total_pop = 0
    for sid in owned:
        kinds = view(state, sid)["bodies"]
        for bi, body in sorted(state["systems"][sid]["bodies"].items()):
            p = body.get("pop", 0)
            if p <= 0:
                continue
            cap = pop_cap(civ, rules, kinds[int(bi)], body)
            if cap > 0:
                p = p + g * p // 1_000_000 * (cap - p) // cap
                p = min(p, cap)
            body["pop"] = p
            total_pop += p

    # stability
    raw_ac = total_pop * rules.ac_per_pop // FP
    social_ac = raw_ac * civ["allocation"]["social"] // 100
    forums = sum(1 for sid in owned for b in state["systems"][sid]["bodies"].values()
                 if b.get("building") == "civic_forum" and b.get("ready"))
    target = (rules.stab_base + rules.stab_per_cohesion * (attrs.get("cohesion", 0) + mod_add(civ, "cohesion") // FP)
              + mod_add(civ, "stability") + 4 * FP * forums
              + rules.social_factor * isqrt(social_ac * FP) // FP
              - rules.stab_per_extra_system * max(0, len(owned) - 1))
    target = max(0, min(100 * FP, target))
    civ["stability"] += max(-rules.stab_drift, min(rules.stab_drift, target - civ["stability"]))
    stab_mult = rules.stab_floor + (FP - rules.stab_floor) * 2 * civ["stability"] // (100 * FP)

    # action credits
    ac = pct_mul(raw_ac * stab_mult // FP, mod_pct(civ, "ac_efficiency"))
    admin = admin_cost(rules, civ, len(owned))
    ac_net = max(0, ac - admin)
    alloc = {k: ac_net * v // 100 for k, v in civ["allocation"].items()}

    # yields
    ind = attrs.get("industry", 0)
    m_in = e_in = r_body = 0
    for sid in owned:
        sv = view(state, sid)
        e_in += rules.attr_mul(pct_mul(rules.star_energy[sv["star"]], mod_pct(civ, "star_energy_yield")), ind)
        rich = FP + rules.metallicity_factor * sv["feh"] // 100
        for bi, kind in enumerate(sv["bodies"]):
            body = state["systems"][sid]["bodies"].get(str(bi), {})
            base = rules.mineral_yield.get(kind, 0) + FP * body.get("dev", 0)
            if kind == "belt":
                base = pct_mul(base, mod_pct(civ, "belt_mineral_yield"))
            if kind == "ice":
                base += mod_add(civ, "ice_mineral_yield")
            if kind == "verdant":
                base = pct_mul(base, mod_pct(civ, "verdant_peak_yield"))
            ready = body.get("ready")
            if ready and body.get("building") == "extraction_complex":
                base += 2 * FP
            m_in += pct_mul(rules.attr_mul(base * rich // FP, ind), mod_pct(civ, "mineral_yield"))
            if kind == "gas_giant":
                e_in += rules.gas_giant_energy + mod_add(civ, "gas_giant_energy")
                r_body += rules.gas_giant_research
            if ready and body.get("building") == "fusion_plant":
                e_in += 3 * FP
            if ready and body.get("building") == "research_station":
                r_body += 2 * FP
    e_in = pct_mul(e_in, mod_pct(civ, "energy_yield"))
    e_out = rules.energy_upkeep_per_system * len(owned) + mod_add(civ, "energy_upkeep")
    m_out = civ["fleet_tons"] * rules.fleet_upkeep_pct // (100 * FP) + mod_add(civ, "mineral_upkeep")
    for sid in owned:
        for b in state["systems"][sid]["bodies"].values():
            if b.get("building") and b.get("ready"):
                spec = rules.buildings[b["building"]]
                e_out += spec["upkeep_energy"]
                m_out += spec["upkeep_minerals"]
    m_out = pct_mul(m_out, mod_pct(civ, "fleet_upkeep")) if mod_pct(civ, "fleet_upkeep") else m_out
    short = civ["energy"] <= 0
    if short:
        m_in = m_in * (100 - rules.shortage_penalty_pct) // 100

    # research
    rp = alloc["research"] * rules.rp_per_ac // FP
    rp = rules.attr_mul(rp, attrs.get("curiosity", 0))
    rp = pct_mul(pct_mul(rp, mod_pct(civ, "research_output")), mod_pct(civ, "research_efficiency")) + r_body
    if short:
        rp = rp * (100 - rules.shortage_penalty_pct) // 100
    _research(state, rules, civ, cid, rp)

    # military: hulls from the military ledger (fleets and combat arrive in Phase 2)
    civ["ledger"]["military"] += alloc["military"]
    build = min(civ["ledger"]["military"] * rules.tons_per_ac // FP,
                max(0, civ["minerals"] - rules.outpost_minerals) // 2)
    if build > 0:
        civ["fleet_tons"] += build
        civ["minerals"] -= build * rules.minerals_per_ton // FP
        civ["ledger"]["military"] -= build * FP // rules.tons_per_ac
    civ["fleet_tons"] -= civ["fleet_tons"] * rules.age_wear_pct // (100 * FP)

    # stockpiles
    storage = rules.mineral_storage_per_system * max(1, len(owned)) + 2000 * FP * sum(
        1 for sid in owned for b in state["systems"][sid]["bodies"].values()
        if b.get("building") == "warehouse" and b.get("ready"))
    before = civ["minerals"] + m_in - m_out
    civ["minerals"] = max(0, min(before, storage))
    if before > storage and not civ["last"].get("capped"):
        _event(state, cid, "minerals_capped", storage=storage)
    civ["energy"] = max(0, min(rules.energy_storage, civ["energy"] + e_in - e_out))
    if civ["energy"] == 0 and not short:
        _event(state, cid, "energy_short")

    # ledgers bank up to bank_ticks of income
    cap = ac_net * rules.bank_ticks
    for k in ("expansion", "economic"):
        civ["ledger"][k] = min(civ["ledger"][k] + alloc[k], max(cap, civ["ledger"][k]))
    civ["ledger"]["military"] = min(civ["ledger"]["military"], max(cap, 0))

    _missions(state, rules, civ, cid)
    _passive_survey(state, rules, cid)

    civ["last"] = {"tick": t, "pop": total_pop, "ac": ac, "admin": admin, "ac_net": ac_net, "alloc": alloc,
                   "rp": rp, "m_in": m_in, "m_out": m_out, "e_in": e_in, "e_out": e_out, "storage": storage,
                   "stability_target": target, "capped": before > storage, "systems": len(owned)}


def _research(state, rules, civ, cid, rp):
    r = civ["research"]
    if r["current"] is None:
        nxt = next((tid for tid in r["queue"] if tech_available(civ, rules, tid)), None)
        if nxt is None:      # governor default: the research focus order, then the cheapest
            nxt = next((tid for tid in rules.research_priority if tech_available(civ, rules, tid)), None)
        if nxt is None:
            avail = sorted(tid for tid in rules.techs if tech_available(civ, rules, tid))
            nxt = min(avail, key=lambda x: (tech_cost(state, civ, rules, x), x)) if avail else None
        if nxt is None:
            return
        r["current"] = nxt
        if nxt in r["paused"]:
            r["progress"] = r["paused"].pop(nxt)
        elif r.get("first"):
            r["progress"] = tech_cost(state, civ, rules, nxt) * rules.start["head_start_pct"] // 100
            r["first"] = False
        else:
            r["progress"] = 0
        _event(state, cid, "research_started", tech=nxt)
    r["progress"] += rp
    cost = tech_cost(state, civ, rules, r["current"])
    if r["progress"] >= cost:
        tid = r["current"]
        r["progress"] -= cost
        r["done"].append(tid)
        r["current"] = None
        if tid in r["queue"]:
            r["queue"].remove(tid)
        t = rules.techs[tid]
        _apply_effects(civ, t["effects"])
        _apply_effects(civ, t["drawbacks"])
        civ["unlocked"] = sorted(set(civ["unlocked"]) | set(t["unlocks"]))
        _event(state, cid, "tech_done", tech=tid)
        _charter(state, rules, civ, cid, "first_tech")


def _missions(state, rules, civ, cid):
    t = state["tick"]
    keep = []
    for m in civ["missions"]:
        if m["arrive"] > t:
            keep.append(m)
            continue
        sid = m["target"]
        if m["kind"] == "survey":
            _reveal(state, civ, cid, sid)
            _event(state, cid, "survey_done", system=sid)
            _charter(state, rules, civ, cid, "first_survey")
            continue
        s = _sys(state, sid)
        bodies = view(state, sid)["bodies"]
        if s.get("owner") not in (None, cid):
            civ["ledger"]["expansion"] += m["paid_ac"]
            civ["minerals"] += m["paid_m"]
            _event(state, cid, "claim_failed", system=sid, reason="another civilization got there first")
            continue
        s["owner"] = cid
        if m.get("body") is not None:
            body = s["bodies"].setdefault(str(m["body"]), {})
            if body.get("pop", 0) <= 0 and pop_cap(civ, rules, bodies[m["body"]], body) > 0:
                body["pop"] = rules.colony_start
            _event(state, cid, "colony_founded", system=sid, body=m["body"])
        else:
            _event(state, cid, "system_claimed", system=sid)
        _charter(state, rules, civ, cid, "first_outpost")
    civ["missions"] = keep


def _reveal(state, civ, cid, sid):
    if sid in civ["surveyed"]:
        return
    civ["surveyed"].append(sid)
    civ["surveyed"].sort()
    s = _sys(state, sid)
    if s.get("discovered_by") is None:
        s["discovered_by"], s["discovered_tick"] = cid, state["tick"]


def _passive_survey(state, rules, cid):
    civ = state["civs"][cid]
    rng_ly = survey_range(civ, rules)
    seed, cell = state["galaxy_seed"], state["cell"]
    systems = galaxy.by_id(seed, cell)
    for o in owned_systems(state, cid):
        origin = systems[o]
        for sid, s in systems.items():
            if sid not in civ["surveyed"] and galaxy.distance(origin, s) <= rng_ly:
                _reveal(state, civ, cid, sid)


def _charter(state, rules, civ, cid, cid_charter):
    c = civ["charters"].get(cid_charter)
    if not c or c["status"] != "active":
        return
    c.update(status="completed", tick=state["tick"])
    civ["minerals"] += rules.tutorial_reward
    _event(state, cid, "charter_done", charter=cid_charter, reward=rules.tutorial_reward)
