"""Shared fixtures. DB tests need FARGLOW_TEST_PG=host:port (test.sh provides one)."""
import os
import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests" / "lib"))


def make_settings(**overrides):
    from farglow.config import Settings
    base = dict(service="test", secret_key="test-secret", link_signing_key="test-link-key",
                galaxy_seed=42, tick_seconds=3600, db_password="test", db_user="postgres")
    base.update(overrides)
    return Settings(**base)


@pytest.fixture
def settings():
    return make_settings(db_host="127.0.0.1", db_port=1)  # nothing listens: DB calls fail fast


@pytest.fixture
def pg_settings():
    """A fresh, migrated database per test."""
    target = os.environ.get("FARGLOW_TEST_PG")
    if not target:
        pytest.skip("FARGLOW_TEST_PG not set (run ./test.sh)")
    import psycopg

    from farglow import migrate
    host, port = target.rsplit(":", 1)
    name = f"t_{uuid.uuid4().hex[:12]}"
    admin = f"postgresql://postgres:test@{host}:{port}/postgres"
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'CREATE DATABASE "{name}"')
    s = make_settings(db_host=host, db_port=int(port), db_name=name, tick_seconds=60)
    migrate.run(s)
    yield s
    with psycopg.connect(admin, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE "{name}" WITH (FORCE)')
