#!/usr/bin/env python3
"""The migrate image is one-shot; healthy means the package and its migrations load."""
import sys

try:
    from farglow import migrate

    migrate.discover()
except Exception as exc:  # noqa: BLE001
    print(f"unhealthy: {exc}")
    sys.exit(1)
sys.exit(0)
