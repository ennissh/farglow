# Changelog

All notable changes to Farglow are recorded here. The format follows
[Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html).

**Rule:** every change to shipped code adds an entry under `## [Unreleased]` *before it is
pushed*. `./test.sh` runs `scripts/check-changelog.py` against `origin/main` and fails when
shipped files changed but this file did not. Top-level `*.md` files and `docs/` are exempt.
A release moves `[Unreleased]` into a dated `## [X.Y.Z] - YYYY-MM-DD` section and bumps `VERSION`.

Categories: Added, Changed, Deprecated, Removed, Fixed, Security.

## [Unreleased]

### Added
- **Design pack unpacked into the repository layout.** Game configs to `config/*.poc.yaml`;
  `tools/sim.py`, `tools/techtree/` and `tools/art/`; mockups, explorations, brand and the
  design-system docs to `docs/design/`; tokens, `bundle.css` and SVG assets to
  `farglow/web/static/ds/`; the art library to `farglow/web/static/art/farglow-art.js`
  (one copy; `tools/art/farglow-art.js` is a shim so the build scripts still load it).
  Every file was checked by SHA-256 against the uploaded pack.

## [0.0.0] - 2026-11-04

### Added
- Repository created with `README.md`, `PLAN.md`, `LICENSE.md` (draft BUSL 1.1) and the design pack.
