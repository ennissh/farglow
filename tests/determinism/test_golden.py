"""Golden hashes: the engine's output for a fixed seed must never change by accident.

If you change the engine ON PURPOSE, update these values in the same commit and say why in
CHANGELOG.md: existing servers' replays would differ.

GOLDEN_V1 must NEVER change: galaxies created by 0.0.x are schema 1, and their recorded
ticks must keep replaying to the same hashes (they upgrade through an engine.upgrade order).
"""
from farglow.engine import rules as R
from farglow.engine import state as st

GOLDEN_SEED = 42
GOLDEN_V1 = {
    0: "69c46fd9e622c3488021c37d9059317266bed59ce3f21e883034c3726b9bcfd3",
    10: "af7c3e257d563c237f9856f9234e5f843f6667090eaba1db7861393c65d4cf37",
}
FOUND = {"kind": "found", "user": 1, "name": "Golden Reach", "set": 3,
         "attributes": {"curiosity": 2, "industry": 0, "growth": -1, "cohesion": 1, "martial": -2, "openness": 0}}
GOLDEN_V2 = {
    "rules": "6c0b41adc0d90588",
    "found_then_48": "889ac8c52ac8b75be9c3595e79bd9641867e6d613e9983b193b10b7c18a12a3d",
}


def test_v1_genesis_hash_is_stable():
    assert st.state_hash(st.genesis_v1(GOLDEN_SEED)) == GOLDEN_V1[0]


def test_v1_ten_empty_ticks_hash_is_stable():
    assert st.replay(GOLDEN_SEED, {}, 10, start=st.genesis_v1(GOLDEN_SEED))[-1] == GOLDEN_V1[10]


def test_v2_first_light_hash_is_stable():
    rules = R.load()
    if rules.hash != GOLDEN_V2["rules"]:
        import pytest
        pytest.skip("config/*.poc.yaml changed: re-run tests/determinism/regen_golden.py and commit the new values")
    hashes = st.replay(GOLDEN_SEED, {1: [FOUND]}, 49, rules=rules)
    assert hashes[-1] == GOLDEN_V2["found_then_48"]
