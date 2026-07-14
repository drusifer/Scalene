# Smith — Sprint 3 Gate 2 Review (E9 architecture, §12)

**Date:** 2026-07-14
**Verdict:** APPROVED, one non-blocking note.

## Review

- No new interactive surface, no flag/output-format changes to existing commands, no breaking changes — low UX risk by construction.
- The "real subprocess, real hook JSON, no mocking" decision for the demo is the right call from a trust standpoint too: a demo built on internal function calls or fabricated JSON could show something that doesn't match what a user actually experiences (Nielsen #2, match between system and real world) — real prospective users will (rightly) distrust a demo that's revealed to be staged.
- `make demo` matches existing target naming conventions (`make test`, `make setup`).
- Testing the demo via `tests/test_demo.py` so it can't rot silently is good — an untested demo is worse than no demo (a stale one actively misleads).

## Non-blocking note

The target audience for the demo per STORY-903 is "a prospective user or reviewer" — someone who may not have read the BRD/PRD and doesn't know what "taint" or "Triangle-of-Doom" mean yet. §12.1's narration requirement ("plain-language narration... what happened and why") should be written for that reader specifically: e.g. instead of "has_sensitive_data flag set," say something like "Scalene noticed this session touched sensitive data." Flagging so whoever implements Phase 3 doesn't default to internal terminology just because it's what the code calls things (Nielsen #2 again).

## Gate Decision

Approved. Proceeding to Mouse for phase breakdown.
