# Morpheus — `*lead review phase-1` — Sprint 9 (E15) — 2026-07-21

Reviewed the real diff (`scanner.py`, `policy_config.py`, `resource_verifier.py`, `onboard.py`, `cache_refresh_worker.py`) against §18.1, not just Neo's/Trin's summaries.

## Architecture fit
- `load_scanners()` is correctly scoped: builds from builtins, validates `extra:` entries against the `Scanner` protocol via `hasattr`, fails loud naming the offending value at every failure branch (missing field, bad import path, missing class, protocol violation, name collision). `ScannerRegistryError` avoiding a circular import back into `policy_config.py` is the right call — small, clean solution to a real constraint.
- `PolicyConfig.scanners`'s `field(default_factory=lambda: dict(SCANNERS))` is correct — a bare `PolicyConfig()` gets its own dict (not the shared module dict object), but the same singleton `FileScanner()`/`URLScanner()` instances, matching today's behavior exactly. No shared-mutable-default bug.
- The scanner-name-validation move (`PolicyRule.__post_init__` → `PolicyConfig.from_yaml`) is implemented exactly as designed: registry built first, each rule's `scanner` field checked against it before construction.
- `resource_verifier.py`'s change is minimal and correct — two one-line swaps (`SCANNERS` → `config.scanners`), no new parameters needed since `config` was already there.

## The two implementation-time findings
Both are real, both are correctly scoped, both are documented rather than silently absorbed:
1. **The `onboard()` legacy-path regression** — I independently traced it: `_onboard_resource()` builds a `PolicyRule` directly, bypassing `from_yaml`'s new validation loop entirely, so removing the check from `__post_init__` without a replacement here would have been a real, silent regression of E12/STORY-1201's original fix. The added check (`if scanner and scanner not in registry: raise OnboardError(...)`) closes it correctly, with a message matching the original's shape. Good catch, correctly fixed, not just noted and left.
2. **`cache_refresh_worker.py`'s scope decision** — agreed, and well-reasoned. Plumbing `policy_path` across a subprocess boundary for a scanner type that doesn't exist yet would be pure speculation. The documented failure mode (return 2, next lookup retries via the existing fail-safe path) is genuinely bounded, not a hidden correctness gap.

## Diagram-drift revert
Confirmed §4 no longer references not-yet-built classes. Correct call — I should have caught this myself when writing §18 (writing the whole epic's diagram in one architecture pass, ahead of phased implementation, is exactly the kind of gap the drift-guard test exists to catch). Noting for my own next architecture pass: only diagram *this phase's* classes when they're this close to being built next, not the whole epic's projected end-state, unless every phase is landing in the same sitting.

## Trin's added CLIlevel tests
Appropriate escalation — the AC is about the registry being *traversed*, and `onboard.py`'s `main()` is a real, separate traversal point from `resource_verifier.py`'s. Good that this wasn't left as "the library-level test implies the CLI works."

## Verdict

**APPROVED.** No architectural concerns, no code smells, no scope creep. Handing Phase 2 to Neo.
