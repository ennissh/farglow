"""Farglow PoC economy simulator: one civilization, no combat, hourly ticks.

Reads balance.poc.yaml and tech_tree.poc.yaml, plays a simple heuristic player,
and reports pacing milestones so the numbers can be checked against targets.
Usage: python sim.py balance.poc.yaml tech_tree.poc.yaml [ticks]
"""
import math
import sys

import yaml

B = yaml.safe_load(open(sys.argv[1]))
T = yaml.safe_load(open(sys.argv[2]))
TICKS = int(sys.argv[3]) if len(sys.argv) > 3 else 2400

ATTR = B["start"]["attributes"]
Y = B["yields"]
POP = B["population"]
AC = B["action_credits"]
EXP = B["expansion"]
ECO = B["economy"]
STAB = B["stability"]
RES = B["research"]
MIL = B["military"]
BLD = B["buildings"]
built_count = {}

# ---- tech effects the economy cares about ---------------------------------
mods = {k: 0.0 for k in [
    "research_output", "research_efficiency", "mineral_yield", "belt_mineral_yield", "ice_mineral_yield",
    "star_energy_yield", "gas_giant_energy", "pop_growth", "pop_cap_rocky", "habitability_step",
    "stability", "cohesion", "ac_efficiency", "expansion_cost", "colonize_cost", "energy_upkeep",
    "mineral_upkeep", "verdant_peak_yield"]}
unlocked = set()


def apply(effects, sign=1):
    for e in effects or []:
        k = e["key"]
        if k in mods and not e.get("per") and not e.get("while"):
            mods[k] += e["value"] * sign


# ---- systems ---------------------------------------------------------------
def body(kind, **kw):
    return {"kind": kind, "dev": 0, **kw}


home = {"name": "Hearth", "star": "K", "feh": 0.08, "bodies": [
    body("rocky"), body("verdant", capital=True), body("gas_giant"), body("belt"), body("ice")]}
candidates = [
    {"name": "Talmar", "star": "K", "feh": 0.12, "dist": 4.1, "bodies": [body("rocky"), body("super_earth"), body("ocean"), body("belt")]},
    {"name": "Oriel", "star": "M", "feh": -0.05, "dist": 5.2, "bodies": [body("rocky"), body("belt")]},
    {"name": "Wren's Lamp", "star": "M", "feh": 0.0, "dist": 3.3, "bodies": [body("belt"), body("belt")]},
    {"name": "Sector star 4", "star": "G", "feh": 0.02, "dist": 6.8, "bodies": [body("rocky"), body("gas_giant"), body("verdant")]},
    {"name": "Sector star 5", "star": "M", "feh": -0.1, "dist": 7.5, "bodies": [body("rocky"), body("ice")]},
    {"name": "Sector star 6", "star": "K", "feh": 0.05, "dist": 8.9, "bodies": [body("super_earth"), body("belt"), body("gas_giant")]},
    {"name": "Sector star 7", "star": "M", "feh": 0.0, "dist": 9.6, "bodies": [body("rocky"), body("rocky")]},
    {"name": "Sector star 8", "star": "F", "feh": 0.1, "dist": 11.2, "bodies": [body("rocky"), body("ocean"), body("belt")]},
]
owned = [home]
colonies = []  # (system, body) pairs with population


def pop_cap(b):
    k = b["kind"]
    cap = POP["capacity"].get(k, 0)
    if b.get("capital"):
        cap += POP["capital_bonus"]
    if k in ("rocky", "super_earth"):
        cap += mods["pop_cap_rocky"]
    if k == "ocean" and "outpost_ocean" not in unlocked:
        cap = 0
    if k in ("super_earth", "ocean") and cap > 0:
        cap *= 1 + 0.25 * mods["habitability_step"]
    if cap > 0:
        cap += 4 * b.get("rings", 0)
    return cap


def pct(a):  # attribute points -> multiplier
    return 1 + B["attributes"]["per_point"] * a


