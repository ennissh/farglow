from .. import config
from .. import log as flog
from ..queue import Runner
from .handlers import HANDLERS


def main() -> int:
    settings = config.load("worker")
    flog.setup("worker", settings.log_level)
    Runner(settings, "worker", ["worker"], HANDLERS).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
