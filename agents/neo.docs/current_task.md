# Current Task

**Status:** Fixed Smith's focus-loss bug. Trin and Smith both re-verified. Phase 3 complete. Sprint 2 implementation (all 3 phases) done.
**Assigned to:** N/A (implementation stage finished)
**Started:** 2026-07-10
**Completed:** 2026-07-10

## Task Description
`*swe fix phase-3 focus bug` — Smith found (real Pilot-driven execution) that dismissing or applying leaves the app with no focused widget at all, stranding the user.

## Progress
- [x] Test-first: added 2 Pilot tests, confirmed red, fixed via `_return_focus_to_events_table()` called from both `action_dismiss_edit()` and `on_input_submitted()`, confirmed green
- [x] Confirmed both tests meaningful (not tautological) by temporarily disabling the fix and watching them fail
- [x] Found and fixed a real, if rare, test-suite flake along the way (500ms poll timer racing with test teardown → `NoMatches` crash) — reproduced deterministically, fixed with a targeted `try/except NoMatches`, re-ran the full suite 4x to confirm it's gone
- [x] `make test`: 124/124 passing, stable across repeated runs

## Blockers
None.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-10*
