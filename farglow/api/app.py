"""Flask application factory.

Health endpoints:
  /healthz  liveness: the process answers (no database). Used by the container HEALTHCHECK.
  /readyz   readiness: database reachable and schema at this release's head.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import psycopg
from flask import Flask, g, jsonify, redirect, render_template, url_for
from werkzeug.middleware.proxy_fix import ProxyFix

from .. import __version__, config, db, migrate

log = logging.getLogger("farglow.api")
WEB = Path(__file__).resolve().parent.parent / "web"

CSP = (
    "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
    "font-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def engine_status(settings: config.Settings) -> dict:
    out = {"version": __version__, "database": "down", "engine": None, "services": []}
    try:
        with db.connect(settings) as conn:
            out["database"] = "up"
            eng = conn.execute(
                "SELECT tick, state_hash, paused, pause_reason, tick_seconds, last_tick_at, next_tick_at, galaxy_seed "
                "FROM engine_state WHERE id = 1").fetchone()
            if eng:
                eng = dict(eng)
                now = datetime.now(timezone.utc)
                eng["next_tick_in_s"] = max(0, int((eng["next_tick_at"] - now).total_seconds()))
                out["engine"] = eng
            # Latest heartbeat per service: a recreated container has a new hostname (instance),
            # so older rows of the same service are history, not extra replicas.
            out["services"] = conn.execute(
                "SELECT DISTINCT ON (service) service, instance, version, seen_at, "
                "extract(epoch FROM now() - seen_at)::int AS age_s FROM service_heartbeats "
                "ORDER BY service, seen_at DESC"
            ).fetchall()
    except psycopg.Error as exc:
        log.warning("status query failed", extra={"error": str(exc).splitlines()[0] if str(exc) else repr(exc)})
    return out


def create_app(settings: config.Settings | None = None) -> Flask:
    settings = settings or config.load("api")
    app = Flask(__name__, template_folder=str(WEB / "templates"), static_folder=str(WEB / "static"),
                static_url_path="/static")
    app.config.update(SECRET_KEY=settings.secret_key or None, SESSION_COOKIE_HTTPONLY=True,
                      SESSION_COOKIE_SAMESITE="Lax",
                      SESSION_COOKIE_SECURE=settings.public_url.startswith("https://"))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)  # nginx sets X-Forwarded-*
    app.config["FARGLOW_SETTINGS"] = settings
    app.config["PERMANENT_SESSION_LIFETIME"] = 30 * 24 * 3600
    head = migrate.head_version()

    from . import auth, game
    app.register_blueprint(auth.bp)
    app.register_blueprint(game.bp)

    @app.before_request
    def _user():
        g.user = None
        if not app.config.get("FARGLOW_NO_DB"):
            try:
                auth.load_user()
            except psycopg.Error:
                g.user = None
        auth.check_csrf()

    app.jinja_env.globals.update(csrf_token=auth.csrf_token)

    @app.context_processor
    def _globals():
        return {"csrf_token": auth.csrf_token, "user": g.get("user"), "debug_server": settings.debug,
                "version": __version__}

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("Content-Security-Policy", CSP)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "same-origin")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return resp

    @app.template_filter("sentence")
    def sentence(text):
        text = str(text or "")
        return text[:1].upper() + text[1:]

    @app.template_filter("thousands")
    def thousands(n):
        return f"{n:,}" if isinstance(n, int) else n

    @app.get("/healthz")
    def healthz():
        return jsonify(status="ok", service="api", version=__version__)

    @app.get("/readyz")
    def readyz():
        try:
            with db.connect(settings) as conn:
                current = conn.execute("SELECT coalesce(max(version), 0) AS v FROM schema_migrations").fetchone()["v"]
        except psycopg.Error as exc:
            return jsonify(status="unavailable", reason="database", detail=str(exc).splitlines()[0] if str(exc) else ""), 503
        if current != head:
            return jsonify(status="unavailable", reason="schema", current=current, head=head), 503
        return jsonify(status="ready", schema=current, version=__version__)

    @app.get("/api/v1/status")
    def api_status():
        s = engine_status(settings)
        return jsonify(s)

    @app.get("/")
    def index():
        if g.get("user"):
            return redirect(url_for("game.play"))
        return render_template("index.html", s=engine_status(settings), settings=settings)

    @app.get("/partials/status")
    def status_partial():
        return render_template("partials/status.html", s=engine_status(settings))

    @app.errorhandler(400)
    def bad_request(e):
        msg = getattr(e, "description", "") or "That request didn't make sense."
        return render_template("error.html", code=400, message=msg), 400

    @app.errorhandler(403)
    def forbidden(_):
        return render_template("error.html", code=403, message="That page is for the host admin."), 403

    @app.errorhandler(404)
    def not_found(_):
        return render_template("error.html", code=404, message="That page is not in the galactic catalogue."), 404

    return app


def wsgi() -> Flask:
    from .. import log as flog
    settings = config.load("api")
    flog.setup("api", settings.log_level)
    return create_app(settings)
