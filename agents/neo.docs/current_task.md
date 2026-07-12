# Current Task

**Status:** `*swe fix judge session` (revised) done — 3 script bugs fixed in `agents/tools/trace_annotate.py`, verified. Sprint 2 implementation (all 3 phases) also done, same day.
**Assigned to:** N/A (no active task)
**Started:** 2026-07-10
**Completed:** 2026-07-10

## Task Description (most recent): `*swe fix judge session` (revised)
Fix the 2 script bugs Smith filed against `agents/tools/trace_annotate.py` after the real `make judge-trace` tool was wired up for the first time (previously orphaned).

## Progress
- [x] Fixed `AP-MAKE-PIPE` false-positiving on `make chat` — regex now checks the piped `make` invocation's target against `MKF_EXCLUDED_TARGETS` (chat/help/install_bob/update_bob/pull_bob/clean_bob aren't mkf-captured, so there's no `build/build.out` for them to tail instead)
- [x] Fixed `AP-DUP-READ` being offset-blind — now keyed on `(path, offset, limit, edit_generation)` so re-reading different sections of a large file, or re-reading after a real edit, no longer counts as a duplicate
- [x] Found and fixed a 3rd latent bug while in there (not filed as a separate ticket, zero real instances today): `AP-SKILL-RELOAD` never checked `trace_rules.json`'s own `multi_call_allowed` exemption list (bloop/chat/personas)
- [x] Verified via Trin's rerun on the same JSONL data: `AP-MAKE-PIPE` 104→53, `AP-DUP-READ` 12→0, no regressions in the real flags that remained
- [x] `make test`: still green (change is confined to `agents/tools/`, doesn't touch `src/scalene`)

## Task Description (prior): Sprint 2 Phase 3 focus-loss fix
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
