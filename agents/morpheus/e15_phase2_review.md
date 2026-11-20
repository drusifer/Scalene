# Morpheus — `*lead review phase-2` — Sprint 9 (E15) — 2026-07-21

## Architecture fit
`_is_hardcoded_restricted()`'s boundary check (`identity == prefix or identity.startswith(prefix.rstrip("/") + os.sep)`) is correct and I confirmed it against the false-positive case myself (`/etcetera/file` vs. `/etc`) — this is exactly the kind of naive-string-matching bug that would have shipped silently if written as a plain `str.startswith(prefix)`. Good that Neo tested it explicitly rather than trusting the obvious-looking one-liner.

## The design correction
Independently re-traced `decide_access()` (I wrote §15.3 originally, so I know its control flow well) — Neo's finding is right: `is_bad` is checked unconditionally before any rule match, so the originally-planned `resource_verifier.py` implicit-rule addition would never execute. This is a case where writing the architecture doc ahead of implementation missed a real detail about the *existing* code's control flow, not a new gap introduced by this epic. Good catch, correctly resolved by simplifying rather than forcing the original (wrong) plan into working code.

## Scope
Correctly narrow: no public cross-module helper where only one consumer exists (YAGNI, matches this project's own stated engineering values). No changes outside `scanner.py`.

## Verdict

**APPROVED.** Handing Phase 3 to Neo.
