"""Engine state and the deterministic step function.

Determinism contract (README "Design rules"):
  * advance(state, orders) is a pure function: same state + same orders -> same result,
    on any machine and either architecture (amd64, arm64).
  * State is plain JSON: dicts with string keys, lists, str, int, bool, None. Floats are
    refused: rounding differs across platforms and libraries, so the engine uses integers
    (fixed-point where fractions are needed).
  * state_hash = SHA-256 of the canonical JSON. Each state records the previous hash, so
    the tick hashes form a chain; a replay from genesis must reproduce every link.
  * Randomness only through rng(seed, *keys), which is derived from the seed, never global.
"""
from __future__ import annotations

import hashlib
import json
import random
from typing import Any

SCHEMA = 1
GENESIS_PREV = "0" * 64


class DeterminismError(TypeError):
    pass


def _check(value: Any, path: str = "$") -> None:
    if isinstance(value, bool) or value is None or isinstance(value, (int, str)):
        return
    if isinstance(value, float):
        raise DeterminismError(f"float at {path}: engine state must use integers")
    if isinstance(value, list):
        for i, item in enumerate(value):
            _check(item, f"{path}[{i}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise DeterminismError(f"non-string key at {path}: {key!r}")
            _check(item, f"{path}.{key}")
        return
    raise DeterminismError(f"unsupported type {type(value).__name__} at {path}")


def canonical(value: Any) -> bytes:
    _check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def state_hash(state: dict) -> str:
    return hashlib.sha256(canonical(state)).hexdigest()


def orders_hash(orders: list) -> str:
    return hashlib.sha256(canonical(orders)).hexdigest()


def rng(seed: int, *keys: Any) -> random.Random:
    """A private RNG for one decision, e.g. rng(seed, 'cell', '41-07-02').

    random.Random with an int seed is stable across CPython versions and platforms for
    random(), randrange() and getrandbits().
    """
    digest = hashlib.sha256(canonical([seed, *[str(k) for k in keys]])).digest()
    return random.Random(int.from_bytes(digest[:16], "big"))


def genesis(seed: int) -> dict:
    return {
        "schema": SCHEMA,
        "galaxy_seed": int(seed),
        "tick": 0,
        "prev_hash": GENESIS_PREV,
        "civilizations": {},
        "systems": {},
        "log": [],
    }


KNOWN_ORDERS: frozenset[str] = frozenset()  # Phase 1 adds order kinds; Phase 0 has none.


def advance(state: dict, orders: list[dict]) -> dict:
    """Return the state one tick later. Never mutates its input."""
    _check(state)
    _check(orders)
    prev = state_hash(state)
    nxt = json.loads(canonical(state))  # deep copy through the canonical form
    nxt["tick"] = state["tick"] + 1
    nxt["prev_hash"] = prev
    rejected = []
    for i, order in enumerate(orders):
        kind = order.get("kind") if isinstance(order, dict) else None
        if kind not in KNOWN_ORDERS:
            rejected.append({"index": i, "kind": kind, "reason": "unknown order kind"})
    # Keep only this tick's engine log: history lives in the ticks table, not in the state.
    nxt["log"] = [{"tick": nxt["tick"], "rejected": rejected}] if rejected else []
    return nxt


def replay(seed: int, orders_by_tick: dict[int, list[dict]], ticks: int) -> list[str]:
    """Hashes of states 1..ticks from genesis. Used by tests and `engine verify`."""
    state = genesis(seed)
    hashes = []
    for t in range(1, ticks + 1):
        state = advance(state, orders_by_tick.get(t, []))
        hashes.append(state_hash(state))
    return hashes
