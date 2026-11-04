"""The advisor. It proposes; the player confirms; the engine decides.

* Suggestions are rule-based at every tier (T0): each one carries a ready-made order the
  player can confirm with one click. The order still goes through validation.
* Questions are answered from the Codex. At T0 the best-matching article is quoted. At T1+
  the LLM gateway gets the question, the matching articles and a fog-of-war summary of the
  civilization (only what it knows), and must answer as JSON {"text": ...}; any failure falls
  back to the T0 answer.
"""
from __future__ import annotations

import json
import re
import urllib.request
from functools import lru_cache

import yaml

from ..engine import galaxy, game
from ..engine.rules import FP, Rules, config_dir
from .view import n, system_name

WORD = re.compile(r"[a-z]+")


@lru_cache(maxsize=1)
def codex() -> list[dict]:
    data = yaml.safe_load((config_dir() / "codex.poc.yaml").read_text(encoding="utf-8"))
    return data["articles"]


def _stem(w: str) -> str:
    """Light stemming so 'surveys', 'surveying' and 'survey' meet."""
    for suffix in ("ing", "es", "s"):
        if len(w) > len(suffix) + 3 and w.endswith(suffix):
            return w[: -len(suffix)]
    return w


def search(question: str, limit: int = 2) -> list[dict]:
    words = {_stem(w) for w in WORD.findall(question.lower())}
    scored = []
    for a in codex():
        score = sum(3 for k in a["keywords"] if _stem(k) in words) + \
            sum(1 for w in WORD.findall(a["title"].lower()) if _stem(w) in words)
        if score:
            scored.append((score, a["id"], a))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [a for _, _, a in scored[:limit]]


def suggestions(state: dict, civ: dict, rules: Rules) -> list[dict]:
    """Up to three things worth doing now, most useful first. Each has an order to confirm."""
    out = []
    uid = int(civ["user"])
    r = civ["research"]
    last = civ.get("last") or {}

    def ok(order):
        return game.validate(state, rules, dict(order, user=uid)) is None

    # 1. research: keep a queue
    if not r["queue"]:
        avail = [t for t in rules.research_priority if game.tech_available(civ, rules, t) and t != r["current"]]
        if avail:
            t = rules.techs[avail[0]]
            cost = game.tech_cost(state, civ, rules, t["id"])
            rp = last.get("rp", 0)
            out.append({"title": f"Queue research: {t['name']}",
                        "text": f"{t['description']} Costs {n(cost)} RP"
                                + (f", about {-(-cost // rp)} ticks at your current rate." if rp else "."),
                        "order": {"kind": "research_queue", "queue": [t["id"]]}, "confirm": "Queue it"})
    # 2. explore: survey the nearest unknown system in reach
    if not any(m["kind"] == "survey" for m in civ["missions"]):
        cands = []
        systems = galaxy.by_id(state["galaxy_seed"], state["cell"])
        for sid in systems:
            if sid in civ["surveyed"]:
                continue
            d, _ = game.nearest_owned(state, civ["id"], sid)
            if d <= rules.max_reach:
                cands.append((d, sid))
        cands.sort()
        if cands and ok({"kind": "survey", "system": cands[0][1]}):
            d, sid = cands[0]
            out.append({"title": f"Survey {system_name(state, sid)}",
                        "text": f"The nearest unknown star, {n(d, 1)} ly out. A survey wing costs "
                                f"{n(rules.survey_ac)} expansion AC and arrives in {game.travel_ticks(civ, d)} ticks.",
                        "order": {"kind": "survey", "system": sid}, "confirm": "Send it"})
    # 3. expand: the best surveyed, unclaimed system in reach
    if not any(m["kind"] == "claim" for m in civ["missions"]):
        best = None
        for sid in civ["surveyed"]:
            st = state["systems"].get(sid) or {}
            if st.get("owner"):
                continue
            d, _ = game.nearest_owned(state, civ["id"], sid)
            if d > rules.max_reach:
                continue
            v = game.view(state, sid)
            hab = [i for i, k in enumerate(v["bodies"]) if game.pop_cap(civ, rules, k, {}) > 0]
            value = sum(rules.mineral_yield.get(k, 0) for k in v["bodies"]) + rules.star_energy[v["star"]] + \
                (20 * FP if hab else 0)
            key = (-value, d, sid)
            if best is None or key < best[0]:
                best = (key, sid, hab, d)
        if best:
            _, sid, hab, d = best
            order = {"kind": "claim", "system": sid, **({"body": hab[0]} if hab else {})}
            ac, m = game.claim_cost(civ, rules, bool(hab))
            if ok(order):
                out.append({"title": f"{'Colonize' if hab else 'Claim'} {system_name(state, sid)}",
                            "text": f"{'It has a world your people can live on. ' if hab else ''}"
                                    f"{n(ac)} AC and {n(m)} minerals, {n(d, 1)} ly away.",
                            "order": order, "confirm": "Send the ship"})
            else:
                have = civ["ledger"]["expansion"]
                out.append({"title": f"Save up for {system_name(state, sid)}",
                            "text": f"Claiming it takes {n(ac)} expansion AC (you have {n(have)}) and {n(m)} "
                                    "minerals. More expansion share in the Governor gets you there sooner.",
                            "order": None})
    # 4. build: the first building, or when minerals are near the cap
    storage = last.get("storage", 0)
    if civ["building_counts"] == {} or (storage and civ["minerals"] * 10 >= storage * 8):
        home = civ["home"]
        kinds = game.view(state, home)["bodies"]
        for bid, prefer in (("extraction_complex", ("belt", "rocky")), ("research_station", ("gas_giant",)),
                            ("warehouse", ("ice",))):
            for bi, kind in enumerate(kinds):
                if kind in prefer and ok({"kind": "build", "system": home, "body": bi, "building": bid}):
                    m, ac = game.building_cost(civ, rules, bid)
                    out.append({"title": f"Build a {bid.replace('_', ' ')} on {system_name(state, home)} {['I','II','III','IV','V'][bi]}",
                                "text": f"{rules.buildings[bid]['effect']}. {n(m)} minerals and {n(ac)} economic AC; "
                                        f"ready in {rules.build_ticks} ticks.",
                                "order": {"kind": "build", "system": home, "body": bi, "building": bid},
                                "confirm": "Build it"})
                    break
            else:
                continue
            break
    # 5. stability
    if civ["stability"] < 45 * FP and civ["allocation"]["social"] < 30:
        a = dict(civ["allocation"])
        donor = max((k for k in a if k != "social"), key=lambda k: a[k])
        if a[donor] >= 5:
            a[donor] -= 5
            a["social"] += 5
            out.append({"title": "Spend a little more on social",
                        "text": f"Stability is {n(civ['stability'])}. Moving 5 % from {donor} to social raises its "
                                "target, and higher stability means more action credits.",
                        "order": {"kind": "allocation", "allocation": a}, "confirm": "Shift 5 %"})
    for t in out:      # a plain string, so templates HTML-escape it inside value="..."
        t["order_json"] = json.dumps(t["order"], sort_keys=True) if t.get("order") else ""
    return out[:3]


