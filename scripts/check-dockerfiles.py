#!/usr/bin/env python3
"""Container contract for every containers/<service>/Dockerfile (run by test.sh).

Rules (CLAUDE.md "Containers"):
  1. every FROM names a tag AND an index digest (tag@sha256:...)
  2. the final stage switches to a non-root USER (a name or uid other than root/0)
  3. a HEALTHCHECK is declared (CMD form)
  4. no curl or wget is installed (runtime images ship no download tools)
  5. Python images install with --only-binary=:all: (wheels only, so arm64 builds never
     compile) and remove pip afterwards
  6. the build context is the repo root: COPY sources start with containers/<svc>/,
     farglow, migrations or VERSION
  7. every service directory has a Dockerfile and is wired into compose.yaml
Exit 0 ok, 1 violations.
"""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FROM_RE = re.compile(r"^FROM\s+(?:--platform=\S+\s+)?(\S+)", re.I | re.M)
PINNED = re.compile(r"^[\w./-]+:[\w.-]+@sha256:[0-9a-f]{64}$")


def logical_lines(text: str) -> list[str]:
    return re.sub(r"\\\n", " ", text).splitlines()


def check(svc_dir: Path, compose: str) -> list[str]:
    svc = svc_dir.name
    df = svc_dir / "Dockerfile"
    if not df.is_file():
        return [f"{svc}: no Dockerfile"]
    text = df.read_text(encoding="utf-8")
    lines = [ln.strip() for ln in logical_lines(text) if ln.strip() and not ln.strip().startswith("#")]
    errs = []
    for image in FROM_RE.findall(text):
        if not PINNED.match(image):
            errs.append(f"{svc}: FROM {image} is not pinned as tag@sha256:digest")
    users = [ln.split(None, 1)[1].strip() for ln in lines if ln.upper().startswith("USER ")]
    if not users or users[-1] in ("root", "0", "0:0"):
        errs.append(f"{svc}: the final USER must be non-root")
    if not any(ln.upper().startswith("HEALTHCHECK") and " CMD " in f" {ln} " for ln in lines):
        errs.append(f"{svc}: no HEALTHCHECK ... CMD")
    for ln in lines:
        if ln.upper().startswith("RUN") and re.search(r"(apt-get|apk|apt)\s+(install|add)\b.*\b(curl|wget)\b", ln):
            errs.append(f"{svc}: installs curl/wget: {ln[:80]}")
        if ln.upper().startswith("RUN") and "pip install" in ln:
            if "--only-binary=:all:" not in ln:
                errs.append(f"{svc}: pip install without --only-binary=:all:")
            if "pip uninstall -y pip" not in ln:
                errs.append(f"{svc}: pip is not removed from the runtime image")
        if ln.upper().startswith(("COPY ", "ADD ")):
            parts = [p for p in ln.split()[1:] if not p.startswith("--")]
            for src in parts[:-1]:
                if not (src.startswith(f"containers/{svc}/") or src in ("VERSION", "farglow", "migrations")
                        or src.startswith(("farglow/", "migrations/"))):
                    errs.append(f"{svc}: COPY source {src} is outside the allowed paths")
    if not re.search(rf"^  {re.escape(svc)}:\s*$", compose, re.M):
        errs.append(f"{svc}: not a service in compose.yaml")
    elif f"/farglow-{svc}:" not in compose:
        errs.append(f"{svc}: compose.yaml does not use image farglow-{svc}")
    return errs


def main() -> int:
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    errs = []
    dirs = sorted(p for p in (ROOT / "containers").iterdir() if p.is_dir())
    for d in dirs:
        errs += check(d, compose)
    for e in errs:
        print(f"check-dockerfiles: {e}")
    print(f"check-dockerfiles: {len(dirs)} services, {len(errs)} problem(s)")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
