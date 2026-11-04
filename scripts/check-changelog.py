#!/usr/bin/env python3
"""CHANGELOG rule: a change to shipped files needs an entry under ## [Unreleased].

    scripts/check-changelog.py [BASE]     BASE defaults to origin/main (else main)

Compares BASE...HEAD plus uncommitted changes. Exempt: top-level *.md, docs/, CHANGELOG.md.
Fails when shipped files changed and either CHANGELOG.md was not touched or its
[Unreleased] section is empty. Exit 0 ok, 1 entry missing, 2 usage or git error.
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args], check=True, capture_output=True, text=True).stdout


def exempt(path: str) -> bool:
    return path == "CHANGELOG.md" or ("/" not in path and path.endswith(".md")) or path.startswith("docs/")


def unreleased_has_entries() -> bool:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    m = re.search(r"^## \[Unreleased\]\s*$(.*?)(?=^## \[)", text, re.M | re.S)
    return bool(m and re.search(r"^\s*- \S", m.group(1), re.M))


def main() -> int:
    base = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        if base is None:
            for candidate in ("origin/main", "main"):
                if subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--verify", "-q", candidate],
                                  capture_output=True).returncode == 0:
                    base = candidate
                    break
        if base is None:
            print("check-changelog: no base branch (origin/main or main); skipped")
            return 0
        changed = set(git("diff", "--name-only", f"{base}...HEAD").split())
        changed |= set(git("diff", "--name-only", "HEAD").split())
        changed |= set(git("ls-files", "--others", "--exclude-standard").split())
    except subprocess.CalledProcessError as exc:
        print(f"check-changelog: git failed: {exc.stderr.strip()}")
        return 2
    shipped = sorted(p for p in changed if not exempt(p))
    if not shipped:
        print("check-changelog: no shipped files changed")
        return 0
    if "CHANGELOG.md" in changed and unreleased_has_entries():
        print(f"check-changelog: ok ({len(shipped)} shipped file(s), [Unreleased] has entries)")
        return 0
    print(f"check-changelog: {len(shipped)} shipped file(s) changed since {base} without a CHANGELOG.md "
          "entry under ## [Unreleased]:")
    for p in shipped[:15]:
        print(f"  {p}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
