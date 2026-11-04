#!/usr/bin/env python3
"""Print the tags of one image on GHCR, one per line (stdlib only; used by build.sh).

    scripts/ghcr-tags.py ghcr.io/ennissh farglow-api

Credentials: GHCR_USER + GHCR_TOKEN from the environment, else the ones `docker login ghcr.io`
saved in ~/.docker/config.json (plain "auths" entries; a desktop credential helper isn't
read), else anonymous (public packages). Credentials never go on a command line.
Behind a TLS-intercepting proxy, FARGLOW_BUILD_CA_FILE is trusted too.

Exit 0 with the tags (none if the image was never pushed), 3 if GHCR can't be read
(no network, or credentials missing or refused).
"""
from __future__ import annotations

import base64
import json
import os
import ssl
import sys
import urllib.error
import urllib.request
from pathlib import Path


def credentials(host: str) -> tuple[str, str] | None:
    user, token = os.environ.get("GHCR_USER"), os.environ.get("GHCR_TOKEN")
    if user and token:
        return user, token
    cfg = Path(os.environ.get("DOCKER_CONFIG", Path.home() / ".docker")) / "config.json"
    try:
        auths = json.loads(cfg.read_text()).get("auths", {})
    except (OSError, ValueError):
        return None
    for name, entry in auths.items():
        if name.rstrip("/").split("//")[-1] == host and entry.get("auth"):
            user, _, token = base64.b64decode(entry["auth"]).decode().partition(":")
            return user, token
    return None


def context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    extra = os.environ.get("FARGLOW_BUILD_CA_FILE")
    if extra and Path(extra).is_file():
        ctx.load_verify_locations(extra)
    return ctx


def get(url: str, headers: dict) -> dict:
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=20, context=context()) as resp:  # noqa: S310 - fixed host
        return json.loads(resp.read())


def main(argv: list[str]) -> int:
    if len(argv) != 2 or not argv[0].startswith("ghcr.io/"):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    host, owner = "ghcr.io", argv[0].split("/", 1)[1].rstrip("/")
    repo = f"{owner}/{argv[1]}"
    headers = {}
    creds = credentials(host)
    if creds:
        headers["Authorization"] = "Basic " + base64.b64encode(f"{creds[0]}:{creds[1]}".encode()).decode()
    try:
        token = get(f"https://{host}/token?scope=repository:{repo}:pull&service={host}", headers).get("token", "")
    except urllib.error.HTTPError as exc:
        if creds:
            print(f"ghcr-tags: GHCR refused the credentials for {creds[0]} ({exc.code}): the token needs read:packages",
                  file=sys.stderr)
        else:
            print("ghcr-tags: no GHCR credentials (private packages): set GHCR_USER + GHCR_TOKEN, "
                  "or run `docker login ghcr.io` once", file=sys.stderr)
        return 3
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"ghcr-tags: can't reach GHCR: {exc}", file=sys.stderr)
        return 3
    try:
        out = get(f"https://{host}/v2/{repo}/tags/list?n=10000", {"Authorization": f"Bearer {token}"})
    except urllib.error.HTTPError as exc:
        if exc.code == 404:          # NAME_UNKNOWN: never pushed
            return 0
        print(f"ghcr-tags: can't list {repo} ({exc.code}); private packages need GHCR_USER/GHCR_TOKEN "
              "or `docker login ghcr.io`", file=sys.stderr)
        return 3
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"ghcr-tags: can't reach GHCR: {exc}", file=sys.stderr)
        return 3
    for tag in out.get("tags") or []:
        print(tag)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