# ---- state -----------------------------------------------------------------
pop = {id(home["bodies"][1]): B["start"]["population"]}
minerals = B["start"]["minerals"]
energy = B["start"]["energy"]
ac_bank = 0.0
stability = B["start"]["stability"]
ledger_acc = {"expansion": 0.0, "economic": 0.0, "social": 0.0, "military": 0.0}
fleet_tons = B["start"]["fleet_tons"]
known = len(T["known_at_start"])
done = set()
progress = 0.0
current = None
tier_base = {t["id"]: t["base_cost"] for t in T["tiers"]}
nodes = {n["id"]: n for n in T["nodes"]}
priority = B["sim_player"]["research_order"]
split = B["start"]["allocation"]
milestones = {}
snap = []
trace = []  # per-tick rows; written to $SIM_TRACE as CSV when set


def tier_open(tier):
    if tier == "reach":
        return True
    need = {"lattice": "reach", "concord": "lattice"}[tier]
    return sum(1 for d in done if nodes[d]["tier"] == need and not nodes[d].get("exclusive_group")) + \
        sum(1 for d in done if nodes[d]["tier"] == need and nodes[d].get("exclusive_group")) >= 6


def available(nid):
    n = nodes[nid]
    if nid in done or n.get("repeatable"):
        return False
    if not tier_open(n["tier"]):
        return False
    if n.get("requires") and any(r not in done for r in n["requires"]):
        return False
    g = n.get("exclusive_group")
    if g and any(nodes[d].get("exclusive_group") == g for d in done):
        return False
    return True


def cost(nid):
    return tier_base[nodes[nid]["tier"]] * (1 + T["cost_model"]["knowledge_tax"] * known)


def pick_research():
    for nid in priority:
        if nid in nodes and available(nid):
            return nid
    avail = [n for n in nodes if available(n)]
    return min(avail, key=cost) if avail else None


def admin_cost():
    n = len(owned)
    return EXP["admin_base"] * (n ** EXP["admin_exponent"]) if n > 1 else 0.0


