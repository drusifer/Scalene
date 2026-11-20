# Morpheus — `*lead review phase-4` (corrected mechanism) — Sprint 9 (E15) — 2026-07-21

## Why this needed a fresh review, not reuse of the earlier approval
The user asked for a real design change after Phase 4 was already fully gated: a real on-disk rule instead of an implicit in-memory one. That's a different implementation, not a refinement of the one I already approved — reviewing it fresh.

## Architecture fit
`write_default_project_policy()` is exactly the right shape: one function, writes exactly the same YAML structure a hand-authored rule would have, no new `PolicyConfig` field, no `__post_init__` special-casing. `cli.py`'s integration is minimal and correctly scoped (only fires when the file doesn't exist, fails safe on `OSError`, falls through to the *same* `from_yaml()` call every other case already uses).

## The shadowing fix
This is the one piece of real engineering judgment in this correction, and I traced it myself rather than trusting the description: `_find_matching_rule()` genuinely does return the first declaration-order match (confirmed by re-reading `resource_verifier.py` directly), and the default rule's pattern genuinely is broad enough to match virtually anything under the project root. Without the fix, a real, plausible sequence (default auto-created, then a developer explicitly `--mode block`s one sensitive file within their own project) would silently and permanently fail to take effect — a real correctness bug, not a hypothetical. The fix (insert new rules before the auto-created default specifically, identified by a shared constant, leaving all other rule-writes' append behavior untouched) is minimal and correctly scoped — it doesn't change ordering semantics for any case that doesn't involve this specific default rule.

## Test coverage
Reviewed Trin's multi-onboard regression test and the real subprocess e2e test — both exercise genuine behavior (real file writes, real rule ordering, a real spawned binary), not shortcuts.

## Verdict

**APPROVED.** Sprint 9 (E15) is fully implemented, gated, and — for Phase 4 specifically — gated twice, correctly, against two genuinely different implementations. Handing to Oracle for the groom pass.
