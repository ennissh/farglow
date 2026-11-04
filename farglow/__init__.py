"""Farglow: a grounded sci-fi 4X MMO played about five minutes a day.

A Generative Distractions game. (c) 2026 Citus Technologies, LLC. BUSL 1.1, see LICENSE.md.
"""
import os
from pathlib import Path


def _version() -> str:
    # Images bake FARGLOW_BUILD (VERSION+git hash) in at build time; a checkout reads VERSION.
    build = os.environ.get("FARGLOW_BUILD")
    if build:
        return build
    for candidate in (Path(__file__).resolve().parent.parent / "VERSION", Path("/app/VERSION")):
        if candidate.is_file():
            return candidate.read_text(encoding="utf-8").strip()
    return "0.0.0+unknown"


__version__ = _version()
