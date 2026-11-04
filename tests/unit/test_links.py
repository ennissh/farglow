import pytest

from farglow import links

KEY = "k" * 32


def test_round_trip():
    token, payload = links.sign(KEY, "dispatch.decide", "civ:1", 600)
    assert links.verify(KEY, token, "dispatch.decide")["n"] == payload["n"]


def test_tampered_token_fails():
    token, _ = links.sign(KEY, "p", "s", 600)
    raw, mac = token.split(".")
    forged = links._b64(links._unb64(raw).replace(b'"s":"s"', b'"s":"x"')) + "." + mac
    with pytest.raises(links.LinkError):
        links.verify(KEY, forged, "p")


def test_wrong_key_fails():
    token, _ = links.sign(KEY, "p", "s", 600)
    with pytest.raises(links.LinkError):
        links.verify("other-key", token, "p")


def test_wrong_purpose_fails():
    token, _ = links.sign(KEY, "p", "s", 600)
    with pytest.raises(links.LinkError):
        links.verify(KEY, token, "q")


def test_expired_fails():
    token, _ = links.sign(KEY, "p", "s", 60, now=1000)
    with pytest.raises(links.LinkError, match="expired"):
        links.verify(KEY, token, "p", now=1061)


def test_malformed_fails():
    with pytest.raises(links.LinkError):
        links.verify(KEY, "not-a-token", "p")


def test_empty_key_refused():
    with pytest.raises(ValueError):
        links.sign("", "p", "s", 60)
