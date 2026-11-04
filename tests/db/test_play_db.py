"""Functional: sign-up -> verify -> found -> ticks -> play -> Dispatch -> delete, through the real app."""
import re
from dataclasses import replace

import pytest

from farglow import db, queue
from farglow.api.app import create_app
from farglow.engine import clock, store
from farglow.worker import handlers

pytestmark = pytest.mark.db
CSRF = "test-csrf-token"


def client_for(settings):
    app = create_app(settings)
    app.testing = True
    c = app.test_client()
    with c.session_transaction() as sess:
        sess["csrf"] = CSRF
    return c


def post(c, url, **data):
    return c.post(url, data={"csrf": CSRF, **data})


def tick(settings, n=1):
    with db.connect(settings, autocommit=True) as conn:
        clock.ensure_state(conn, settings)
        for _ in range(n):
            new = clock.run_tick(conn, settings, force=True)
            job = queue.claim(conn, ["worker"], "test")
            while job:
                handlers.HANDLERS[job["kind"]](job, settings)
                queue.complete(conn, job["id"])
                job = queue.claim(conn, ["worker"], "test")
    return new


def signup(c, email="pilot@example.test", year="1990"):
    with c.session_transaction() as sess:      # signup clears the session; keep our CSRF token
        sess["csrf"] = CSRF
    r = post(c, "/signup", email=email, display_name="Pilot", password="correct horse battery",
             birth_month="5", birth_year=year)
    with c.session_transaction() as sess:
        sess["csrf"] = CSRF
    return r


def test_under_13_is_refused_and_nothing_is_kept(pg_settings):
    c = client_for(pg_settings)
    r = signup(c, year="2020")
    assert r.status_code == 403 and "fg_age_lock" in r.headers.get("Set-Cookie", "")
    with db.connect(pg_settings) as conn:
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0


def test_email_verification_link_is_post_only_and_single_use(pg_settings):
    s = replace(pg_settings, smtp_host="smtp.example.test")       # mail on: verification required
    c = client_for(s)
    assert signup(c).headers["Location"].endswith("/verify/pending")
    assert c.get("/play").headers["Location"].endswith("/verify/pending")
    with db.connect(s) as conn:
        job = conn.execute("SELECT payload FROM jobs WHERE kind = 'mail.send'").fetchone()
    token = re.search(r"/verify\?t=(\S+)", job["payload"]["text"]).group(1)
    r = c.get(f"/verify?t={token}")
    assert r.status_code == 200 and b"Confirm my email" in r.data
    with db.connect(s) as conn:   # the GET verified nothing
        assert conn.execute("SELECT email_verified_at FROM users").fetchone()["email_verified_at"] is None
    assert post(c, "/verify", t=token).status_code == 302
    assert post(c, "/verify", t=token).status_code == 400        # single use


def test_full_first_light_loop(pg_settings):
    s = replace(pg_settings, admin_email="pilot@example.test", debug=True)
    tick(s, 1)                                                   # genesis + tick 1
    c = client_for(s)
    assert signup(c).headers["Location"].endswith("/play")        # no SMTP: ready at once
    assert c.get("/play").headers["Location"].endswith("/found")
    assert b"Meet your civilization" in c.get("/found").data
    r = post(c, "/found", name="Ashenreach Collective", set="5", home_name="Hearth",
             **{f"attr_{k}": str(v) for k, v in
                {"curiosity": 2, "industry": 0, "growth": -1, "cohesion": 1, "martial": -2, "openness": 0}.items()})
    assert r.status_code == 302
    assert b"gathering" in c.get("/play").data                   # founded at the next tick
    tick(s, 1)
    page = c.get("/play")
    assert page.status_code == 200 and b"Ashenreach Collective" in page.data and b"Hearth" in page.data
    m = c.get("/api/v1/map").get_json()
    assert m["owned"] and any(x["home"] for x in m["systems"] if x.get("surveyed"))
    for url in ("/governor", "/research", "/research?tech=orbital_survey_array", "/dispatch", "/admin", "/account"):
        assert c.get(url).status_code == 200, url
    assert b"is founded at Hearth" in c.get("/dispatch").data
    # orders: allocation, research queue, a survey once affordable
    assert post(c, "/act/allocation", expansion="35", research="30", social="10", economic="20",
                military="5").status_code == 302
    post(c, "/act/queue", tech="belt_extraction_rigs", op="add")
    tick(s, 7)
    with db.connect(s) as conn:
        state = store.current_state(conn)
    civ = state["civs"]["c1"]
    assert civ["allocation"]["expansion"] == 35 and "belt_extraction_rigs" in civ["research"]["queue"] + civ["research"]["done"] + [civ["research"]["current"]]
    # the advisor's suggestion button posts a valid order straight from the rendered page
    import html as _html
    found = re.search(r'name="order" value="([^"]*)"', c.get("/play").data.decode())
    assert found, "the advisor offered no confirmable suggestion"
    r = post(c, "/act/advice", order=_html.unescape(found.group(1)), back="/play")
    assert r.status_code == 302
    assert b"Not possible" not in c.get("/play").data
    target = next(x["id"] for x in m["systems"] if not x["surveyed"])
    r = post(c, "/act/survey", system=target)
    assert r.status_code == 302
    # the advisor answers at T0 from the Codex, and logs it
    a = post(c, "/advisor/ask", question="What are action credits?")
    assert a.status_code == 200 and b"Codex" in a.data
    # host admin can run the clock
    assert post(c, "/admin/engine/verify").status_code == 302
    assert post(c, "/clock/advance").status_code == 302
    # the morning Dispatch email: every 12 ticks on a development server, to verified players
    tick(s, 4)
    with db.connect(s) as conn:
        mail = conn.execute("SELECT payload FROM jobs WHERE kind = 'mail.send' AND payload->>'subject' LIKE 'The Dispatch%%'"
                            ).fetchone()
    assert mail and "Ashenreach Collective" in mail["payload"]["text"] and "/play" in mail["payload"]["text"]
    # delete the account: the civilization retires at the next tick
    r = post(c, "/account/delete", confirm="DELETE", password="correct horse battery")
    assert r.status_code == 302
    tick(s, 1)
    with db.connect(s) as conn:
        state = store.current_state(conn)
        assert conn.execute("SELECT count(*) AS n FROM users").fetchone()["n"] == 0
        ok, msg = clock.verify_chain(conn)
    assert not state["civs"]["c1"]["alive"]
    assert ok, msg