for tick in range(1, TICKS + 1):
    # population growth (logistic) per habitable body
    g = POP["growth_per_tick"] * pct(ATTR["growth"]) * (1 + mods["pop_growth"] / 100)
    total_pop = 0.0
    for s in owned:
        for b in s["bodies"]:
            cap = pop_cap(b)
            if cap <= 0:
                continue
            k = id(b)
            p = pop.get(k, 0.0)
            if p <= 0:
                continue
            p += g * p * (1 - p / cap)
            pop[k] = min(p, cap)
            total_pop += pop[k]

    # stability
    target = STAB["base"] + STAB["per_cohesion"] * (ATTR["cohesion"] + mods["cohesion"]) + mods["stability"] \
        + 4 * built_count.get("civic_forum", 0) \
        + STAB["social_ac_factor"] * (split["social"] / 100) * (total_pop * AC["per_pop"]) ** 0.5 \
        - STAB["per_extra_system"] * (len(owned) - 1)
    target = max(0, min(100, target))
    stability += max(-1, min(1, target - stability))
    stab_mult = AC["stability_floor"] + (1 - AC["stability_floor"]) * 2 * stability / 100

    # action credits
    ac = total_pop * AC["per_pop"] * stab_mult * (1 + mods["ac_efficiency"] / 100)
    ac_net = max(0.0, ac - admin_cost())
    alloc = {k: ac_net * v / 100 for k, v in split.items()}

    # yields
    min_mult = pct(ATTR["industry"]) * (1 + mods["mineral_yield"] / 100)
    m_in = e_in = r_body = 0.0
    for s in owned:
        e_in += Y["star_energy"][s["star"]] * (1 + mods["star_energy_yield"] / 100) * pct(ATTR["industry"])
        rich = 1 + Y["metallicity_factor"] * s["feh"]
        for b in s["bodies"]:
            k = b["kind"]
            base = Y["minerals"].get(k, 0) + b["dev"]
            if k == "belt":
                base *= 1 + mods["belt_mineral_yield"] / 100
            if k == "ice":
                base += mods["ice_mineral_yield"]
            if k == "verdant":
                base *= 1 + mods["verdant_peak_yield"] / 100
            base += 2 * b.get("extract", 0)
            m_in += base * rich * min_mult
            if k == "gas_giant":
                e_in += Y["gas_giant_energy"] + mods["gas_giant_energy"]
                r_body += Y["gas_giant_research"]
    e_in += 3 * built_count.get("fusion_plant", 0)
    r_body += 2 * built_count.get("research_station", 0)
    e_out = Y["energy_upkeep_per_system"] * len(owned) + mods["energy_upkeep"] + sum(
        BLD["list"][k].get("upkeep_energy", 0) * v for k, v in built_count.items())
    m_out = MIL["upkeep_pct_per_tick"] / 100 * fleet_tons + mods["mineral_upkeep"] + built_count.get("defense_battery", 0)
    short = 1 - BLD["energy_shortage_output_penalty_pct"] / 100 if energy <= 0 else 1.0
    m_in *= short

    # research
    rp = (alloc["research"] * RES["rp_per_ac"] * pct(ATTR["curiosity"]) * (1 + mods["research_output"] / 100)
          * (1 + mods["research_efficiency"] / 100) + r_body) * short
    if current is None:
        current = pick_research()
        progress = cost(current) * B["start"].get("research_head_start_pct", 0) / 100 if not done else 0.0
    if current:
        progress += rp
        if progress >= cost(current):
            progress -= cost(current)
            done.add(current)
            known += 1
            apply(nodes[current].get("effects"))
            apply(nodes[current].get("drawbacks"))
            for u in nodes[current].get("unlocks", []) or []:
                unlocked.add(u)
            milestones.setdefault("first_tech", tick)
            reach_n = sum(1 for d in done if nodes[d]["tier"] == "reach")
            if reach_n >= 6:
                milestones.setdefault("lattice_open", tick)
            if tier_open("concord"):
                milestones.setdefault("concord_open", tick)
            if all(nid in done or nodes[nid].get("repeatable") or
                   (nodes[nid].get("exclusive_group") and any(nodes[d].get("exclusive_group") == nodes[nid]["exclusive_group"] for d in done))
                   for nid in nodes):
                milestones.setdefault("tree_complete", tick)
            current = None

    # buildings: one per tick, from minerals + economic AC
    ledger_acc["economic"] += alloc["economic"]
    storage = Y["mineral_storage_per_system"] * len(owned) + 2000 * built_count.get("warehouse", 0)
    used = sum(b.get("extract", 0) + b.get("rings", 0) + b.get("generic", 0) for s_ in owned for b in s_["bodies"])
    slots = sum(len(s_["bodies"]) for s_ in owned)
    hab_full = [b for s_ in owned for b in s_["bodies"] if pop_cap(b) > 0 and pop.get(id(b), 0) > 0.85 * pop_cap(b)
                and b["kind"] in ("verdant", "ocean", "super_earth") and not b.get("rings")]
    ext_free = [b for s_ in owned for b in s_["bodies"] if b["kind"] in ("rocky", "super_earth", "belt", "ice")
                and not b.get("extract") and not b.get("rings") and not b.get("generic")]
    wants = []
    if stability < 45: wants.append("civic_forum")
    if e_in - e_out < 1: wants.append("fusion_plant")
    if hab_full: wants.append("habitat_ring")
    if minerals > 0.8 * storage: wants.append("warehouse")
    wants += ["research_station", "extraction_complex", "defense_battery"]
    if used < slots:
        for w in wants:
            spec = BLD["list"][w]
            f = 1 + BLD["repeat_cost_growth"] * built_count.get(w, 0)
            mneed, aneed = spec["minerals"] * f, spec["ac"] * f
            if w == "habitat_ring" and not hab_full: continue
            if w == "extraction_complex" and not ext_free: continue
            if minerals - mneed >= BLD["reserve_minerals_for_expansion"] and ledger_acc["economic"] >= aneed:
                minerals -= mneed
                ledger_acc["economic"] -= aneed
                built_count[w] = built_count.get(w, 0) + 1
                if w == "habitat_ring": hab_full[0]["rings"] = 1
                elif w == "extraction_complex": ext_free[0]["extract"] = 1
                else:
                    free = next(b for s_ in owned for b in s_["bodies"] if not (b.get("extract") or b.get("rings") or b.get("generic")))
                    free["generic"] = 1
                break

    # economic development: improve the best mineral body
    bodies = [b for s in owned for b in s["bodies"] if Y["minerals"].get(b["kind"], 0) > 0]
    if bodies:
        b = min(bodies, key=lambda x: x["dev"])
        need = ECO["dev_cost_base"] * (b["dev"] + 1)
        if b["dev"] < ECO["max_dev"] and ledger_acc["economic"] >= need:
            ledger_acc["economic"] -= need
            b["dev"] += 1

    # military: build hulls from minerals
    ledger_acc["military"] += alloc["military"]
    build = min(ledger_acc["military"] * MIL["tons_per_ac"], max(0.0, minerals - EXP["outpost_minerals"]) * 0.5)
    if build > 0:
        fleet_tons += build
        minerals -= build * MIL["minerals_per_ton"]
        ledger_acc["military"] -= build / MIL["tons_per_ac"]
    fleet_tons *= 1 - MIL["age_wear_pct_per_tick"] / 100

    minerals = min(minerals + m_in - m_out, storage)
    energy = min(Y["energy_storage"], energy + e_in - e_out)

    # expansion: outpost the next candidate when affordable
    ledger_acc["expansion"] += alloc["expansion"]
    if candidates:
        nxt = min(candidates, key=lambda c: c["dist"])
        hab = any(pop_cap(b) > 0 for b in nxt["bodies"])
        ac_need = (EXP["colony_ac"] if hab else EXP["outpost_ac"]) * (1 + (mods["expansion_cost"] + mods["colonize_cost"]) / 100)
        m_need = EXP["colony_minerals"] if hab else EXP["outpost_minerals"]
        if ledger_acc["expansion"] >= ac_need and minerals >= m_need:
            ledger_acc["expansion"] -= ac_need
            minerals -= m_need
            candidates.remove(nxt)
            owned.append(nxt)
            for b in nxt["bodies"]:
                if pop_cap(b) > 0:
                    pop[id(b)] = POP["colony_start"]
            milestones.setdefault("first_new_system", tick)
            if hab:
                milestones.setdefault("first_colony", tick)

    # late unlocks can make existing bodies habitable (ocean worlds)
    for s in owned:
        for b in s["bodies"]:
            if pop_cap(b) > 0 and pop.get(id(b), 0) <= 0:
                pop[id(b)] = POP["colony_start"]

    ac_bank = min(ac_bank + 0, ac * AC["bank_ticks"])
    trace.append((tick, total_pop, ac, rp, m_in, minerals, len(owned), stability, len(done), fleet_tons, sum(built_count.values())))
    if tick in (1, 24, 24 * 7, 24 * 14, 24 * 30, 24 * 60, 24 * 90):
        snap.append((tick, total_pop, ac, rp, m_in, minerals, e_in - e_out, len(owned), stability, len(done), fleet_tons, sum(built_count.values())))

days = lambda t: f"{t} (day {t / 24:.1f})" if t else "not reached"
print("MILESTONES")
for k in ["first_tech", "first_new_system", "first_colony", "lattice_open", "concord_open", "tree_complete"]:
    print(f"  {k:18s} tick {days(milestones.get(k))}")
print("\nSNAPSHOTS  tick  pop    AC/t   RP/t   M/t    M stock  E net  sys stab techs fleet_t bldg")
for s in snap:
    print(f"  day {s[0] / 24:5.1f} {s[0]:5d} {s[1]:6.1f} {s[2]:6.1f} {s[3]:6.1f} {s[4]:6.1f} {s[5]:8.0f} {s[6]:5.1f} {s[7]:4d} {s[8]:4.0f} {s[9]:5d} {s[10]:7.0f} {s[11]:4d}")
print("\nBUILDINGS", built_count)

import os, csv
if os.environ.get("SIM_TRACE"):
    with open(os.environ["SIM_TRACE"], "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["tick", "pop", "ac", "rp", "m_in", "minerals", "systems", "stability", "techs", "fleet_tons", "buildings"])
        w.writerows(trace)
