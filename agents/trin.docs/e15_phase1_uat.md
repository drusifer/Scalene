# Trin — `*qa uat phase-1` — Sprint 9 (E15) — 2026-07-21

## Checked against artifacts first
`task.md` Sprint 9 Phase 1 exit criteria: "a config-declared test-only scanner class actually loads and dispatches through identify()/scan(); omitting scanners: reproduces today's exact behavior; a bad import: path and a name-collision both fail loud naming the offending value." `docs/ARCHITECTURE.md` §18.1 for the real design.

## What I verified independently (not just re-running Neo's own tests)
Neo's tests (`TestLoadScanners`, `TestPolicyConfigScanners`) cover the library level correctly. The actual STORY-1501 AC is about the **registry being traversed**, which for `scg onboard` means the real CLI entry point (`main()`), not just `load_scanners()`/`PolicyConfig` in isolation — so I added 3 new tests in `tests/test_onboard.py::TestCustomScannerCLI` exercising `main()` directly with a real `scalene_policy.yaml` declaring a config scanner:
- `main()` identifies and onboards a target through a config-declared scanner end-to-end (`--call`/`--yes`/`--mode allow`), confirmed via real stdout ("1 onboarded, 0 blocked", `dummy:widget-1`).
- `scg onboard --list` shows the config-declared scanner's onboarded entry after the fact.
- **Adversarial**: a typo'd `--scanner` name, checked against the *full* loaded registry (builtins + config-declared), still fails loud via the real CLI (`0 onboarded, 1 blocked`) — this specifically re-checks Neo's own flagged regression-and-fix (the legacy `onboard()`/`_onboard_resource()` path losing then regaining its scanner-name validation) at the CLI level, not just the unit level Neo already covered.

## Verified Neo's two self-reported findings independently
1. **Regression fix**: confirmed `_onboard_resource()` now validates `scanner` against its `registry` param before constructing `PolicyRule` — read the code, not just the diff description; confirmed `tests/test_onboard.py::test_invalid_rule_fields_reuse_policyrule_validation` (pre-existing, unmodified) passes again.
2. **Diagram revert**: confirmed `docs/ARCHITECTURE.md` §4 no longer references `ReputationChecker`/`LocalHeuristicChecker`/`URLHausChecker`/`ReputationResult` — `tests/test_architecture_docs.py` passes.

## Scope decision I agree with
`cache_refresh_worker.py` staying on the module-level `SCANNERS` (documented in-code) is the right call — real subprocess-argv plumbing for a scanner type that doesn't exist yet would be speculative, and the failure mode if it ever matters is bounded (a no-op background refresh, not silent wrong data — the next lookup still retries via the normal fail-safe path).

## Regression check
Full suite, not scoped: `make test` — **352/352** (349 after Neo's Phase 1 + my 3 new CLI-level tests).

## `make judge-trace` note
Not run this session — no interactive CLI surface introduced in Phase 1 to be worth a targeted trace check yet (Smith's mandatory gate for that lands on Phase 4). Will run it as part of that gate's UAT instead.

## Verdict

**PASSED.** No regressions, no code smells (registry-loading logic is small, single-purpose, fails loud with specific messages). Handing to Morpheus for code review.
