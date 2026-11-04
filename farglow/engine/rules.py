"""Game rules: config/*.poc.yaml turned into integers, once, at load time.

The engine never sees a float. Every number from the YAML is converted here with
Decimal (exact for the decimal text in the file) into fixed-point integers:

    milli(x)  = x × 1000      amounts: population, minerals, energy, AC, RP, stability, tons
    ly        = x × 1000      distances in milli-light-years
    pct       = x × 1000      percentages (25 % -> 25_000), applied with pct_mul()

Rules are data: the same code with different YAML gives a different game, and
`rules_hash` (stored in the engine state) says which rules a state was computed with.
"""
from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml

FP = 1000


def milli(x) -> int:
    return int((Decimal(str(x)) * FP).to_integral_value())


def config_dir() -> Path:
    for candidate in (Path(__file__).resolve().parents[2] / "config", Path("/app/config")):
        if (candidate / "balance.poc.yaml").is_file():
            return candidate
    raise FileNotFoundError("config/balance.poc.yaml not found")


BODY_KINDS = ("verdant", "ocean", "super_earth", "rocky", "gas_giant", "ice", "belt")
HABITABLE = ("verdant", "ocean", "super_earth")
ALLOCATION_KEYS = ("expansion", "research", "social", "economic", "military")

# Tech effect keys the PoC engine applies (others are recorded but have no effect yet).
MOD_KEYS = (
    "research_output", "research_efficiency", "mineral_yield", "belt_mineral_yield", "ice_mineral_yield",
    "star_energy_yield", "energy_yield", "gas_giant_energy", "pop_growth", "pop_cap_rocky", "habitability_step",
    "stability", "cohesion", "ac_efficiency", "expansion_cost", "colonize_cost", "energy_upkeep",
    "mineral_upkeep", "verdant_peak_yield", "survey_range_ly", "ftl_speed_ly_per_tick", "comms_speed_ly_per_tick",
    "admin_cost_exponent", "charter_slots", "fleet_upkeep",
)


