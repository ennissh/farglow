"""Accounts: sign-up (stated age), email verification, sign-in, sign-out, settings, deletion.

Rules (README, config/moderation.poc.yaml):
  * Age is self-declared as birth month and year; under-13s are refused and nothing from the
    attempt is kept (a 24-hour browser lockout stops an immediate retry with another age).
  * Email verification uses a signed single-use link. The GET shows a confirm page; only the
    POST verifies (a GET never changes anything, so link scanners can't verify for you).
  * If the server has no SMTP configured, accounts are verified at sign-up (a LAN server).
  * The first account with the host admin email (FARGLOW_ADMIN_EMAIL) is the host admin.
"""
from __future__ import annotations

import re
import secrets
from datetime import datetime, timezone
from functools import wraps

import psycopg
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .. import db, links, queue
from ..engine import store

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[A-Za-z]{2,}$")
VERIFY_TTL = 48 * 3600
MIN_PASSWORD = 10


def settings():
    return current_app.config["FARGLOW_SETTINGS"]


def age_of(year: int, month: int, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    return now.year - year - (1 if now.month < month else 0)


def load_user():
    g.user = None
    uid, ver = session.get("uid"), session.get("ver")
    if not uid:
        return
    with db.connect(settings()) as conn:
        row = conn.execute("SELECT * FROM users WHERE id = %s", (uid,)).fetchone()
        if row and row["session_version"] == ver:
            g.user = row
            if request.method == "POST":      # GETs never write; "last seen" is updated by actions
                conn.execute("UPDATE users SET last_seen_at = now() WHERE id = %s", (uid,))
                conn.commit()
        else:
            session.clear()


def csrf_token() -> str:
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(24)
    return session["csrf"]


def check_csrf():
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("csrf") or request.headers.get("X-CSRF-Token")
        if not sent or not secrets.compare_digest(sent, session.get("csrf", "")):
            abort(400, "Your session expired. Reload the page and try again.")


def login_required(view):
    @wraps(view)
    def wrapped(*a, **kw):
        if g.user is None:
            return redirect(url_for("auth.signin", next=request.path))
        if g.user["email_verified_at"] is None:
            return redirect(url_for("auth.verify_pending"))
        return view(*a, **kw)
    return wrapped


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*a, **kw):
        if not g.user["is_admin"]:
            abort(403)
        return view(*a, **kw)
    return wrapped


def _send_verification(conn, user) -> None:
    s = settings()
    token = links.issue(conn, s.link_signing_key, "verify_email", str(user["id"]), VERIFY_TTL)
    url = f"{s.public_url}/verify?t={token}"
    queue.enqueue(conn, "mail", "mail.send", {
        "to": user["email"],
        "subject": "Confirm your Farglow account",
        "text": (f"Hello {user['display_name']},\n\nConfirm your email to start playing on {s.public_url}:\n\n{url}\n\n"
                 "The link works once and expires in 48 hours. If you didn't sign up, ignore this email.\n"),
    })


@bp.route("/signup", methods=["GET", "POST"])
def signup():
    if g.user:
        return redirect(url_for("game.play"))
    if request.cookies.get("fg_age_lock"):
        return render_template("auth/signup.html", locked=True, form={}), 403
    form = request.form if request.method == "POST" else {}
    if request.method == "GET":
        return render_template("auth/signup.html", form={}, locked=False)
    email = (form.get("email") or "").strip()
    name = (form.get("display_name") or "").strip()
    pw = form.get("password") or ""
    errors = []
    if not EMAIL_RE.match(email):
        errors.append("Enter a valid email address.")
    if not 2 <= len(name) <= 32:
        errors.append("Your display name is 2-32 characters.")
    if len(pw) < MIN_PASSWORD:
        errors.append(f"Use a password of at least {MIN_PASSWORD} characters.")
    try:
        year, month = int(form.get("birth_year", "")), int(form.get("birth_month", ""))
        now = datetime.now(timezone.utc)
        if not (1900 <= year <= now.year and 1 <= month <= 12):
            raise ValueError
    except ValueError:
        errors.append("Enter the month and year you were born.")
        year = month = None
    if errors:
        return render_template("auth/signup.html", form=form, errors=errors, locked=False), 400
    if age_of(year, month) < 13:
        # COPPA: refuse, keep nothing; stop an immediate retry with a different age.
        resp = current_app.make_response((render_template("auth/signup.html", refused=True, form={}, locked=True), 403))
        resp.set_cookie("fg_age_lock", "1", max_age=24 * 3600, httponly=True, samesite="Lax",
                        secure=request.is_secure)
        return resp
    s = settings()
    with db.connect(s) as conn:
        try:
            with conn.transaction():
                first_admin = (email.lower() == (s.admin_email or "").lower() and not conn.execute(
                    "SELECT 1 FROM users WHERE is_admin").fetchone())
                user = conn.execute(
                    "INSERT INTO users (email, email_lower, display_name, password_hash, birth_year, birth_month, "
                    "is_admin, email_verified_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING *",
                    (email, email.lower(), name, generate_password_hash(pw), year, month, first_admin,
                     None if s.mail_enabled else datetime.now(timezone.utc))).fetchone()
                if s.mail_enabled:
                    _send_verification(conn, user)
        except psycopg.errors.UniqueViolation:
            return render_template("auth/signup.html", form=form, locked=False,
                                   errors=["An account with that email already exists. Sign in instead."]), 400
    session.clear()
    session.update(uid=user["id"], ver=user["session_version"])
    if not s.mail_enabled:
        flash("This server has no email set up, so your account is ready now.")
        return redirect(url_for("game.play"))
    return redirect(url_for("auth.verify_pending"))


