#!/usr/bin/env python3
"""The content hash of one service image: its Dockerfile plus every file its COPY lines read.

    scripts/inputs.py api                  -> <16 hex digits>
    scripts/inputs.py api --salt platforms  (mixes in a string, e.g. the platform list)

build.sh uses it to skip images whose inputs haven't changed:
  * --local: the image already loaded with the same `org.farglow.inputs` label is kept as is;
  * push:    the registry already has `farglow-<svc>:inputs-<hash>`: the new version tag is
             added to that image (server side, no rebuild, no upload).
The build metadata (version, revision, time) is NOT an input: it is stamped last in every
Dockerfile so it never invalidates the cache. Paths follow .dockerignore's exclusions
(__pycache__, *.pyc). Same idea as rapax-cloud's v2_inputs.py; written for Farglow.
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_PARTS = {"__pycache__"}
SKIP_SUFFIX = {".pyc"}


def copy_sources(dockerfile: Path) -> list[str]:
    text = re.sub(r"\\\n", " ", dockerfile.read_text(encoding="utf-8"))
    sources = []
    for line in text.splitlines():
        line = line.strip()
        if not re.match(r"^(COPY|ADD)\s", line, re.I):
            continue
        parts = [p for p in line.split()[1:] if not p.startswith("--")]
        if any(p.startswith("--from") for p in line.split()):
            continue                         # from another stage: not a build-context input
        sources.extend(parts[:-1])
    return sources


def files_of(rel: str) -> list[Path]:
    p = ROOT / rel
    if p.is_file():
        return [p]
    if p.is_dir():
        return sorted(f for f in p.rglob("*") if f.is_file() and not (set(f.parts) & SKIP_PARTS)
                      and f.suffix not in SKIP_SUFFIX)
    raise FileNotFoundError(f"COPY source {rel} does not exist")


def inputs_hash(service: str, salt: str = "") -> str:
    df = ROOT / "containers" / service / "Dockerfile"
    h = hashlib.sha256()
    h.update(b"farglow-inputs/1\0" + salt.encode() + b"\0")
    for f in [df] + [f for src in copy_sources(df) for f in files_of(src)]:
        rel = f.relative_to(ROOT).as_posix()
        h.update(rel.encode() + b"\0")
        h.update(hashlib.sha256(f.read_bytes()).digest())
        h.update(b"\1" if f.stat().st_mode & 0o111 else b"\0")     # an executable bit is content too
    return h.hexdigest()[:16]


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    salt = argv[argv.index("--salt") + 1] if "--salt" in argv else ""
    try:
        print(inputs_hash(argv[0], salt))
    except FileNotFoundError as exc:
        print(f"inputs: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
