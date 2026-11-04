"""Signed, single-use links for email actions.

Token = base64url(payload) "." base64url(HMAC-SHA256(key, payload)). The payload carries a
random nonce; the nonce row in link_tokens makes the link single-use and revocable (a
rollback revokes links issued after the restore point). Rules from README.md:
  * a GET never changes anything: GET shows a confirm page, the POST calls consume();
  * email replies can only ask questions.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time


class LinkError(Exception):
    """The link is malformed, forged, expired, used or revoked."""


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def sign(key: str, purpose: str, subject: str, ttl_s: int, now: float | None = None,
         nonce: str | None = None) -> tuple[str, dict]:
    if not key:
        raise ValueError("link signing key is empty")
    payload = {
        "p": purpose,
        "s": subject,
        "e": int((now if now is not None else time.time()) + ttl_s),
        "n": nonce or secrets.token_urlsafe(16),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    mac = hmac.new(key.encode(), raw, hashlib.sha256).digest()
    return f"{_b64(raw)}.{_b64(mac)}", payload


def verify(key: str, token: str, purpose: str, now: float | None = None) -> dict:
    """Check signature, purpose and expiry. Does NOT consume: see consume()."""
    try:
        raw_b64, mac_b64 = token.split(".", 1)
        raw = _unb64(raw_b64)
        mac = _unb64(mac_b64)
    except (ValueError, TypeError) as exc:
        raise LinkError("malformed link") from exc
    expected = hmac.new(key.encode(), raw, hashlib.sha256).digest()
    if not hmac.compare_digest(mac, expected):
        raise LinkError("bad signature")
    payload = json.loads(raw)
    if payload.get("p") != purpose:
        raise LinkError("wrong purpose")
    if payload["e"] < (now if now is not None else time.time()):
        raise LinkError("expired")
    return payload


def issue(conn, key: str, purpose: str, subject: str, ttl_s: int, tick: int | None = None) -> str:
    token, payload = sign(key, purpose, subject, ttl_s)
    conn.execute(
        "INSERT INTO link_tokens (nonce, purpose, subject, expires_at, issued_tick) "
        "VALUES (%s, %s, %s, to_timestamp(%s), %s)",
        (payload["n"], purpose, subject, payload["e"], tick),
    )
    return token


def consume(conn, key: str, token: str, purpose: str) -> dict:
    """Verify and mark used, atomically. A second call with the same token fails."""
    payload = verify(key, token, purpose)
    row = conn.execute(
        """
        UPDATE link_tokens SET used_at = now()
        WHERE nonce = %s AND purpose = %s AND used_at IS NULL AND revoked_at IS NULL
              AND expires_at > now()
        RETURNING subject
        """,
        (payload["n"], purpose),
    ).fetchone()
    if row is None:
        raise LinkError("link already used, revoked or unknown")
    return payload


def revoke_after_tick(conn, tick: int) -> int:
    """Rollback support: links issued after the restore point stop working."""
    return conn.execute(
        "UPDATE link_tokens SET revoked_at = now() WHERE issued_tick > %s AND revoked_at IS NULL",
        (tick,),
    ).rowcount
