#!/usr/bin/env python3
"""Every Python dependency is pinned exactly (==), and the same package has the same
version everywhere (containers/*/requirements.txt and requirements-dev.txt).

Run by test.sh. Exit 0 ok, 1 violations. To add or bump a dependency: pin the whole tree
(pip freeze in a clean venv), and check that amd64 and arm64 wheels exist (the images
install with --only-binary=:all:, so a missing wheel fails the arm64 build).
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LINE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)(\[[^\]]+\])?==([0-9][0-9A-Za-z.+!-]*)$")


def main() -> int:
    files = sorted(ROOT.glob("containers/*/requirements*.txt")) + sorted(ROOT.glob("requirements*.txt"))
    seen: dict[str, tuple[str, Path]] = {}
    errs = []
    for f in files:
        for n, raw in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = LINE.match(line)
            if not m:
                errs.append(f"{f.relative_to(ROOT)}:{n}: not an exact pin: {line}")
                continue
            name, ver = m.group(1).lower().replace("_", "-"), m.group(3)
            if name in seen and seen[name][0] != ver:
                errs.append(f"{f.relative_to(ROOT)}:{n}: {name}=={ver} but "
                            f"{seen[name][1].relative_to(ROOT)} pins {seen[name][0]}")
            seen.setdefault(name, (ver, f))
    for e in errs:
        print(f"check-pins: {e}")
    print(f"check-pins: {len(files)} files, {len(seen)} packages, {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
