# Bug 2026-07-10-003: `make test 2>&1 | tail -N` used habitually despite an explicit written rule

**Severity**: P3 — Token/output waste at real scale, not a one-off lapse
**Filed by**: Smith
**Route to**: Bob (prompt reinforcement, not documentation — the text is already correct)

---

## Reproduction

`agents/trin.docs/judge_20260710_trace.md`, `AP-MAKE-PIPE` breakdown: ~39 of ~45 `make test` invocations during Sprint 2 implementation were piped through `tail`.

## Expected

`agents/neo.docs/SKILL.md` line 145, verbatim: `NEVER: make test 2>&1 | tail -30 → use make test-q (built-in concise output)`. This is not ambiguous and not missing.

## Actual

The documented anti-pattern was the majority behavior for test runs this entire sprint, not an isolated slip (contrast with bug S1-001 from the 2026-07-08/09 loop, which was a single instance).

## Root Cause

Unlike S1-001 (single lapse, plausibly a genuine one-off), this is systemic — the rule exists and is precise, but isn't being consulted or recalled at the actual moment of running tests, across dozens of repetitions. Restating the rule again in prose is unlikely to change behavior that already had the correct prose in scope every time.

## Recommended Fix

Something with more teeth than another SKILL.md sentence: consider whether `make test`'s own output could nudge toward `test-q` (e.g., if invoked with a trailing pipe detected via shell wrapper, emit a one-line hint), or whether Trin's UAT pass should include a quick self-check of the session's own tool-call hygiene before signing off a phase — turning this from a purely aspirational rule into one with a checkpoint. Flagging for Bob's judgment on mechanism; the underlying rule text itself does not need to change.
