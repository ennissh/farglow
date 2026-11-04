"""Structured logging: one JSON object per line on stdout, collected by Docker.

Fields: ts, level, service, logger, msg, plus any `extra={...}` keys. Secrets must never
be passed in `extra`; keys that look like secrets are redacted as a backstop.
"""
from __future__ import annotations

import json
import logging
import sys
import time

_REDACT = ("password", "secret", "token", "api_key", "apikey", "authorization")
_STD = set(vars(logging.LogRecord("", 0, "", 0, "", (), None))) | {"message", "asctime"}


class JsonFormatter(logging.Formatter):
    def __init__(self, service: str):
        super().__init__()
        self.service = service

    def format(self, record: logging.LogRecord) -> str:
        out = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(record.created))
            + f".{int(record.msecs):03d}Z",
            "level": record.levelname,
            "service": self.service,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, value in record.__dict__.items():
            if key in _STD or key.startswith("_"):
                continue
            out[key] = "[redacted]" if any(r in key.lower() for r in _REDACT) else value
        if record.exc_info:
            out["exc"] = self.formatException(record.exc_info)
        return json.dumps(out, default=str, ensure_ascii=False)


def setup(service: str, level: str = "INFO") -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter(service))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    return logging.getLogger(service)
