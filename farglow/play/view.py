"""Fog-of-war views of the engine state for one civilization (pages, the map, the advisor)."""
from __future__ import annotations

from ..engine import galaxy, game
from ..engine.rules import FP, HABITABLE, Rules

BODY_LABEL = {"rocky": "Rocky", "super_earth": "Super-Earth", "verdant": "Verdant", "ocean": "Ocean world",
              "gas_giant": "Gas giant", "ice": "Ice giant", "belt": "Asteroid belt"}
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X"]


def n(x: int, places: int = 0) -> str:
    """Fixed-point to display: 12345 -> '12' (places=0) or '12.3' (places=1)."""
    v = x / FP
    return f"{v:,.{places}f}"


def civ_of(state: dict, user_id: int) -> dict | None:
    cid = state.get("users", {}).get(str(user_id))
    civ = state.get("civs", {}).get(cid) if cid else None
    return civ if civ and civ["alive"] else None


def system_name(state: dict, sid: str, civ: dict | None = None) -> str:
    """The system's name, as far as `civ` knows: a name another civilization gave is only
    known once you have surveyed the system (fog of war). Without `civ`: the true name."""
    s = state["systems"].get(sid) or {}
    if s.get("name") and (civ is None or sid in civ["surveyed"]):
        return s["name"]
    return galaxy.by_id(state["galaxy_seed"], state["cell"])[sid]["designation"]


def tier_label(civ: dict, rules: Rules) -> str:
    tier = "Reach"
    for t in ("lattice", "concord"):
        if game.tier_open(civ, rules, t):
            tier = rules.tiers[t]["name"]
    return tier


def header(state: dict, civ: dict | None, rules: Rules) -> dict:
    if civ is None:
        return {}
    last = civ.get("last") or {}
    storage = last.get("storage", 0)
    return {"tier": tier_label(civ, rules), "ac": n(last.get("ac_net", 0)), "population": n(last.get("pop", 0), 1),
            "rp": n(last.get("rp", 0), 1), "minerals": n(civ["minerals"]), "storage": n(storage),
            "minerals_full": bool(storage) and civ["minerals"] * 10 >= storage * 9,
            "energy": n(civ["energy"]), "energy_max": n(rules.energy_storage), "energy_low": civ["energy"] == 0,
            "stability": n(civ["stability"]), "stability_low": civ["stability"] < 45 * FP,
            "exp": n(civ["ledger"]["expansion"]), "eco": n(civ["ledger"]["economic"]),
            "systems": len(game.owned_systems(state, civ["id"]))}


def map_data(state: dict, civ: dict, rules: Rules) -> dict:
    """Everything the star map draws. Unsurveyed stars are dots with a designation only."""
    seed, cell = state["galaxy_seed"], state["cell"]
    surveyed = set(civ["surveyed"])
    out = []
    for s in galaxy.generate(seed, cell):
        sid = s["id"]
        st = state["systems"].get(sid) or {}
        owner = st.get("owner")
        item = {"id": sid, "x": s["x"], "y": s["y"], "name": system_name(state, sid, civ), "surveyed": sid in surveyed,
                "named": bool(st.get("name")) and sid in surveyed}
        if sid in surveyed:
            v = game.view(state, sid)
            item.update(star=v["star"], cls=f"{v['star']}{v['subclass']} V", bodies=len(v["bodies"]),
                        mine=owner == civ["id"], other=bool(owner) and owner != civ["id"],
                        home=sid == civ["home"])
        out.append(item)
    missions = [{"kind": m["kind"], "target": m["target"], "arrive": m["arrive"]} for m in civ["missions"]]
    return {"systems": out, "survey_range": game.survey_range(civ, rules), "reach": rules.max_reach,
            "owned": game.owned_systems(state, civ["id"]), "missions": missions, "home": civ["home"],
            "size": galaxy.CELL_SIZE_MLY, "tick": state["tick"]}


