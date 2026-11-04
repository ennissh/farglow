"""How engine events read, in the Dispatch and in email. T0: templates only."""
from __future__ import annotations

from ..engine.rules import FP, Rules
from .view import system_name

SKIP = {"allocation_set"}


def render(ev: dict, state: dict, rules: Rules, civ: dict | None = None) -> tuple[str, str] | None:
    """(headline, detail) for one event, or None if it isn't news. Names follow `civ`'s fog of war."""
    k = ev["kind"]
    if k in SKIP:
        return None
    sysname = system_name(state, ev["system"], civ) if ev.get("system") and ev["system"] in _all(state) else ""
    tech = rules.techs.get(ev.get("tech", ""), {}).get("name", ev.get("tech", ""))
    building = (ev.get("building") or "").replace("_", " ")
    if k == "founded":
        return (f"{ev['name']} is founded at {sysname}", "Your people look up at a sky full of unknown stars.")
    if k == "research_started":
        return (f"Research begins on {tech}", "Your scientists have a new focus.")
    if k == "tech_done":
        t = rules.techs.get(ev["tech"], {})
        return (f"{tech} is complete", t.get("description", ""))
    if k == "survey_done":
        return (f"Survey of {sysname} is back", "Its star and worlds are now on your charts.")
    if k == "mission_started":
        what = {"survey": "A survey wing", "outpost": "An outpost convoy", "colony": "A colony ship"}[ev["mission"]]
        return (f"{what} leaves for {sysname}", f"Expected at tick {ev['arrive']:,}.")
    if k == "system_claimed":
        return (f"Outpost established at {sysname}", "The system's worlds now count toward your yields.")
    if k == "colony_founded":
        return (f"Colonists land at {sysname}", "A new world begins to grow.")
    if k == "claim_failed":
        return (f"Claim on {sysname} failed", f"{ev.get('reason', '')}. Your AC and minerals were refunded.")
    if k == "building_started":
        return (f"Construction starts: {building} at {sysname}", f"Ready at tick {ev['done']:,}.")
    if k == "building_done":
        return (f"The {building} at {sysname} is finished", "")
    if k == "developed":
        return (f"{sysname} developed to level {ev['level']}", "+1 mineral a tick on that body.")
    if k == "charter_done":
        return (f"Charter complete: {ev['charter'].replace('_', ' ')}", f"Reward: {ev['reward'] // FP:,} minerals.")
    if k == "named":
        return (f"A star gets a name: {ev['name']}", "It goes into the galactic catalogue for good.")
    if k == "minerals_capped":
        return ("Mineral stores are full", f"Storage holds {ev['storage'] // FP:,}. Anything over is lost: build or expand.")
    if k == "energy_short":
        return ("Energy reserves are empty", "Minerals and research drop 10 % until energy recovers.")
    if k == "order_rejected":
        return (f"An order could not be carried out ({ev.get('order', '')})", ev.get("reason", ""))
    if k == "retired":
        return ("Your civilization has left the galaxy", "")
    return None


def _all(state):
    from ..engine import galaxy
    return galaxy.by_id(state["galaxy_seed"], state["cell"])
