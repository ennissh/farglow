"""Procedural galaxy cell: generated from hash(galaxy_seed, cell_id), never stored.

A 10 pc cell near the Sun holds about 100 systems (config/galaxy.poc.yaml). The PoC map is
the cell's face-on projection: positions are integer milli-light-years in a 32.6 × 32.6 ly
square, so the distances a player sees are the distances the engine uses.

Only what civilizations discover or change is stored in the engine state (fog of war).
Everything here uses integer arithmetic and the seeded RNG, so it is identical on every
machine and architecture.
"""
from __future__ import annotations

from functools import lru_cache
from math import isqrt

from .state import rng

CELL_SIZE_MLY = 32_600          # 10 pc = 32.6 ly
DEFAULT_CELL = "41-07-02"       # placeholder address for the host's first cell (Phase 3 makes it real)

# (class, weight, energy class key, body count range) - roughly the real main-sequence mix
STAR_TABLE = (("M", 70, (1, 4)), ("K", 15, (2, 6)), ("G", 9, (2, 7)), ("F", 5, (2, 7)), ("A", 1, (1, 5)))
BODY_TABLE = (("rocky", 30), ("gas_giant", 15), ("ice", 15), ("belt", 15), ("super_earth", 8),
              ("ocean", 6), ("verdant", 4))
WARM = ("K", "G", "F")           # only these stars get ocean and verdant worlds
SUBCLASS = "0123456789"
HOME_BODIES = ("rocky", "verdant", "gas_giant", "belt", "ice")


def _pick(r, table, total):
    x = r.randrange(total)
    for row in table:
        x -= row[1]
        if x < 0:
            return row
    return table[-1]


@lru_cache(maxsize=8)
def generate(seed: int, cell: str = DEFAULT_CELL) -> tuple[dict, ...]:
    r = rng(seed, "cell", cell)
    count = 85 + r.randrange(31)                    # 85-115 systems: a "medium" cell
    star_total = sum(w for _, w, _ in STAR_TABLE)
    body_total = sum(w for _, w in BODY_TABLE)
    systems = []
    taken = set()
    for i in range(count):
        # keep stars at least ~0.6 ly apart so the map stays readable
        for _ in range(20):
            x, y = 800 + r.randrange(CELL_SIZE_MLY - 1600), 800 + r.randrange(CELL_SIZE_MLY - 1600)
            key = (x // 600, y // 600)
            if key not in taken:
                break
        taken.add(key)
        cls, _, (lo, hi) = _pick(r, STAR_TABLE, star_total)
        n_bodies = lo + r.randrange(hi - lo + 1)
        bodies = []
        for _ in range(n_bodies):
            kind = _pick(r, BODY_TABLE, body_total)[0]
            if kind in ("ocean", "verdant") and cls not in WARM:
                kind = "rocky"
            bodies.append(kind)
        bodies.sort(key=BODY_ORDER.get)
        systems.append({
            "id": f"s{i:03d}",
            "designation": f"FG {cell}·{i + 1:03d}",
            "x": x, "y": y,
            "star": cls, "subclass": SUBCLASS[r.randrange(10)],
            "multiple": r.randrange(3) == 0,          # ~a third are binary or triple
            "feh": r.randrange(-40, 41),              # [Fe/H] in centi-dex
            "bodies": tuple(bodies),
        })
    return tuple(systems)


BODY_ORDER = {"rocky": 0, "super_earth": 1, "verdant": 2, "ocean": 3, "gas_giant": 4, "ice": 5, "belt": 6}


def by_id(seed: int, cell: str = DEFAULT_CELL) -> dict[str, dict]:
    return {s["id"]: s for s in generate(seed, cell)}


def distance(a: dict, b: dict) -> int:
    """Distance in milli-ly between two systems (integer square root: deterministic)."""
    return isqrt((a["x"] - b["x"]) ** 2 + (a["y"] - b["y"]) ** 2)


def system_view(seed: int, state_systems: dict, sid: str, cell: str = DEFAULT_CELL) -> dict:
    """The generated system with the engine state's overrides (home systems) applied."""
    base = dict(by_id(seed, cell)[sid])
    ov = (state_systems.get(sid) or {}).get("override")
    if ov:
        base.update(ov)
        base["bodies"] = tuple(ov.get("bodies", base["bodies"]))
    return base


def pick_home(seed: int, state_systems: dict, homes: list[str], cell: str = DEFAULT_CELL) -> str:
    """Deterministic home placement: the first civ starts nearest the centre; each later civ
    takes the free system that maximises its distance to the nearest existing home."""
    systems = generate(seed, cell)
    free = [s for s in systems if not (state_systems.get(s["id"]) or {}).get("owner")
            and s["id"] not in homes]
    if not free:
        raise RuntimeError("the cell is full")
    centre = {"x": CELL_SIZE_MLY // 2, "y": CELL_SIZE_MLY // 2}
    if not homes:
        return min(free, key=lambda s: (distance(s, centre), s["id"]))["id"]
    home_sys = [by_id(seed, cell)[h] for h in homes]

    def score(s):
        nearest = min(distance(s, h) for h in home_sys)
        edge = min(s["x"], s["y"], CELL_SIZE_MLY - s["x"], CELL_SIZE_MLY - s["y"])
        return (min(nearest, 3 * edge), s["id"])
    return max(free, key=score)["id"]


def home_override(seed: int, sid: str) -> dict:
    """A home system is a developed K or G star with the standard five bodies."""
    s = by_id(seed)[sid]
    star = s["star"] if s["star"] in ("K", "G") else "K"
    return {"star": star, "bodies": list(HOME_BODIES), "multiple": False, "feh": max(s["feh"], 0)}
