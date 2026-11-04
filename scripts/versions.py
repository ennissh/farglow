#!/usr/bin/env python3
"""Build numbers for pushed images, checked against the tags GHCR already holds.

A release is X.Y.Z (the VERSION file). Every build pushed after it is X.Y.Z-N. Installs that
follow `latest` or the newest build need every pushed number to be NEW and HIGHER than all
before it, so:
  * next RELEASE      -> RELEASE-(N+1), N = the highest build of RELEASE in the registry (0 if none);
                         refused if the registry already holds a HIGHER release or build line
                         (bump VERSION first)
  * check VERSION     -> exit 0, or 1 with the reason: an existing number is refused (it would
                         overwrite images that installs may be pinned to; --replace allows exactly
                         that), a number lower than the newest version is refused
  * release VERSION   -> exit 0 if the release tag X.Y.Z can still be pushed (it never existed)

Tags come on stdin, one per line (non-version tags like latest or local are ignored).
"""
from __future__ import annotations

import re
import sys

BUILD_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)-(\d+)$")
RELEASE_RE = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def key(tag: str):
    """Sort key: a release sorts before its builds (0.1.0 < 0.1.0-1 < 0.1.1). None if not a version."""
    m = BUILD_RE.match(tag)
    if m:
        return tuple(int(x) for x in m.groups()[:3]), int(m.group(4))
    m = RELEASE_RE.match(tag)
    if m:
        return tuple(int(x) for x in m.groups()), 0
    return None


def fmt(k) -> str:
    return ".".join(map(str, k[0])) + (f"-{k[1]}" if k[1] else "")


def newest(tags):
    return max((k for k in map(key, tags) if k), default=None)


def next_build(release: str, tags) -> tuple[bool, str]:
    m = RELEASE_RE.match(release)
    if not m:
        return False, f"VERSION {release!r} is not X.Y.Z"
    rel = tuple(int(x) for x in m.groups())
    top = newest(tags)
    if top and top[0] > rel:
        return False, (f"the registry already has {fmt(top)}, newer than VERSION {release}: "
                       "bump VERSION (or pull the latest code)")
    n = max((k[1] for k in map(key, tags) if k and k[0] == rel), default=0)
    return True, f"{release}-{n + 1}"


def check(version: str, tags, replace: bool = False) -> tuple[bool, str]:
    k = key(version)
    if k is None or not BUILD_RE.match(version):
        return False, f"{version} is not a build number (X.Y.Z-N, e.g. 0.1.0-7)"
    tags = set(tags)
    if version in tags:
        if replace:
            return True, f"{version} exists and will be REPLACED (--replace-version)"
        return False, f"{version} is already in the registry; choose a new number or pass --replace-version"
    top = newest(tags)
    if top and k <= top:
        return False, f"{version} is lower than the newest version in the registry ({fmt(top)})"
    return True, f"{version} is new"


def release_ok(version: str, tags) -> tuple[bool, str]:
    if not RELEASE_RE.match(version):
        return False, f"{version} is not a release number (X.Y.Z)"
    if version in set(tags):
        return False, f"release {version} is already published: bump VERSION for a new release"
    top = newest(tags)
    if top and key(version) <= top:
        return False, (f"release {version} would sort below {fmt(top)} already in the registry "
                       "(builds X.Y.Z-N come after their release): bump VERSION")
    return True, f"release {version} is new"


def main(argv: list[str]) -> int:
    if len(argv) < 2 or argv[0] not in ("next", "check", "release"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    tags = [t.strip() for t in sys.stdin.read().split() if t.strip()]
    fn = {"next": lambda: next_build(argv[1], tags),
          "check": lambda: check(argv[1], tags, "--replace" in argv[2:]),
          "release": lambda: release_ok(argv[1], tags)}[argv[0]]
    ok, msg = fn()
    print(msg, file=sys.stdout if ok else sys.stderr)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
