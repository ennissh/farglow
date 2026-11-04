#!/usr/bin/env python3
"""Container health check: GET http://127.0.0.1:PORT/healthz must answer 200.

Python urllib, not curl/wget: runtime images ship no download tools.
"""
import sys
import urllib.request

PORT = 8000
try:
    with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/healthz", timeout=4) as resp:  # noqa: S310
        sys.exit(0 if resp.status == 200 else 1)
except Exception as exc:  # noqa: BLE001
    print(f"unhealthy: {exc}")
    sys.exit(1)
