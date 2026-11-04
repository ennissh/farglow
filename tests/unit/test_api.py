from farglow.api.app import create_app


def client(settings):
    app = create_app(settings)
    app.testing = True
    return app.test_client()


def test_healthz_needs_no_database(settings):
    r = client(settings).get("/healthz")
    assert r.status_code == 200 and r.json["status"] == "ok"


def test_readyz_reports_database_down(settings):
    r = client(settings).get("/readyz")
    assert r.status_code == 503 and r.json["reason"] == "database"


def test_index_renders_without_database(settings):
    r = client(settings).get("/")
    assert r.status_code == 200
    assert b"farglow" in r.data and b"database down" in r.data


def test_security_headers(settings):
    r = client(settings).get("/healthz")
    assert "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in r.headers["Content-Security-Policy"]
    assert r.headers["X-Content-Type-Options"] == "nosniff"


def test_404_page(settings):
    r = client(settings).get("/no-such-page")
    assert r.status_code == 404 and b"galactic catalogue" in r.data


def test_state_changing_routes_are_post_only(settings):
    # Rule: a GET never changes anything. Every action route accepts POST only.
    app = create_app(settings)
    actions = ("/act/", "/admin/engine/", "/clock/", "/walkthrough/", "/advisor/", "/account/delete", "/signout",
               "/verify/resend")
    for rule in app.url_map.iter_rules():
        if any(str(rule).startswith(a) for a in actions):
            assert "GET" not in rule.methods, f"{rule} must be POST-only"


def test_post_without_csrf_is_refused(settings):
    r = client(settings).post("/signin", data={"email": "a@b.c", "password": "x"})
    assert r.status_code == 400
