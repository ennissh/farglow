from conftest import make_settings
from farglow.llm.gateway import create_app


def post(settings, body):
    app = create_app(settings)
    app.testing = True
    return app.test_client().post("/v1/propose", json=body)


def test_t0_uses_templates():
    r = post(make_settings(ai_tier="T0"), {"task": "advisor.greeting"})
    assert r.json["tier"] == "T0" and r.json["fallback"] is False
    assert r.json["proposal"]["template"] is True


def test_unreachable_t2_falls_back_to_t0():
    s = make_settings(ai_tier="T2", llm_endpoint="http://127.0.0.1:1", llm_model="m", llm_timeout=2)
    r = post(s, {"task": "advisor.greeting", "prompt": "hi"})
    assert r.status_code == 200
    assert r.json["tier"] == "T0" and r.json["fallback"] is True


def test_t4_not_available_falls_back():
    r = post(make_settings(ai_tier="T4", llm_endpoint="http://x"), {"task": "news.headline"})
    assert r.json["fallback"] is True