def summary(state: dict, civ: dict, rules: Rules) -> str:
    """What the civilization knows, for the model's context. Fog of war applies to the AI too."""
    last = civ.get("last") or {}
    r = civ["research"]
    lines = [
        f"Civilization: {civ['name']}. Tick {state['tick']}.",
        f"Population {n(last.get('pop', 0), 1)}, stability {n(civ['stability'])}, AC {n(last.get('ac_net', 0))}/tick.",
        f"Minerals {n(civ['minerals'])} of {n(last.get('storage', 0))}, energy {n(civ['energy'])}.",
        f"Banked: expansion {n(civ['ledger']['expansion'])} AC, economic {n(civ['ledger']['economic'])} AC.",
        f"Allocation: " + ", ".join(f"{k} {v}%" for k, v in civ["allocation"].items()) + ".",
        f"Researching: {rules.techs[r['current']]['name'] if r['current'] else 'nothing'}; known techs: "
        + (", ".join(rules.techs[t]["name"] for t in r["done"]) or "none yet") + ".",
        f"Systems owned: " + ", ".join(system_name(state, s) for s in game.owned_systems(state, civ["id"])) + ".",
        f"Systems surveyed: {len(civ['surveyed'])}.",
    ]
    return "\n".join(lines)


def answer(question: str, state: dict, civ: dict, rules: Rules, gateway_url: str, tier: str) -> dict:
    """{'text', 'tier', 'fallback', 'sources'}"""
    found = search(question)
    words = set(WORD.findall(question.lower()))
    if not found and words & {"first", "next", "should", "start", "begin", "now", "recommend", "advice", "priority"}:
        tips = suggestions(state, civ, rules)
        t0_text = ("Here is what I would do now: " + " ".join(f"{i + 1}. {t['title']}: {t['text']}" for i, t in enumerate(tips))
                   if tips else "Nothing urgent. Let a few ticks pass, then read the Dispatch.")
    else:
        t0_text = (" ".join(a["text"].strip() for a in found[:1]) if found else
                   "I can only answer questions about the game. Try asking about action credits, research, "
                   "surveys, outposts, buildings, stability or the Dispatch.")
    sources = [a["title"] for a in found]
    if tier == "T0" or not gateway_url:
        return {"text": t0_text, "tier": "T0", "fallback": False, "sources": sources}
    prompt = (
        f"You are {civ['advisor']}, chief of staff to the {civ['name']} in the game Farglow. "
        "Answer the player's question in 2-4 plain sentences, using ONLY the Codex articles and the "
        "civilization summary below. Never invent rules or numbers; if the articles don't cover it, say so. "
        'Reply as JSON: {"text": "..."}\n\n'
        "CODEX:\n" + "\n".join(f"[{a['title']}] {a['text'].strip()}" for a in found) +
        "\n\nCIVILIZATION (what it knows):\n" + summary(state, civ, rules) +
        f"\n\nQUESTION: {question[:500]}"
    )
    try:
        req = urllib.request.Request(f"{gateway_url}/v1/propose", method="POST",
                                     data=json.dumps({"task": "advisor.answer", "prompt": prompt}).encode(),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=90) as resp:  # noqa: S310 - internal service
            out = json.loads(resp.read())
        text = out.get("proposal", {}).get("text")
        if not isinstance(text, str) or not text.strip() or out.get("fallback"):
            raise ValueError("no answer")
        return {"text": text.strip()[:1500], "tier": out.get("tier", tier), "fallback": False, "sources": sources}
    except Exception:  # noqa: BLE001 - every feature works at T0
        return {"text": t0_text, "tier": "T0", "fallback": True, "sources": sources}
