"""PostgreSQL access (psycopg 3). PostgreSQL 16 is the only datastore."""
from __future__ import annotations

import logging
import time

import psycopg
from psycopg.rows import dict_row

from .config import Settings

log = logging.getLogger(__name__)


def connect(settings: Settings, autocommit: bool = False, application_name: str | None = None):
    return psycopg.connect(
        settings.database_url,
        autocommit=autocommit,
        row_factory=dict_row,
        connect_timeout=10,
        application_name=application_name or f"farglow-{settings.service}",
    )


def wait_for_db(settings: Settings, timeout: float = 120.0) -> None:
    deadline = time.monotonic() + timeout
    delay = 1.0
    while True:
        try:
            with connect(settings) as conn:
                conn.execute("SELECT 1")
            return
        except psycopg.OperationalError as exc:
            if time.monotonic() > deadline:
                raise
            log.info("waiting for database", extra={"error": str(exc).splitlines()[0]})
            time.sleep(delay)
            delay = min(delay * 2, 10.0)


def heartbeat(conn, service: str, instance: str, version: str, detail: dict | None = None) -> None:
    """Record that a service is alive; the status page and host admin read this table."""
    conn.execute(
        """
        INSERT INTO service_heartbeats (service, instance, version, seen_at, detail)
        VALUES (%s, %s, %s, now(), %s)
        ON CONFLICT (service, instance)
        DO UPDATE SET version = EXCLUDED.version, seen_at = now(), detail = EXCLUDED.detail
        """,
        (service, instance, version, psycopg.types.json.Jsonb(detail or {})),
    )
