"""Engine schema 2 (First Light): rules, economy parity with sim.py, orders, missions, fog."""
import re
import subprocess
import sys
from pathlib import Path

import pytest

from farglow.engine import game, galaxy
from farglow.engine import rules as R
from farglow.engine import state as st
from farglow.play import advisor, view

ROOT = Path(__file__).resolve().parents[2]
ATTRS = {"curiosity": 2, "industry": 0, "growth": -1, "cohesion": 1, "martial": -2, "openness": 0}


@pytest.fixture(scope="module")
def rules():
    return R.load()


def found(user=1, name="Test Reach", **kw):
    return {"kind": "found", "user": user, "name": name, "set": 3, "attributes": dict(ATTRS), **kw}


def run(state, rules, ticks, orders=None):
    for i in range(ticks):
        state = st.advance(state, (orders or {}).get(i, []), rules)
    return state


def new_game(rules, **kw):
    s = st.advance(st.genesis(42, rules), [found(**kw)], rules)
    return s, s["civs"]["c1"]


def test_rules_are_integers_only(rules):
    assert rules.start["population"] == 12_000 and rules.growth_ppm == 4000 and rules.per_point == 50
    assert rules.buildings["fusion_plant"]["on"] == "any"            # the YAML `on:` key quirk
    assert len(rules.techs) == 32 and "first_dispatch_reply" not in rules.tutorial_charters


def test_galaxy_is_deterministic_and_medium_density():
    a, b = galaxy.generate(7), galaxy.generate(7)
    assert a == b and 85 <= len(a) <= 115
    assert galaxy.generate(8) != a
    assert all(0 < s["x"] < galaxy.CELL_SIZE_MLY for s in a)


def test_economy_matches_sim_first_tech(rules):
    """Balance is measured: with no player orders the engine's first tech lands on the same tick as sim.py."""
    out = subprocess.run([sys.executable, str(ROOT / "tools/sim.py"), str(ROOT / "config/balance.poc.yaml"),
                          str(ROOT / "config/tech_tree.poc.yaml"), "200"], capture_output=True, text=True, check=True).stdout
    sim_tick = int(re.search(r"first_tech\s+tick (\d+)", out).group(1))
    s, civ = new_game(rules)
    founded = s["tick"]
    first = None
    for _ in range(60):
        s = st.advance(s, [], rules)
        if any(e["kind"] == "tech_done" for e in s["log"]):
            first = s["tick"] - founded + 1
            break
    assert first == sim_tick


def test_found_validation(rules):
    s = st.genesis(1, rules)
    assert game.validate(s, rules, found(attributes={**ATTRS, "martial": 0})) == "attributes must sum to 0"
    assert "run" in game.validate(s, rules, found(attributes={**ATTRS, "curiosity": 4, "martial": -4}))
    assert game.validate(s, rules, found(name="x")).startswith("a civilization name")
    assert game.validate(s, rules, found(set=40)) == "pick one of the 32 civilization sets"
    assert game.validate(s, rules, found()) is None


def test_one_civ_per_user_and_names_unique(rules):
    s, _ = new_game(rules)
    assert game.validate(s, rules, found()) == "you already lead a civilization"
    assert game.validate(s, rules, found(user=2)) == "that name is taken on this server"


def test_second_civ_lands_far_away(rules):
    s, c1 = new_game(rules)
    s = st.advance(s, [found(user=2, name="Second Light")], rules)
    c2 = s["civs"]["c2"]
    systems = galaxy.by_id(42)
    assert c1["home"] != c2["home"]
    assert galaxy.distance(systems[c1["home"]], systems[c2["home"]]) > 10_000
    assert s["systems"][c2["home"]]["name"] != s["systems"][c1["home"]]["name"]


