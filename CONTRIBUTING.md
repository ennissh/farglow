# Contributing to Farglow

Farglow is **not open to outside contributions yet**.

When it opens, **a Contributor License Agreement (CLA) will be required** before any contribution can be merged. The CLA lets Citus Technologies, LLC offer commercial licenses for Farglow and relicense each version under Apache 2.0 on its Change Date, as `LICENSE.md` describes. *The CLA's wording is to be written by a lawyer; until it exists, no outside contribution can be accepted.*

Farglow is source-available under the Business Source License 1.1, not OSI open source. Please don't describe it as open source.

## For the core team

- Read `CLAUDE.md` (conventions) and `TESTING.md`.
- Work on a branch, in small commits with clear messages, and open one PR per item.
- Every change to shipped files needs a `CHANGELOG.md` entry under `## [Unreleased]`.
- `./test.sh` must pass before you push. It also runs gitleaks: never commit secrets.
- New decisions go in `docs/specs/decisions-*.md`. Open items go in PLAN.md's open-items table.
- Choices made to fill a gap in the spec are marked **Proposal** in the PR description, so the owner can confirm them.
