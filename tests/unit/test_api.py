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


def test_get_requests_never_write(settings):
    # Rule: a GET never changes anything. Phase 0 has no write routes at all.
    app = create_app(settings)
    writes = [r for r in app.url_map.iter_rules() if r.methods & {"POST", "PUT", "PATCH", "DELETE"}]
    assert writes == []