class Rules:
    def __init__(self, balance: dict, tree: dict, objectives: dict, source_hash: str | None = None):
        b, t = balance, tree
        self.raw = {"balance": balance, "tech_tree": tree, "objectives": objectives}
        a = b["attributes"]
        self.attributes = tuple(a["list"])
        self.attr_min, self.attr_max = a["range"]
        self.attr_sum = a["sum_must_equal"]
        self.per_point = milli(a["per_point"])                      # 50 = 5 %
        s = b["start"]
        self.start = {
            "attributes": dict(s["attributes"]),
            "population": milli(s["population"]),
            "minerals": milli(s["minerals"]),
            "energy": milli(s["energy"]),
            "stability": milli(s["stability"]),
            "fleet_tons": milli(s["fleet_tons"]),
            "head_start_pct": int(s["research_head_start_pct"]),
            "allocation": {k: int(v) for k, v in s["allocation"].items()},
        }
        p = b["population"]
        self.pop_capacity = {k: milli(v) for k, v in p["capacity"].items()}
        self.capital_bonus = milli(p["capital_bonus"])
        self.growth_ppm = int(Decimal(str(p["growth_per_tick"])) * 1_000_000)
        self.colony_start = milli(p["colony_start"])
        ac = b["action_credits"]
        self.ac_per_pop = milli(ac["per_pop"])
        self.stab_floor = milli(ac["stability_floor"])               # 750
        self.bank_ticks = int(ac["bank_ticks"])
        st = b["stability"]
        self.stab_base = milli(st["base"])
        self.stab_per_cohesion = milli(st["per_cohesion"])
        self.social_factor = milli(st["social_ac_factor"])
        self.stab_per_extra_system = milli(st["per_extra_system"])
        self.stab_drift = milli(st["drift_per_tick"])
        y = b["yields"]
        self.star_energy = {k: milli(v) for k, v in y["star_energy"].items()}
        self.mineral_yield = {k: milli(v) for k, v in y["minerals"].items()}
        self.gas_giant_energy = milli(y["gas_giant_energy"])
        self.gas_giant_research = milli(y["gas_giant_research"])
        self.metallicity_factor = milli(y["metallicity_factor"])
        self.energy_upkeep_per_system = milli(y["energy_upkeep_per_system"])
        self.energy_storage = milli(y["energy_storage"])
        self.mineral_storage_per_system = milli(y["mineral_storage_per_system"])
        e = b["economy"]
        self.dev_cost_base = milli(e["dev_cost_base"])
        self.max_dev = int(e["max_dev"])
        bl = b["buildings"]
        self.repeat_cost_growth = milli(bl["repeat_cost_growth"])
        self.build_ticks = int(bl.get("build_ticks", 12))
        self.shortage_penalty_pct = int(bl["energy_shortage_output_penalty_pct"])
        self.buildings = {}
        for bid, spec in bl["list"].items():
            on = spec["on"] if "on" in spec else spec[True]   # YAML 1.1 reads a bare `on:` key as True
            self.buildings[bid] = {
                "minerals": milli(spec["minerals"]), "ac": milli(spec["ac"]),
                "upkeep_energy": milli(spec.get("upkeep_energy", 0)),
                "upkeep_minerals": milli(spec.get("upkeep_minerals", 0)),
                "on": "any" if on == "any" else ("populated" if on == "populated" else tuple(on)),
                "requires": spec.get("requires"), "effect": spec["effect"],
            }
        self.rp_per_ac = milli(b["research"]["rp_per_ac"])
        x = b["expansion"]
        self.outpost_ac, self.outpost_minerals = milli(x["outpost_ac"]), milli(x["outpost_minerals"])
        self.colony_ac, self.colony_minerals = milli(x["colony_ac"]), milli(x["colony_minerals"])
        self.survey_ac = milli(x.get("survey_ac", 150))
        self.survey_minerals = milli(x.get("survey_minerals", 0))
        self.max_reach = milli(x.get("max_reach_ly", 12))
        self.admin_base = milli(x["admin_base"])
        self.admin_exponent = milli(x["admin_exponent"])            # 1300
        m = b["military"]
        self.tons_per_ac = milli(m["tons_per_ac"])
        self.minerals_per_ton = milli(m["minerals_per_ton"])
        self.fleet_upkeep_pct = milli(m["upkeep_pct_per_tick"])      # 500 = 0.5 %
        self.age_wear_pct = milli(m["age_wear_pct_per_tick"])        # 20 = 0.02 %
        self.research_priority = tuple(b.get("sim_player", {}).get("research_order", ()))

        # ---- tech tree
        cm = t["cost_model"]
        self.knowledge_tax = milli(cm["knowledge_tax"])              # 40 = 4 %
        self.debug_cost_multiplier = milli(cm.get("debug_cost_multiplier", 1))
        self.repeatable_growth = milli(cm.get("repeatable_growth", 1.25))
        self.tiers = {tier["id"]: {"order": tier["order"], "name": tier["name"], "base_cost": milli(tier["base_cost"]),
                                   "unlock": tier.get("unlock")} for tier in t["tiers"]}
        self.fields = tuple(t["fields"])
        self.known_at_start = tuple(n["id"] for n in t["known_at_start"])
        self.start_effects = [_effect(e) for n in t["known_at_start"] for e in (n.get("effects") or [])]
        self.start_unlocks = [u for n in t["known_at_start"] for u in (n.get("unlocks") or [])]
        self.start_names = {n["id"]: n["name"] for n in t["known_at_start"]}
        self.techs = {}
        for n in t["nodes"]:
            if n["id"] in self.techs:      # the file repeats some ids in a summary block; first wins
                continue
            self.techs[n["id"]] = {
                "id": n["id"], "name": n["name"], "tier": n["tier"], "field": n.get("field", ""),
                "description": n.get("description", ""), "requires": tuple(n.get("requires") or ()),
                "group": n.get("exclusive_group"), "repeatable": bool(n.get("repeatable")),
                "effects": [_effect(e) for e in (n.get("effects") or [])],
                "drawbacks": [_effect(e) for e in (n.get("drawbacks") or [])],
                "unlocks": tuple(n.get("unlocks") or ()),
            }
        # ---- objectives: tutorial charters
        tut = objectives["charters"]["tutorial"]
        self.tutorial_charters = tuple(c for c in tut["list"] if c != "first_dispatch_reply")
        self.tutorial_reward = milli(tut.get("reward_minerals", 400))

        self.hash = hashlib.sha256(json.dumps(self.raw, sort_keys=True, default=str).encode()).hexdigest()[:16] \
            if source_hash is None else source_hash

    # ---- helpers -------------------------------------------------------------------
    def attr_mul(self, value: int, points: int) -> int:
        """value × (1 + 5 % × points)."""
        return value * (FP + self.per_point * points) // FP

    def tech_cost(self, tech_id: str, known: int, debug: bool = False) -> int:
        base = self.tiers[self.techs[tech_id]["tier"]]["base_cost"]
        cost = base * (FP + self.knowledge_tax * known) // FP
        if debug:
            cost = cost * self.debug_cost_multiplier // FP
        return max(cost, FP)


def _effect(e: dict) -> dict:
    out = {"key": e["key"], "op": e.get("op", "add"), "value": milli(e.get("value", 0))}
    if e.get("per") or e.get("while"):
        out["conditional"] = True
    return out


def pct_mul(value: int, pct_milli: int) -> int:
    """value × (1 + pct/100), pct in milli-percent (25 % = 25_000)."""
    return value * (100_000 + pct_milli) // 100_000


@lru_cache(maxsize=4)
def _load(directory: str) -> Rules:
    d = Path(directory)
    names = ("balance.poc.yaml", "tech_tree.poc.yaml", "objectives.poc.yaml")
    texts = [(d / n).read_bytes() for n in names]
    source_hash = hashlib.sha256(b"\0".join(texts)).hexdigest()[:16]   # which rules a state was computed with
    return Rules(*(yaml.safe_load(t) for t in texts), source_hash=source_hash)


def load(directory: Path | None = None) -> Rules:
    return _load(str(directory or config_dir()))