@bp.get("/verify/pending")
def verify_pending():
    if g.user is None:
        return redirect(url_for("auth.signin"))
    if g.user["email_verified_at"]:
        return redirect(url_for("game.play"))
    return render_template("auth/verify_pending.html")


@bp.post("/verify/resend")
def verify_resend():
    if g.user is None or g.user["email_verified_at"]:
        return redirect(url_for("auth.signin"))
    with db.connect(settings()) as conn:
        recent = conn.execute("SELECT count(*) AS n FROM link_tokens WHERE purpose = 'verify_email' AND subject = %s "
                              "AND created_at > now() - interval '10 minutes'", (str(g.user["id"]),)).fetchone()["n"]
        if recent >= 3:
            flash("We've sent a few already. Check your spam folder, or wait 10 minutes.")
        else:
            _send_verification(conn, g.user)
            conn.commit()
            flash("Sent. Check your inbox.")
    return redirect(url_for("auth.verify_pending"))


@bp.route("/verify", methods=["GET", "POST"])
def verify():
    token = request.values.get("t", "")
    s = settings()
    try:
        payload = links.verify(s.link_signing_key, token, "verify_email")
    except links.LinkError as exc:
        return render_template("auth/verify.html", error=str(exc), token=None), 400
    if request.method == "GET":       # never verify on GET: show the confirm button
        return render_template("auth/verify.html", token=token, error=None)
    with db.connect(s) as conn:
        try:
            with conn.transaction():
                links.consume(conn, s.link_signing_key, token, "verify_email")
                user = conn.execute("UPDATE users SET email_verified_at = coalesce(email_verified_at, now()) "
                                    "WHERE id = %s RETURNING *", (int(payload["s"]),)).fetchone()
        except links.LinkError as exc:
            return render_template("auth/verify.html", error=str(exc), token=None), 400
    if user is None:
        return render_template("auth/verify.html", error="that account no longer exists", token=None), 400
    session.clear()
    session.update(uid=user["id"], ver=user["session_version"])
    flash("Email confirmed. Welcome to Farglow.")
    return redirect(url_for("game.play"))


@bp.route("/signin", methods=["GET", "POST"])
def signin():
    if request.method == "GET":
        return render_template("auth/signin.html", next=request.args.get("next", ""))
    email = (request.form.get("email") or "").strip().lower()
    with db.connect(settings()) as conn:
        user = conn.execute("SELECT * FROM users WHERE email_lower = %s", (email,)).fetchone()
    if not user or not check_password_hash(user["password_hash"], request.form.get("password") or ""):
        return render_template("auth/signin.html", error="That email and password don't match.",
                               next=request.form.get("next", "")), 401
    session.clear()
    session.update(uid=user["id"], ver=user["session_version"])
    nxt = request.form.get("next") or ""
    return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else url_for("game.play"))


@bp.post("/signout")
def signout():
    session.clear()
    return redirect(url_for("index"))


@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        with db.connect(settings()) as conn:
            conn.execute("UPDATE users SET dispatch_email = %s WHERE id = %s",
                         (request.form.get("dispatch_email") == "on", g.user["id"]))
            conn.commit()
        flash("Settings saved.")
        return redirect(url_for("auth.account"))
    minor = age_of(g.user["birth_year"], g.user["birth_month"]) < 18
    return render_template("auth/account.html", minor=minor)


@bp.post("/account/delete")
@login_required
def delete_account():
    if (request.form.get("confirm") or "").strip() != "DELETE" or \
            not check_password_hash(g.user["password_hash"], request.form.get("password") or ""):
        flash("Type DELETE and your password to delete your account.")
        return redirect(url_for("auth.account"))
    with db.connect(settings()) as conn:
        state = store.current_state(conn)
        if state and str(g.user["id"]) in state.get("users", {}):
            store.queue_order(conn, {"kind": "retire", "user": int(g.user["id"])}, g.user["id"])
        conn.execute("DELETE FROM users WHERE id = %s", (g.user["id"],))
        conn.commit()
    session.clear()
    flash("Your account is deleted. Your civilization leaves the galaxy at the next tick.")
    return redirect(url_for("index"))
