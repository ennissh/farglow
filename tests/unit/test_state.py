import pytest

from farglow.engine import state as st


def test_same_seed_same_hashes():
    assert st.replay(42, {}, 25) == st.replay(42, {}, 25)


def test_different_seed_different_hashes():
    assert st.replay(42, {}, 3) != st.replay(43, {}, 3)


def test_advance_does_not_mutate_input():
    g = st.genesis(7)
    before = st.state_hash(g)
    st.advance(g, [])
    assert st.state_hash(g) == before


def test_hash_chain_links_previous_state():
    g = st.genesis(7)
    s1 = st.advance(g, [])
    assert s1["prev_hash"] == st.state_hash(g)
    assert s1["tick"] == 1


def test_floats_are_refused():
    with pytest.raises(st.DeterminismError):
        st.state_hash({"x": 0.5})


def test_canonical_is_key_order_independent():
    assert st.canonical({"b": 1, "a": 2}) == st.canonical({"a": 2, "b": 1})


def test_unknown_orders_are_rejected_not_applied():
    s1 = st.advance(st.genesis(1), [{"kind": "build", "what": "death-ray"}])
    assert s1["log"][0]["rejected"][0]["reason"] == "unknown order kind"
    # orders change the hash (they are part of the history)
    assert st.state_hash(s1) != st.state_hash(st.advance(st.genesis(1), []))


def test_rng_is_derived_and_stable():
    a = [st.rng(42, "cell", "41-07-02").randrange(1_000_000) for _ in range(3)]
    b = [st.rng(42, "cell", "41-07-02").randrange(1_000_000) for _ in range(3)]
    assert a == b
    assert st.rng(42, "cell", "41-07-03").random() != st.rng(42, "cell", "41-07-02").random()
