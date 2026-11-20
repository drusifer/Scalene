# Smith — `*user test phase-4` — Sprint 9 (E15), mandatory gate — 2026-07-21

## What I ran
Same as Trin's UAT, re-run myself rather than trusting her transcript — actually ran `python -m scalene.onboard --list` cold in a fresh scratch directory (no cache, no policy file), and read the `--help` output the way a real user would.

```
$ python -m scalene.onboard --list --cache-path ./cache.json --policy-path ./scalene_policy.yaml
implicit default: /tmp/e15_smith_check -> sensitivity=internal, trust=trusted (project-folder default, docs/ARCHITECTURE.md sec18.4)
No onboarded targets in the scan cache.
```

## My Gate 1 hard requirement (discoverability)
**Satisfied.** The line appears unprompted on the exact command `--list` already trained developers to check (STORY-1404), whether or not any real entries exist yet. This is the shape I approved at Gate 2.

## New finding — real, not cosmetic: `trust=trusted` is inaccurate and uses a vocabulary that doesn't exist anywhere else in this project

**HEURISTIC: #4 Consistency and Standards / #2 Match Between System and Real World**
**SURFACE:** `scg onboard --list`'s synthetic default line (`onboard.py::_list_inventory`)
**EXPECTED:** The line should describe the real, actual effect on session state, using this project's own established vocabulary (`taint.trust` is one of `"low"`/`"med"`/`"high"` — confirmed in `taint_state.py:25`, `TRUST_LEVELS`).
**ACTUAL:** The line says `trust=trusted` — a value that **cannot occur anywhere in this system**. Worse, I traced `decide_access()`'s actual code: a project-folder resource only ever escalates `taint.sensitivity` (`validated_allow`'s only mutation); `trust` is never touched for it at all. A session that only ever touches clean project files keeps whatever `trust` value it already had (`"high"` by default, unescalated) — it does not get set to some active "trusted" state. So this isn't just wrong vocabulary, it's describing a mechanism that doesn't exist: implying this default *actively grants* trust, when what it actually does is *never contaminate* trust in the first place (a real but different thing).
**IMPACT:** A developer who's seen `trust=low`/`trust=high` anywhere else in this project (monitor panel, block-reason messages) and then reads `trust=trusted` here has to wonder whether this is a typo, a different concept, or a real inconsistency. Worse: if they take the line at face value, they'd have a wrong mental model of what this default actually does to their session.

**Not blocking the *mechanism*** (the underlying behavior — sensitivity escalation, trust left alone — is correct and well-tested per Trin's/Neo's work) — **blocking the *line's wording*.** This is exactly the kind of "correct code, inaccurate/confusing display text" gap my gate exists to catch before it ships, same shape as sec16's `--help` finding.

## Verdict (initial)

**REJECTED, fix required before I approve.**

```
REASON: The --list synthetic default line claims "trust=trusted", a value that doesn't exist in this project's real trust vocabulary (low/med/high) and doesn't match what the mechanism actually does (it only ever escalates sensitivity to "internal"; trust is never touched).
FIX: Reword the line to describe what actually happens -- e.g. "implicit default: <root> -> sensitivity=internal (project files don't escalate trust)" or similar, using real vocabulary only. Re-run `--list` for real after the fix, don't just re-read the diff.
```

## Re-test (2026-07-21, after Neo's fix)

Ran the real CLI myself again, fresh scratch directory, not just re-reading the diff:

```
$ python -m scalene.onboard --list --cache-path ./cache.json --policy-path ./scalene_policy.yaml
implicit default: /tmp/e15_smith_recheck2 -> sensitivity=internal (clean project files are allowed without escalating trust; project-folder default, docs/ARCHITECTURE.md sec18.4)
No onboarded targets in the scan cache.
exit=0
```

Reads clearly, states the real mechanism accurately (no invented vocabulary), still satisfies discoverability without becoming so hedged it stops being a clear one-line summary. My Gate 1 hard requirement remains satisfied, and the accuracy problem is closed.

## Final Verdict

**APPROVED.** Handing to Morpheus for the Phase 4 code review.
