"""Job handlers for the 'worker' queue. Each takes (job, settings) and raises on failure.

Phase 0 has only the plumbing jobs; Dispatch, moderation and advisor jobs arrive in
Phase 1 and 2 and register here.
"""
from __future__ import annotations

import logging

from ..config import Settings

log = logging.getLogger("farglow.worker")


def tick_completed(job: dict, settings: Settings) -> None:
    # Phase 1: build the Dispatch and news for the tick. Phase 0: record that we saw it.
    log.info("tick completed", extra={"tick": job["payload"].get("tick")})


def noop(job: dict, settings: Settings) -> None:
    log.info("noop job", extra={"payload": job["payload"]})


HANDLERS = {
    "tick.completed": tick_completed,
    "noop": noop,
}
