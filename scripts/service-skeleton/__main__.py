"""farglow-__NAME__: __TITLE__

One process per container. Touch /tmp/farglow-heartbeat from the main loop: the health
check fails when it goes stale. Log with the structured logger, never print secrets.
"""
import logging
import signal
import time

from .. import config
from .. import log as flog

log = logging.getLogger("farglow.__MODULE__")
HEARTBEAT = "/tmp/farglow-heartbeat"


def main() -> int:
    settings = config.load("__NAME__")
    flog.setup("__NAME__", settings.log_level)
    stopping = False

    def stop(*_):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, stop)
    log.info("started")
    while not stopping:
        with open(HEARTBEAT, "w", encoding="utf-8") as fh:
            fh.write(str(int(time.time())))
        time.sleep(5)  # replace with the service's work
    log.info("stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
