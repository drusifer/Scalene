# Agent State

Keep this working-memory file current. Preserve exactly these three top-level sections; see the
State Management Protocol in `agents/skills/bob-protocol/SKILL.md` for entry and exit steps.

## Context
- **Recent decisions:** Fixed Smith's pre-PyPI review findings: implemented `-h`/`--help` on top-level `scg` (`src/scalene/main_cli.py`, exits 0 with subcommand descriptions; unknown/empty still exits 2), quoted `"scalene-guard[monitor]"` in `src/scalene/monitor.py`'s ImportError hint for zsh compatibility, added tests (`test_cli.py`, `test_monitor_cli.py`, `test_user_guide_docs.py`), re-enabled `scg --help` in `Makefile` `check-dist`, and applied all P0/P1 user-doc fixes across `README.md`, `docs/GETTING_STARTED.md`, `docs/SETUP.md`, `docs/USER_GUIDE.md`, and `docs/MONITOR_GUIDE.md`.
- **Key findings:** `tests/test_user_guide_docs.py` checked `--help` flags for `scalene-guard`, `scg onboard`, and `scg install-hooks`, but previously missed `scg monitor`; added `test_monitor_flags_match_real_help_output` to prevent future drift.
- **Important notes:** All targeted tests (`test_cli` 20/20, `test_monitor_cli` 3/3, `test_getting_started_docs` 4/4, `test_user_guide_docs` 10/10), `make build`, `make check-dist`, and `make secrets` passed cleanly.

## Current Task
- **Status:** Complete
- **Assigned to:** Neo
- **Started:** 2026-11-21
- **Description:** Apply Smith's P0/P1 pre-PyPI doc fixes and fix `scg --help` exiting 2 + zsh-safe `[monitor]` hint.
- **Progress:** Code, tests, and all 5 user docs updated and verified; handed to Smith for re-verification.
- **Blockers:** None
- **Consultations:** Smith (`agents/smith/pypi_docs_review.md`).

## Next Steps
- **Immediate next action:** Await user confirmation to commit, push, and cut `v0.1.0` release.
- **Waiting on:** User.
- **Planned work:** None.

---
*Last updated: 2026-11-21*
