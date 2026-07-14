# Current Task

**Status:** NOT STARTED — Sprint 4 Phase 1 (Scanner Protocol & Built-in Scanners) just handed to me by Morpheus. This is the actual next task on cold start.
**Assigned to:** Neo
**Started:** (not yet)

## Task Description (next, unstarted): `*swe impl phase-1` (Sprint 4, STORY-1001/1002)
Build `Scanner` protocol (`identify()`/`scan()`), `Resource`/`ScanResult` dataclasses, `FileScanner` (wraps existing `secrets_scan.py`), `URLScanner` (wraps existing `reputation.py`'s `LocalHeuristicChecker`), both with named-capture-based generic fallback detection, plus wiring `Bash`'s `command` string into both scanners' fallback (no dedicated Bash scanner type). Full spec: `docs/ARCHITECTURE.md` §13.2, task breakdown in `task.md` Sprint 4 Phase 1. No Smith gate on this phase (internal, no user-facing surface yet). Exit criteria: Trin UAT (both scanners at parity with today's secrets-scan/reputation-check, no regression), Morpheus review.

**Known gap to be aware of, not part of this task:** Sprint 3 Phase 3 (the demo) was implemented and handed to Trin for UAT below, but Trin's UAT was never actually completed before this session moved into unrelated direct-request work (pip packaging, then the masking/hook-schema bug fixes that became Sprint 4). Sprint 3 was never formally closed (no retro, no `*pm launch`). This doesn't block Sprint 4 — different subsystem entirely — but flag it if anyone asks "is Sprint 3 done."

## Task Description (prior, historical): `*swe impl phase-3` (Sprint 3, STORY-903): `demo/run_demo.py`

## Progress
- [x] `demo/run_demo.py`: real subprocess calls to the installed `scalene-guard` binary (located via `Path(sys.executable).parent`, same interpreter's venv), no policy file (out-of-the-box defaults, matches Phase 1's finding), scenario = Read(fake secret) → PostToolUse → WebFetch(untrusted) → masked. Narration written for a BRD-naive reader per Smith's Gate 2 note (no "taint"/"Triangle-of-Doom" jargon)
- [x] Added `make demo` as a **bypass target** (else-block only, like `help`/`chat`) per the make-discover skill convention — a normal mkf-wrapped target would silently capture the narration instead of showing it, defeating the whole point of a demo
- [x] Caught a real Makefile gotcha before it shipped: `make demo` initially did nothing (`'demo' is up to date`) because the `demo/` directory shares its name with the target and make treated it as a file — fixed by adding `demo` to the `else` block's `.PHONY` list
- [x] Ran `make demo` once directly (the actual deliverable, not a throwaway verification script) to confirm the narration reads correctly
- [x] `tests/test_demo.py`: runs the demo as a subprocess (same as `make demo` would), asserts the mask marker appears, the fake secret never appears unmasked after "Step 3", and the suggested onboard command is shown
- [x] `make test`: 140/140 passing (137 + 3 new)

## Task Description (prior): `*swe impl phase-2` (Sprint 3, STORY-902): `docs/USER_GUIDE.md`

## Progress
- [x] Wrote `docs/USER_GUIDE.md`: all 4 commands (`scalene-guard`, `scalene onboard`, `scalene install-hooks`, `scalene monitor`) documented against real `--help` output; policy schema by example cross-referencing `ARCHITECTURE.md` §4 and `BRD.md` §2.3.2 rather than duplicating; onboard-suggestion workflow presented as the primary path (Smith's Gate 1 note) with manual flags as fallback; troubleshooting table
- [x] **Found and fixed a real, pre-existing bug** while writing the troubleshooting section: `cli.py`'s `main()` called `PolicyConfig.from_yaml()` with no exception handling — a malformed `scalene_policy.yaml` crashed `scalene-guard` with an uncaught `PolicyConfigError`, violating the module's own documented fail-safe guarantee. Fixed by catching `PolicyConfigError` and falling back to `PolicyConfig()` defaults (same as a missing file), with a warning logged. Added `test_malformed_policy_yaml_fails_safe_and_allows` (`tests/test_cli.py`) as the regression test — did not verify this via a manual bash repro, wrote it as a real test per user correction this session
- [x] Added `tests/test_user_guide_docs.py`: existence/term checks + **actually invokes** `scalene-guard --help`/`scalene onboard --help`/`scalene install-hooks --help` via the real `main()` functions and asserts every flag mentioned in the guide is present in real output — not just prose matching
- [x] README updated: `USER_GUIDE.md` added to doc table
- [x] `make test`: 137/137 passing (129 + 8 new)

## Task Description (prior): `*swe fix phase-1 doc-drift test`
Morpheus rejected Phase 1 round 1: `tests/test_getting_started_docs.py` only checked term-presence in prose, never actually ran the scenario, so `docs/GETTING_STARTED.md`'s literal mask output could go stale silently (same drift class as Sprint 2's 2 AC-text incidents).

## Progress (fix)
- [x] Added `test_walkthrough_scenario_actually_masks`: calls `pre_tool_use`/`post_tool_use` directly (same pattern as `tests/test_hook_adapter.py`), replays the doc's exact 3-call scenario, asserts `updatedInput["prompt"] == MaskingEngine.MASK_LITERAL`
- [x] Caught my own near-miss while writing it: `pre_tool_use`'s `audit_log_path` defaults to a *relative* `.scalene/audit.log` (cwd-relative, not `state_dir`-relative) — without explicitly overriding it, the test would have written into the real repo's cwd during `make test`. Passed `audit_log_path=state_dir/"audit.log"` explicitly, matching `test_hook_adapter.py`'s existing pattern.
- [x] `make test`: 128/128 passing (127 + 1 new)
- [x] Confirmed no stray `.scalene/audit.log` writes leaked into the repo root from the test

## Task Description (prior): `*swe impl phase-1` (Sprint 3, STORY-901): `docs/GETTING_STARTED.md`, README trim.

## Progress
- [x] Verified real `--help` output for `scalene`, `scalene onboard`, `scalene install-hooks`, `scalene-guard` before writing anything (did not transcribe from memory/source)
- [x] Read `hook_adapter.py`/`masking.py`/`policy_config.py`/`taint_state.py` to find a genuinely minimal repro: with **no policy file at all**, defaults (`sensitive_by_default`/`untrusted_by_default` both `True`) mean a `Read` then any outbound call (e.g. `WebFetch`) gets masked with zero config — this matches §12.1's "matches the fail-safe defaults new users actually hit first" intent exactly
- [x] Actually ran the 3-command sequence in a scratch dir against the real installed `scalene-guard` before writing it into the doc — confirmed real masked output, real `systemMessage`, real `.scalene/audit.log` entry (not assumed/fabricated)
- [x] Wrote `docs/GETTING_STARTED.md`: clone → `make setup` → 3 copy-pasteable `scalene-guard` invocations → observed mask event → links to SETUP.md/USER_GUIDE.md/demo
- [x] Trimmed `README.md`'s "Getting started" section to link to the new doc (kept `make setup`/`make test` since that's the repo-contributor flow, not a duplicate of the demo walkthrough); added GETTING_STARTED.md to the doc table
- [x] Added `tests/test_getting_started_docs.py` (existence + key-term checks, same pattern as existing `test_setup_docs.py`) — confirms README links rather than duplicates
- [x] `make test`: 127/127 passing (124 + 3 new)

## Blockers
None.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-14*
