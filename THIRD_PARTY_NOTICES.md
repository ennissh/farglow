# Third-party notices

Farglow is © 2026 Citus Technologies, LLC under the Business Source License 1.1 (see `LICENSE.md`). The components below keep their own licenses. Check this list against the pins before every release (RELEASE.md, step 1).

## Bundled in the repository

| Component | Version | License | Where | Use |
|---|---|---|---|---|
| Inter Tight (font, latin 400–700) | Fontsource 5.3.0 | SIL Open Font License 1.1 | `farglow/web/static/fonts/` (license text: `OFL-InterTight.txt`) | All reading text |
| IBM Plex Mono (font, latin 400–500) | Fontsource 5.3.0 | SIL Open Font License 1.1 | `farglow/web/static/fonts/` (license text: `OFL-IBMPlexMono.txt`) | Numbers, timestamps, kickers |
| htmx | 2.0.4 | Zero-Clause BSD | `farglow/web/static/vendor/htmx/` | Page partials |

The fonts are served from the Farglow server itself (no Google Fonts requests), unmodified. Under the OFL they may be bundled and redistributed with software; they may not be sold on their own.

## Installed into the images (Python, exact pins)

| Package | Version | License |
|---|---|---|
| Flask | 3.1.3 | BSD-3-Clause |
| Werkzeug | 3.1.9 | BSD-3-Clause |
| Jinja2 | 3.1.6 | BSD-3-Clause |
| MarkupSafe | 3.0.4 | BSD-3-Clause |
| itsdangerous | 2.2.0 | BSD-3-Clause |
| click | 8.5.0 | BSD-3-Clause |
| blinker | 1.9.0 | MIT |
| gunicorn | 26.2.0 | MIT |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| psycopg, psycopg-binary | 3.3.7 | LGPL-3.0-only (used unmodified, as a dynamically loaded library) |
| PyYAML | 6.0.3 | MIT |

Test-only (not shipped): pytest 9.2.0 (MIT), pluggy 1.7.0 (MIT), iniconfig 2.3.1 (MIT), Pygments 2.21.0 (BSD-2-Clause), shellcheck-py 0.11.0.1 (MIT wrapper; ShellCheck is GPL-3.0, run as a separate tool), gitleaks 8.28.0 (MIT, downloaded at test time).

## Base images

| Image | Pinned digest in | License of the software |
|---|---|---|
| `python:3.13-slim` (Debian) | `containers/{api,tick,worker,mailer,migrate,llm-gateway}/Dockerfile` | Python Software Foundation License; Debian packages under their own licenses |
| `postgres:16-bookworm` | `containers/{db,backup}/Dockerfile` | PostgreSQL License |
| `nginxinc/nginx-unprivileged:1.29-alpine` | `containers/nginx/Dockerfile` | BSD-2-Clause (nginx); Alpine packages under their own licenses |

## Note for legal review
psycopg is LGPL-3.0. Shipping it unmodified inside a container image is normally compatible with a source-available product, but this should be confirmed in the license review that PLAN.md already lists.
