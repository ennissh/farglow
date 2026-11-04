"""Golden hashes: the engine's output for a fixed seed must never change by accident.

If you change the engine ON PURPOSE (new state fields, a new rule), update these values in
the same commit and say why in CHANGELOG.md: existing servers' replays would differ.
"""
from farglow.engine import state as st

GOLDEN_SEED = 42
GOLDEN = {
    0: "69c46fd9e622c3488021c37d9059317266bed59ce3f21e883034c3726b9bcfd3",
    10: "af7c3e257d563c237f9856f9234e5f843f6667090eaba1db7861393c65d4cf37",
}


def test_genesis_hash_is_stable():
    assert st.state_hash(st.genesis(GOLDEN_SEED)) == GOLDEN[0]


def test_ten_empty_ticks_hash_is_stable():
    assert st.replay(GOLDEN_SEED, {}, 10)[-1] == GOLDEN[10]
