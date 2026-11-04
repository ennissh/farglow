import pytest

from farglow import config


def test_defaults_hourly(monkeypatch):
    for k in ("FARGLOW_DEBUG", "FARGLOW_TICK_SECONDS"):
        monkeypatch.delenv(k, raising=False)
    assert config.load().tick_seconds == 3600


def test_debug_ticks_every_five_minutes(monkeypatch):
    monkeypatch.setenv("FARGLOW_DEBUG", "true")
    monkeypatch.delenv("FARGLOW_TICK_SECONDS", raising=False)
    assert config.load().tick_seconds == 300


def test_empty_values_mean_default(monkeypatch):
    monkeypatch.setenv("FARGLOW_TICK_SECONDS", "")
    monkeypatch.delenv("FARGLOW_DEBUG", raising=False)
    assert config.load().tick_seconds == 3600


def test_bad_tier_refused(monkeypatch):
    monkeypatch.setenv("FARGLOW_AI_TIER", "T9")
    with pytest.raises(ValueError):
        config.load()


def test_secret_from_file(monkeypatch, tmp_path):
    f = tmp_path / "pw"
    f.write_text("from-file\n")
    monkeypatch.setenv("POSTGRES_PASSWORD_FILE", str(f))
    assert config.load().db_password == "from-file"


def test_database_url_escapes_password():
    s = config.Settings(db_password="p@ss:w/rd")
    assert "p%40ss%3Aw%2Frd@" in s.database_url