def test_survey_mission_travels_then_reveals_and_pays_the_charter(rules):
    s, civ = new_game(rules)
    s = run(s, rules, 8)                                         # bank 150 expansion AC
    civ = s["civs"]["c1"]
    target = next(sid for sid in galaxy.by_id(42) if sid not in civ["surveyed"]
                  and game.nearest_owned(s, "c1", sid)[0] <= rules.max_reach)
    order = {"kind": "survey", "system": target, "user": 1}
    assert game.validate(s, rules, order) is None
    minerals = s["civs"]["c1"]["minerals"]
    s = st.advance(s, [order], rules)
    m = s["civs"]["c1"]["missions"][0]
    assert m["arrive"] > s["tick"]
    while s["tick"] < m["arrive"]:
        s = st.advance(s, [], rules)
    civ = s["civs"]["c1"]
    assert target in civ["surveyed"] and civ["charters"]["first_survey"]["status"] == "completed"
    assert any(e["kind"] == "charter_done" for e in s["log"])
    assert s["systems"][target]["discovered_by"] == "c1"
    assert civ["minerals"] > minerals                           # the 400-mineral reward landed


def test_build_takes_twelve_ticks(rules):
    s, civ = new_game(rules)
    home = s["civs"]["c1"]["home"]
    order = {"kind": "build", "system": home, "body": 3, "building": "extraction_complex", "user": 1}  # the belt
    for _ in range(120):                                         # minerals and economic AC for a building
        if game.validate(s, rules, order) is None:
            break
        s = st.advance(s, [], rules)
    assert game.validate(s, rules, order) is None
    s = st.advance(s, [order], rules)
    body = s["systems"][home]["bodies"]["3"]
    assert body["building"] == "extraction_complex" and not body["ready"]
    assert game.validate(s, rules, order) == "that body already has a building (one per body)"
    s = run(s, rules, rules.build_ticks)
    assert s["systems"][home]["bodies"]["3"]["ready"]
    assert s["civs"]["c1"]["charters"]["first_building"]["status"] == "completed"


def test_claim_needs_survey_and_funds(rules):
    s, civ = new_game(rules)
    far = next(sid for sid in galaxy.by_id(42) if sid not in civ["surveyed"])
    assert game.validate(s, rules, {"kind": "claim", "system": far, "user": 1}) == "survey it first"
    near = next(sid for sid in civ["surveyed"] if sid != civ["home"])
    err = game.validate(s, rules, {"kind": "claim", "system": near, "user": 1})
    assert err.startswith("needs") and "expansion AC" in err


def test_outpost_arrives_and_costs_stability(rules):
    s, civ = new_game(rules)
    near = sorted((game.nearest_owned(s, "c1", sid)[0], sid) for sid in civ["surveyed"] if sid != civ["home"])[0][1]
    order = {"kind": "claim", "system": near, "user": 1}
    for _ in range(80):
        if game.validate(s, rules, order) is None:
            break
        s = st.advance(s, [], rules)
    assert game.validate(s, rules, order) is None
    s = st.advance(s, [order], rules)
    for _ in range(60):
        s = st.advance(s, [], rules)
        if s["systems"].get(near, {}).get("owner") == "c1":
            break
    assert s["systems"][near]["owner"] == "c1"
    civ = s["civs"]["c1"]
    assert civ["charters"]["first_outpost"]["status"] == "completed"
    assert len(game.owned_systems(s, "c1")) == 2


def test_doctrine_locks_the_other_two(rules):
    s, civ = new_game(rules)
    civ = s["civs"]["c1"]
    civ["research"]["done"].append("relay_bloom")                 # as if researched
    err = game.validate(s, rules, {"kind": "research_queue", "queue": ["fold_lensing"], "user": 1})
    assert "locked by your doctrine" in err


def test_allocation_must_sum_to_100(rules):
    s, _ = new_game(rules)
    bad = {"kind": "allocation", "user": 1, "allocation": {"expansion": 30, "research": 30, "social": 10,
                                                          "economic": 20, "military": 15}}
    assert game.validate(s, rules, bad) == "the shares must add up to 100 %"
    good = dict(bad, allocation={**bad["allocation"], "military": 10})
    assert game.validate(s, rules, good) is None
    s = st.advance(s, [good], rules)
    assert s["civs"]["c1"]["allocation"]["expansion"] == 30


def test_rejected_orders_become_news_not_changes(rules):
    s, _ = new_game(rules)
    before = st.state_hash(st.advance(s, [], rules))
    s2 = st.advance(s, [{"kind": "survey", "system": "nope", "user": 1}], rules)
    assert s2["log"][0]["kind"] == "order_rejected"
    s2["log"] = [e for e in s2["log"] if e["kind"] != "order_rejected"]
    s3 = st.advance(s, [], rules)
    assert st.state_hash(s2) == st.state_hash(s3) == before


