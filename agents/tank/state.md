# Agent State

Keep this working-memory file current. Preserve exactly these three top-level sections; see the
State Management Protocol in `agents/skills/bob-protocol/SKILL.md` for entry and exit steps.

## Context
- **Recent decisions:** Prepped `scalene-guard` (`0.1.0`) for automated PyPI publishing via OIDC Trusted Publishing (`drew.gs.works` account): GitHub Release (`published`) triggers `.github/workflows/publish.yml`, which calls `.github/workflows/ci.yml` (`test` 3.13 & 3.15 matrix, `package` on 3.13, `secrets`), verifies `make release-check`, builds `dist/`, and publishes via `pypa/gh-action-pypi-publish` in the `pypi` environment. Raised `requires-python` to `>=3.13` (per user direction, matching local system Python 3.13 and testing latest CPython 3.15 in CI). All GitHub Actions are pinned to full commit SHAs with weekly `.github/dependabot.yml` updates.
- **Key findings:**
  - PEP 639 (`license = "MIT"` + `license-files = ["LICENSE"]`) requires `setuptools>=77`.
  - Unused runtime dependency `jsonpath-ng>=1.6` dropped cleanly; 635/635 unit tests pass from a clean `.venv`.
  - `MANIFEST.in` keeps sdist clean (65 entries; no `.scalene/`, `agents/`, or `.venv/`).
  - `scg --help` exits with code 2 (no top-level help flag in `src/scalene/main_cli.py`); `make check-dist` smoke-tests subcommand `--help` and real `scalene-guard` stdin/stdout instead.
- **Important notes:**
  - `docs/SDLC.md` created and verified from clean (`make distclean && make setup && make build && make check-dist && make release-check TAG=v0.1.0 && make secrets && make test-q`).
  - One-time manual setup required on PyPI (`drew.gs.works` Pending Publisher: `scalene-guard` / `drusifer` / `Scalene` / `publish.yml` / `pypi`) and GitHub (`pypi` environment with required reviewer).

## Current Task
- **Status:** Complete
- **Assigned to:** Tank
- **Started:** 2026-11-21
- **Description:** Prep Scalene (`scalene-guard`) for PyPI publishing via `drew.gs.works` OIDC Trusted Publishing and establish `docs/SDLC.md`.
- **Progress:** All packaging, CI/release workflows, Makefile targets, README PyPI fixes, and `docs/SDLC.md` implemented and verified from clean (635/635 tests pass). Handed off to Smith for user-oriented documentation review.
- **Blockers:** None
- **Consultations:** Handed off to `@Smith *user review docs`.

## Next Steps
- **Immediate next action:** Await Smith's user-oriented doc review; apply any Tank-owned doc/packaging adjustments if flagged.
- **Waiting on:** Smith (`*user review docs`) and user approval to commit/push and configure PyPI Pending Publisher + GitHub `pypi` environment.
- **Planned work:** None.

---
*Last updated: 2026-11-21*