def system_detail(state: dict, civ: dict, rules: Rules, sid: str) -> dict:
    seed, cell = state["galaxy_seed"], state["cell"]
    base = galaxy.by_id(seed, cell)[sid]
    st = state["systems"].get(sid) or {}
    surveyed = sid in civ["surveyed"]
    dist, _ = game.nearest_owned(state, civ["id"], sid)
    d = {"id": sid, "name": system_name(state, sid, civ), "designation": base["designation"], "surveyed": surveyed,
         "distance": dist, "distance_ly": n(dist, 1), "ticks": game.travel_ticks(civ, dist) if dist < 10**8 else None,
         "owner": st.get("owner"), "mine": st.get("owner") == civ["id"], "home": sid == civ["home"],
         "missions": [m for m in civ["missions"] if m["target"] == sid], "in_reach": dist <= rules.max_reach}
    if st.get("owner") and st["owner"] != civ["id"]:
        d["owner_name"] = state["civs"][st["owner"]]["name"]
    d["can_name"] = (st.get("discovered_by") == civ["id"] and not st.get("name")
                     and state["tick"] - (st.get("discovered_tick") or 0) <= game.NAMING_WINDOW)
    if not surveyed:
        d.update(survey_cost=n(rules.survey_ac), can_survey=game.validate(state, rules, {
            "kind": "survey", "system": sid, "user": int(civ["user"])}))
        return d
    v = game.view(state, sid)
    d.update(star=v["star"], cls=f"{v['star']}{v['subclass']} V", multiple=v["multiple"], feh=v["feh"])
    ind = civ["attributes"].get("industry", 0)
    rich = FP + rules.metallicity_factor * v["feh"] // 100
    bodies = []
    for bi, kind in enumerate(v["bodies"]):
        b = st.get("bodies", {}).get(str(bi), {})
        minerals = rules.mineral_yield.get(kind, 0) + FP * b.get("dev", 0)
        if b.get("ready") and b.get("building") == "extraction_complex":
            minerals += 2 * FP
        cap = game.pop_cap(civ, rules, kind, b)
        row = {
            "index": bi, "name": f"{d['name']} {ROMAN[bi] if bi < len(ROMAN) else bi + 1}", "kind": kind,
            "label": BODY_LABEL[kind], "minerals": n(rules.attr_mul(minerals * rich // FP, ind), 1) if minerals else "",
            "energy": n(rules.gas_giant_energy) if kind == "gas_giant" else "",
            "research": n(rules.gas_giant_research) if kind == "gas_giant" else "",
            "population": n(b.get("pop", 0), 1) if b.get("pop") else "", "cap": n(cap) if cap else "",
            "habitable": cap > 0, "capital": b.get("capital", False), "dev": b.get("dev", 0),
            "building": b.get("building"), "ready": b.get("ready", False), "done_tick": b.get("done_tick"),
        }
        if d["mine"]:
            row["build_options"] = []
            if not b.get("building"):
                for bid in rules.buildings:
                    m, ac = game.building_cost(civ, rules, bid)
                    err = game.validate(state, rules, {"kind": "build", "system": sid, "body": bi, "building": bid,
                                                       "user": int(civ["user"])})
                    if err and ("can't go on" in err or "needs Relay" in err):
                        continue
                    row["build_options"].append({"id": bid, "minerals": n(m), "ac": n(ac), "error": err,
                                                 "effect": rules.buildings[bid]["effect"]})
            if rules.mineral_yield.get(kind, 0) > 0 and b.get("dev", 0) < rules.max_dev:
                row["develop_cost"] = n(rules.dev_cost_base * (b.get("dev", 0) + 1))
                row["develop_error"] = game.validate(state, rules, {"kind": "develop", "system": sid, "body": bi,
                                                                    "user": int(civ["user"])})
        if cap > 0 and not b.get("pop"):
            ac, m = game.claim_cost(civ, rules, True)
            row["colony"] = {"ac": n(ac), "minerals": n(m), "error": game.validate(state, rules, {
                "kind": "claim", "system": sid, "body": bi, "user": int(civ["user"])})}
        bodies.append(row)
    d["bodies"] = bodies
    d["star_energy"] = n(rules.star_energy[v["star"]])
    if not st.get("owner"):
        ac, m = game.claim_cost(civ, rules, False)
        d["outpost"] = {"ac": n(ac), "minerals": n(m), "error": game.validate(state, rules, {
            "kind": "claim", "system": sid, "user": int(civ["user"])})}
    return d


def research_view(state: dict, civ: dict, rules: Rules) -> dict:
    r = civ["research"]
    rp = (civ.get("last") or {}).get("rp", 0)
    tiers = []
    for tid_tier, tier in sorted(rules.tiers.items(), key=lambda kv: kv[1]["order"]):
        nodes = [t for t in rules.techs.values() if t["tier"] == tid_tier and not t["repeatable"]]
        rows = []
        for t in nodes:
            cost = game.tech_cost(state, civ, rules, t["id"])
            status = ("done" if t["id"] in r["done"] else "current" if t["id"] == r["current"]
                      else "available" if game.tech_available(civ, rules, t["id"])
                      else "locked")
            if t["group"] and status == "locked" and any(rules.techs[x]["group"] == t["group"] for x in r["done"]):
                status = "excluded"
            rows.append({**t, "cost": n(cost), "cost_raw": cost, "status": status,
                         "ticks": -(-cost // rp) if rp else None, "queued": t["id"] in r["queue"],
                         "requires_names": [rules.techs[x]["name"] for x in t["requires"]]})
        done = sum(1 for t in nodes if t["id"] in r["done"])
        tiers.append({"id": tid_tier, "name": tier["name"], "order": tier["order"], "open": game.tier_open(civ, rules, tid_tier),
                      "done": done, "total": len(nodes), "nodes": rows, "unlock": tier.get("unlock")})
    cur = r["current"]
    current = None
    if cur:
        cost = game.tech_cost(state, civ, rules, cur)
        current = {"id": cur, "name": rules.techs[cur]["name"], "progress": n(r["progress"]), "cost": n(cost),
                   "pct": min(100, r["progress"] * 100 // cost), "ticks": -(-(cost - r["progress"]) // rp) if rp else None}
    known = len(rules.known_at_start) + len(r["done"])
    return {"tiers": tiers, "current": current, "queue": [{"id": q, "name": rules.techs[q]["name"]} for q in r["queue"]],
            "known": known, "tax_pct": rules.knowledge_tax * known // 10, "rp": n(rp, 1),
            "start_names": [rules.start_names[k] for k in rules.known_at_start]}


def effect_text(e: dict) -> str:
    v = e["value"] / FP
    sign = "+" if v >= 0 else ""
    num = f"{v:g}"
    unit = " %" if e["op"] == "pct" else ""
    return f"{sign}{num}{unit} {e['key'].replace('_', ' ')}"


def known_systems(state: dict, civ: dict, rules: Rules) -> list[dict]:
    """Every system the civilization has surveyed, nearest first (yours on top): the dense list."""
    rows = []
    for sid in civ["surveyed"]:
        st = state["systems"].get(sid) or {}
        v = game.view(state, sid)
        dist, _ = game.nearest_owned(state, civ["id"], sid)
        owner = st.get("owner")
        hab = sum(1 for i, k in enumerate(v["bodies"]) if game.pop_cap(civ, rules, k, st.get("bodies", {}).get(str(i), {})) > 0)
        minerals = sum(rules.mineral_yield.get(k, 0) for k in v["bodies"])
        rows.append({"id": sid, "name": system_name(state, sid, civ), "cls": f"{v['star']}{v['subclass']} V",
                     "dist": dist, "dist_ly": n(dist, 1) if owner != civ["id"] else "–", "bodies": len(v["bodies"]),
                     "habitable": hab, "minerals": n(minerals), "mine": owner == civ["id"],
                     "owner": state["civs"][owner]["name"] if owner and owner != civ["id"] else "",
                     "home": sid == civ["home"], "in_reach": dist <= rules.max_reach,
                     "underway": any(m["target"] == sid for m in civ["missions"])})
    rows.sort(key=lambda r: (not r["mine"], r["dist"], r["id"]))
    return rows