def test_fog_of_war_in_the_map(rules):
    s, civ = new_game(rules)
    m = view.map_data(s, civ, rules)
    hidden = [x for x in m["systems"] if not x["surveyed"]]
    assert hidden and all("star" not in x and "bodies" not in x for x in hidden)
    assert any(x["home"] for x in m["systems"] if x["surveyed"])


def test_advisor_suggests_confirmable_orders(rules):
    s, civ = new_game(rules)
    s = run(s, rules, 8)
    civ = s["civs"]["c1"]
    tips = advisor.suggestions(s, civ, rules)
    assert tips and any(t["order"] for t in tips)
    for t in tips:
        if t["order"]:
            assert game.validate(s, rules, dict(t["order"], user=1)) is None
    t0 = advisor.answer("how do action credits work?", s, civ, rules, "", "T0")
    assert t0["tier"] == "T0" and "action credits" in t0["text"].lower()


def test_upgrade_from_v1_keeps_old_ticks_replayable(rules):
    v1 = st.genesis_v1(42)
    hashes_v1 = st.replay(42, {}, 5, start=v1)
    s = v1
    for _ in range(5):
        s = st.advance(s, [], rules)
    assert st.state_hash(s) == hashes_v1[-1]                    # old history untouched
    s = st.advance(s, [{"kind": "engine.upgrade", "to": 2}], rules)
    assert s["schema"] == 2 and s["tick"] == 6 and s["prev_hash"] == hashes_v1[-1]
    s = st.advance(s, [found()], rules)
    assert s["civs"]["c1"]["alive"]


def test_retire_releases_systems(rules):
    s, civ = new_game(rules)
    s = st.advance(s, [{"kind": "retire", "user": 1}], rules)
    assert not s["civs"]["c1"]["alive"] and s["systems"][civ["home"]]["owner"] is None
    assert "1" not in s["users"]


def test_long_run_is_deterministic_and_float_free(rules):
    def play():
        s, _ = new_game(rules)
        return st.replay(42, {}, 300, start=s, rules=rules)[-1]
    assert play() == play()


def test_advisor_order_json_round_trips(rules):
    import json
    s, civ = new_game(rules)
    s = run(s, rules, 8)
    for t in advisor.suggestions(s, s["civs"]["c1"], rules):
        if t["order"]:
            assert json.loads(t["order_json"]) == t["order"]


def test_advisor_t2_answers_through_the_gateway_and_falls_back(rules):
    import json
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    seen = {}

    class Gateway(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            seen["prompt"] = body["prompt"]
            out = json.dumps({"tier": "T2", "fallback": False, "proposal": {"text": "Spend expansion AC on surveys."}})
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(out.encode())

        def log_message(self, *a):
            pass

    srv = HTTPServer(("127.0.0.1", 0), Gateway)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    s, civ = new_game(rules)
    out = advisor.answer("how do surveys work?", s, civ, rules, f"http://127.0.0.1:{srv.server_port}", "T2")
    srv.shutdown()
    assert out == {"text": "Spend expansion AC on surveys.", "tier": "T2", "fallback": False, "sources": ["Surveying"]}
    assert "Test Reach" in seen["prompt"] and "Surveying" in seen["prompt"]      # Codex + fog-limited summary
    down = advisor.answer("how do surveys work?", s, civ, rules, "http://127.0.0.1:1", "T2")
    assert down["tier"] == "T0" and down["fallback"] and "survey" in down["text"].lower()


def test_fog_of_war_hides_names_of_unsurveyed_systems(rules):
    s, c1 = new_game(rules)
    s = st.advance(s, [found(user=2, name="Second Light", home_name="Secret Harbour")], rules)
    c1, c2 = s["civs"]["c1"], s["civs"]["c2"]
    assert c2["home"] not in c1["surveyed"]
    m = view.map_data(s, c1, rules)
    leaked = [x for x in m["systems"] if x["name"] == "Secret Harbour"]
    assert not leaked, "another civilization's home name is visible before it is surveyed"
    assert view.system_detail(s, c1, rules, c2["home"])["name"] != "Secret Harbour"
    assert view.system_detail(s, c2, rules, c2["home"])["name"] == "Secret Harbour"
