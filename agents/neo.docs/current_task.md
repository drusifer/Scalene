**Status:** DONE — post-E15-close correction: generic protocol detection + file:// routing. `make test`: 396/396.
**Assigned to:** Neo
**Started:** 2026-07-22
**Finished:** 2026-07-22

## Task Description (most recent): direct user session, post-E15-close — generic URL protocol detection, `file://` → FileScanner
User questioned STORY-1504's `scanner: secrets` filter, which surfaced a broader design gap: `URLScanner` only matched `http(s)://`, and no scanner recognized `file://` URIs at all. Broadened `_URL_FALLBACK_RE` to any URI scheme (`_URI_SCHEME` grammar), added `_FILE_URI_RE` to `FileScanner.identify()` so `file://` is recognized as a file resource regardless of which tool/field it appears in, and removed the now-redundant `scanner: secrets` filter from the auto-created project-folder rule (the anchored absolute-path pattern was already sufficient — general principle: don't require a rule author to remember scanner registry names).

**Real bug found while implementing, not assumed correct**: my first attempt excluded `file://` from `URLScanner`'s regex via a `(?!file://)` negative lookahead — wrong, because `re.finditer` retries one character later when a match fails at the current position, and `(?!file://)` trivially passes there, matching `"ile://..."` as a bogus scheme. Caught by a test that actually ran `file://` through `URLScanner.identify()`. Fixed by matching any scheme unconditionally and filtering `file://` out in Python code (`_is_file_uri()`), which has no analogous retry failure mode.

Recorded in `docs/ARCHITECTURE.md` §19. `make test`: 396/396 (390 + 6 new tests covering file:// routing, non-http protocols, and the regex-retry regression).

## Task Description (prior): DONE — reworked Phase 4's mechanism per direct user request (real on-disk rule, not implicit in-memory). Handed to Trin for re-UAT.

## Task Description (most recent): Phase 4 mechanism rework — real rule file, not implicit special case
Full notes: `agents/neo.docs/e15_phase4_correction_notes.md`. User asked, after Phase 4 was already gated: create a real `scalene_policy.yaml` with a real rule for the project folder when none exists, with no cache entry pre-seeded ("timestamp uninitialized"), avoiding an implicit special case. Removed `PolicyConfig.project_root`/its `__post_init__` logic/the synthetic `--list` line entirely; added `policy_config.write_default_project_policy()`, called once by `cli.py` before the ordinary `from_yaml()` load. Found and fixed a real bug while implementing: the broad default rule, written first, would silently shadow any later onboard-authored specific rule under append-only + first-match-wins semantics — fixed `_write_rule()` to insert ahead of the auto-created default specifically, leaving all other rule-writes unchanged. `make test`: 387/387, plus a real end-to-end CLI run confirming the file gets created correctly.

## Task Description (prior): DONE — fixed Smith's Phase 4 rejection (`--list` wording). Handed back to Smith for re-test.

## Task Description (most recent): fix Smith's Gate rejection — `--list` synthetic line wording
Smith found the original wording (`trust=trusted`) used a value that doesn't exist in this project's real trust vocabulary and described a mechanism (`decide_access()` escalating trust) that doesn't actually happen for a project-folder resource. Reworded to `sensitivity=internal (clean project files are allowed without escalating trust; ...)` — accurate to what the code actually does. Updated the one test asserting the old string, and `docs/ARCHITECTURE.md` §18.4's own line + a correction note. Re-ran the real CLI myself (not just the diff) to confirm the new text renders correctly. `make test`: 381/381 (unchanged count, just the one test's assertion updated).

## Task Description (prior): DONE — Sprint 9 (E15) Phase 4: Project-Folder Default. Handed to Trin for UAT (Smith's mandatory gate still pending).

## Task Description (most recent): `*swe impl phase-4` (Sprint 9/E15) — project-folder default posture
Full notes: `agents/neo.docs/e15_phase4_notes.md`. `PolicyConfig.project_root` + an implicit allow-rule appended after user rules; `cli.py` wired on both bare-constructor branches; `scg onboard --list` shows the synthetic discoverability line satisfying Smith's Gate 1 hard requirement. Real, wide implementation-time finding: deriving `project_root` unconditionally in `from_yaml()` broke 7 existing tests (extra rule in count assertions) — fixed each explicitly with a comment, not routed around by making the feature conditional. 5 new `TestProjectFolderDefault` tests cover the actual mechanism (clean-file validated-allow, second-file-doesn't-hit-the-wall, explicit-rule-wins, coexistence-with-restricted-paths, outside-project unaffected) plus 2 new `--list` tests for the synthetic line. `make test`: 381/381 (374 + 7 new).

Sprint 9 (E15) all 4 phases now implemented. Sprint-level exit needs: Trin's Phase 4 UAT, Smith's mandatory gate (her own Gate 1 hard requirement lands here), Morpheus's Phase 4 review, then sprint close (Oracle groom → Smith end-to-end test → retro → Cypher launch).

## Task Description (prior): DONE — Sprint 9 (E15) Phase 3: External Reputation Source. Handed to Trin for UAT (Tank review still required before phase closes).

## Task Description (most recent): `*swe impl phase-3` (Sprint 9/E15) — external reputation source
Full notes: `agents/neo.docs/e15_phase3_notes.md`. `URLHausChecker` + `composite_check()` in `reputation.py`, wired into `scan_worker.py`'s isolated subprocess. **Serious implementation-time finding**: wiring the composite check into the live subprocess path made every existing `URLScanner.scan()`-exercising test hit a real, live network call (the subprocess boundary means no in-process mock can reach `composite_check()`) — confirmed via timing (57s vs. ~43s baseline) and a direct curl to the endpoint from this environment. Fixed with an env-var gate (`SCALENE_SKIP_REMOTE_REPUTATION`, read by `composite_check()`, propagated to the child subprocess via `subprocess_isolation.run_scanner`'s existing env-copy) — added a small shared test helper (`tests/_env_guards.py`) and wired `setUpModule`/`tearDownModule` into all 8 test files that exercise a URL resource through a real scan path. `test_reputation.py` itself deliberately left unguarded (its own tests mock `_query_urlhaus` in-process, need the real code path). Re-added the §4 class-diagram entries this time (Phase 1 had to revert a premature addition). `make test`: 371/371, timing back to ~45s.

## Task Description (prior): DONE — Sprint 9 (E15) Phase 2: Hardcoded Restricted Paths. Handed to Trin for UAT.

## Task Description (most recent): `*swe impl phase-2` (Sprint 9/E15) — hardcoded restricted paths
Full notes: `agents/neo.docs/e15_phase2_notes.md`. Summary: `FileScanner.scan()` short-circuits on `/etc`/`~/.ssh` (prefix-boundary-safe, not naive startswith) before the secrets-scan subprocess ever runs. **Real design correction, found by tracing control flow before writing code, not after a test failed**: §18.2's proposed `resource_verifier.py` implicit-rule addition would have been unreachable dead code — `decide_access()` checks `is_bad` (true for any cached `"sensitive"` label) before any rule match, so the `FileScanner` short-circuit alone already makes this unconditional and un-overridable. Corrected `docs/ARCHITECTURE.md` §18.2 rather than implementing the unverified original plan. `make test`: 360/360 (352 + 8 new).

## Task Description (prior): DONE — Sprint 9 (E15) Phase 1: Configurable Scanner Registry. Handed to Trin for UAT.

## Task Description (most recent): `*swe impl phase-1` (Sprint 9/E15) — config-driven scanner registry
Full notes: `agents/neo.docs/e15_phase1_notes.md`. Summary: `scanner.load_scanners()` (new), `PolicyConfig.scanners` field, validation of a rule's `scanner` field moved from `PolicyRule.__post_init__` to `PolicyConfig.from_yaml` (documented behavior change, anticipated by Morpheus/Smith at Gate 2). `resource_verifier.py`/`onboard.py` thread `config.scanners`/an optional `scanners` param instead of importing the module `SCANNERS` constant directly. Found and fixed a real regression the full test suite caught (not a new test I wrote to find it): `onboard()`'s legacy path lost scanner-name validation when it moved out of `PolicyRule`, since `_onboard_resource()` constructs a `PolicyRule` directly, bypassing `from_yaml`'s new check — restored via an explicit check in `_onboard_resource()` itself. Also reverted a premature class-diagram addition (Phase 3's `ReputationChecker`/etc, caught by the diagram-drift guard test) — will re-add during Phase 3 itself, not before. `cache_refresh_worker.py` deliberately left scoped to builtins only (documented in-code), since making it see a config-declared scanner needs subprocess-argv plumbing with zero real payoff this epic (no custom scanner ships). `make test`: 349/349 (332 + 17 new).

## Task Description (prior): DONE — Sprint 8 (E14) Phase 3: demo/docs/existing-test reconciliation. Handed to Trin.

## Task Description (most recent): `*swe impl phase-3` (Sprint 8/E14) — breaking-change surface
Every real `--target` reference found at Smith's Gate 1 grep, fixed and re-verified against real output (not fabricated):
- `demo/run_demo.py`/`tests/test_demo.py`: `_onboard()` now writes a real tool-call JSON to a temp file and calls `scg onboard --call <path> --yes` (cleans up the temp file in a `finally`); Part 3's narration and the closing summary paragraph rewritten to describe target-identification + confirmation, not the retired single-URI flow. Ran the real demo end-to-end before touching the test.
- `docs/GETTING_STARTED.md` §4 and `docs/SETUP.md`'s onboarding section: rewritten against real command output (piped tool-call JSON, `--yes`, real `Verified:`/`Rule written to`/`N onboarded, M blocked` lines) — **found SETUP.md's onboard section had been stale since before sec16** (still described "seeds the cache" as if onboard never wrote a rule), a pre-existing gap this pass also closed, not something Sprint 8 introduced.
- `docs/USER_GUIDE.md`'s `scg onboard` section: fully rewritten against the real current `--help` output (`--call`/`--yes`/`--only`/`--list`, the removed `--tool`/`--pattern`), plus the confirmation flow, batch semantics, and `--list` all documented for the first time.
- `tests/test_user_guide_docs.py`: 2 tests were failing on `--target` no longer existing anywhere real — fixed both against real current text/output, added 1 new test asserting the confirmation UX (`--yes`/`--only`/`[Y/n/s(elect)]`) is documented, not just implemented.
- `tests/test_getting_started_docs.py`: its one direct-library-call test now mirrors the doc's real new flow (`identify_targets()` + `onboard_targets()`), matching what the rewritten doc actually shows.

**Revised scope, documented transparently (not silently)**: my Phase 1/2 handoffs both said `_resolve_resource()`/old `onboard()` would be deleted once Phase 3 removed their last real callers. Attempting the migration, I found `onboard()`'s own dedicated test suite (`TestOnboardUrlTarget`'s `test_unknown_scheme_blocks_with_no_cache_write`, in particular) exercises real, distinct behavior — `_resolve_resource()`'s URI-scheme validation — that has **no equivalent** in the new `identify_targets()` flow (an unrecognized scheme there just identifies nothing, silently; it was never designed to raise). Forcing this test to "migrate" would either lose real coverage or fabricate a test that doesn't reflect real usage. **Kept `onboard()`/`_resolve_resource()`** as a legitimate, still-fully-tested, single-URI library convenience function distinct from the new tool-call-driven flow, rather than deleting genuinely useful behavior to match a plan written before this was known. `main()` and the demo no longer call it — its callers are its own test suite now, which is appropriate for a still-real, still-correct library function.

**Flagged, not fixed (out of this phase's named scope, Morpheus's call)**: `docs/ARCHITECTURE.md` §5's "Onboarding" sequence diagram is stale — still shows the pre-Sprint-4 `jsonpath`/`pattern`/`allowlist` flow, predating even sec16. Not caught by `test_architecture_docs.py` (only checks the classDiagram block). Pre-existing, not introduced by this sprint; flagging for whoever next touches §5, or for Morpheus's Phase 3 review to decide if it belongs in this sprint's cleanup.

`make test`: 331/331 (was 324/329 known-red at Phase 2 handoff; all 5 fixed, 2 new tests added).

## Task Description (prior): `*swe fix` — Morpheus's Phase 2 review finding (axis validation ordering)

## Task Description (most recent): `*swe fix` — Morpheus's Phase 2 review finding (axis validation ordering)
Moved `_validate_axis(args.sensitivity, args.mode)` to run immediately after `argparse`, before `load_tool_call`/`identify_targets`/`_confirm_targets` — previously it only ran inside `onboard_targets()`, which is called *after* the interactive confirmation prompt, so a user answering the prompt could still get told afterward they'd forgotten a required flag. `main()` now uses the pre-validated, defaulted `(sensitivity, mode)` values directly when calling `onboard_targets()` (which still re-validates internally too — harmless, keeps it correct for direct library callers that skip `main()` entirely). Added a regression test asserting `input()` is never called when the axis is missing (`mock_input.assert_not_called()`), not just that the exit code is right — matches Morpheus's own verification standard (mocked a real run, not just read the code). `make test`: 330/330 minus the same 5 known Phase-3-scoped failures (one new test added, all else unchanged).

## Task Description (prior): `*swe impl phase-2` (Sprint 8/E14) — the Smith-gated phase

## Task Description (most recent): `*swe impl phase-2` (Sprint 8/E14) — the Smith-gated phase
TDD throughout, same discipline as Phase 1.
- Task 2.1 (§17.3, STORY-1402, Smith's Gate 1 hard requirement): `_confirm_targets()` — interactive numbered-list prompt by default (`Y`/empty=all, `n`=clean no-op, `s`=select-to-exclude), `--yes`/`--only` as non-interactive escapes, `--only` fails loud (names the missing identity) if given something never identified. **Fail-fast-not-hang verified directly**: mocked `sys.stdin.isatty()` → `False` with neither escape given, confirmed `OnboardError` raises immediately and `input()` is never called (`mock_input.assert_not_called()`) — this is the exact failure mode the hard requirement exists to prevent, tested as a negative assertion, not just "it didn't hang in this one run."
- Task 2.2 (§17.4, STORY-1403/1405): `onboard_targets()`/`_onboard_resource()` (factored out of the old `onboard()`, which now calls the same shared per-target logic — fixed a real bug I caught myself before it shipped: my first pass had `onboard()` construct its own second `PolicyRule` to override the batch function's return value, but the batch function had *already written* the wrong rule to disk by then — the override only fixed the returned dict, not the actual file. Fixed by giving `_onboard_resource()` optional `tool`/`pattern` params instead, so `onboard()`'s custom values flow through to the one real write, not a cosmetic patch after the fact). Batch semantics confirmed: one bad target in a 2-target batch leaves exactly 1 rule written, not 0 or 2. Reputation score appears in `main()`'s output when present (`... -> trusted (score 1.00)`).
- Task 2.3 (§17.5, STORY-1404): `--list [--scanner NAME]` — reads `ScanCache.all_entries()` directly, groups by scanner, no new store.
- `--target`/`--tool`/`--pattern` removed from `main()`'s argparse entirely, replaced by `--call`/`--yes`/`--only`/`--list`.
- **`make test`: 324/329 (5 known failures, not a regression to chase)** — all 5 are in files Mouse's plan explicitly scoped to Phase 3 (task 3.1: `tests/test_demo.py` ×4, still shelling out to the retired `scg onboard --target`; task 3.2: `tests/test_user_guide_docs.py`'s `test_onboard_flags_match_real_help_output`, checking `USER_GUIDE.md`'s stale usage block against the real new `--help` output). Also fixed one I found that *wasn't* in Mouse's named list: `tests/test_cli.py::test_onboard_subcommand_dispatches` also used `--target` — this one I fixed now rather than deferring, since it's testing `main()` itself (the exact thing this phase changes), not a demo/doc reconciliation task belonging to Phase 3.

## Task Description (prior): `*swe impl phase-1` (Sprint 8/E14): reputation score + target-identification core.

## Task Description (most recent): `*swe impl phase-1` (Sprint 8/E14)
TDD throughout — confirmed each new test red (`AttributeError`/`ImportError`) before implementing.
- Task 1.1 (§17.6, STORY-1405): `ReputationResult` gains `score: float`. `LocalHeuristicChecker.check()` rewritten from first-match-wins to evaluate-all-3-heuristics, `score = 1.0 - (triggered/3)`, `reason` now joins every triggered heuristic (not just the first). Proved it's not a relabeled boolean with a synthetic target that trips 2 of 3 heuristics simultaneously (`"xn--" + "a"*30 + ".com"` — punycode AND suspicious-length), confirming both the score and both reason substrings. `is_trusted`'s truth table confirmed unchanged (still any-trip-fails) via a dedicated regression test. Wired the score through the full real isolated-subprocess boundary (`scan_worker.py`'s JSON → `subprocess_isolation.run_scanner` → `URLScanner.scan()`), not just the in-process checker — `ScanResult` gains `reputation: float | None = None`, additive, `FileScanner` stays `None` deliberately (no test asserts otherwise, matching §17.6's "false precision" reasoning). 8 new tests.
- Task 1.2 (§17.1/17.2, STORY-1401): added `identify_targets(tool_name, tool_input)` (traverses `SCANNERS`, dedupes by `(kind, identity)`) and `load_tool_call(call_path=None)` (reads `{"tool_name", "tool_input"}` from a file or stdin, raises `OnboardError` — never a raw exception — on a missing file, malformed JSON, or missing `tool_name`). Both are new, standalone, fully tested functions — **deliberately did not touch `onboard()`/`main()`/`_resolve_resource()` yet**, a real scope adjustment from Mouse's literal Phase 1 task wording ("delete `_resolve_resource()` entirely"): rewiring the old single-target CLI into the new multi-target confirm/scan/write loop is Phase 2's actual job per Mouse's own dependency framing ("Phase 2 depends on Phase 1"), and deleting `_resolve_resource()` before Phase 2 replaces its only caller would either break `onboard()`/`main()` outright or leave dead code in between phases. Kept every phase independently green instead — 8 new tests, zero of the ~40 pre-existing onboard tests touched or broken.
- `make test`: 307/307 (299 + 8).

## Task Description (prior): `*swe fix` — Smith's sec16 gate bug (`scg onboard --help` discoverability)
Smith's `*user test sec16` found a real first-use regression: `--help` showed `--sensitivity`/`--mode` as independently optional (standard argparse brackets), so the naive pre-sec16 command (`--target` alone, matching old muscle memory) always failed on the first try with no way to know why beforehand. Bundled in Trin's related finding (`--mode mask` rejected by argparse's generic message before `onboard()`'s own detailed rationale could fire).
- Added an `epilog=` to `main()`'s `ArgumentParser` (with `RawDescriptionHelpFormatter` so line breaks render) disclosing both constraints — the runtime error messages were already correct, this only makes them reachable via `--help` before a user has to trigger the error.
- Updated `docs/USER_GUIDE.md`'s literal `scg onboard --help` reproduction to match (this doc's own convention, STORY-902, requires matching real `--help` output, not paraphrasing it).
- Added `TestOnboardHelpDisclosesRealConstraints` (2 new tests) to `tests/test_onboard.py`, guarding both disclosures directly against `main(["--help"])`'s real captured stdout, not just the epilog string existing in source.
- `make test`: 291/291 (289 + 2 new).

## Task Description (prior): pick up uncommitted `scg onboard` rework, fix the one failing test, close the architecture-doc gap
The user had already implemented (uncommitted, outside the formal Bloop chain) making `scg onboard` author a full `PolicyRule` in one call — see `onboard.py`'s own docstring for the full design rationale. `make test` was red on 1 failure when this session picked it up.
- Fixed `tests/test_user_guide_docs.py::test_documents_the_two_step_clearing_workflow` (renamed to `test_documents_the_single_call_clearing_workflow`) — it asserted retired "two explicit steps" language; `docs/USER_GUIDE.md`/`docs/GETTING_STARTED.md` were already correctly updated, only this test lagged.
- Added `docs/ARCHITECTURE.md` §16 — the uncommitted work reverses §14.3's Smith-Gate-locked "CLI surface does not change" hard requirement with no addendum recording it. Documented the reversal per this doc's established append-only-correction convention, and flagged the same review debt §15 flagged for itself (no Trin/Morpheus/Smith pass has run against this change yet).
- `make test`: 289/289 (via the `make` skill, not raw unittest). Cross-checked call sites via `via` (`--via calls -mg '*onboard*'`) after `make via_index` — only `run_demo.py`/`onboard.py`'s own `main()` call it, both already consistent with the new signature.
- **Not done**: the formal Trin UAT / Morpheus review / Smith gate this change needs — see §16's "Not yet reconciled" note and `next_steps.md`.

## Task Description (prior): `*swe impl phase-1` (Sprint 6/E12)
- Task 1.1: `PolicyRule.__post_init__` validates `scanner` against the real `SCANNERS` registry (empty/omitted stays unvalidated — the common case). 3 new tests.
- Task 1.2: `make test-q` — real recipe `unittest discover -s tests -b`. **Verified empirically before finishing, not assumed**: measured 5→1 occurrences of logging/asyncio noise on a real run — genuinely quieter, not perfectly silent (one asyncio slow-callback warning survives a test class whose event loop pre-dates `-b`'s per-test redirection). Corrected my own architecture handoff message and the `make` skill's doc, which both implied full suppression — also fixed the skill's pre-existing wrong claim that `make test` runs pytest+lint+secret-scan (it's plain `unittest discover`, always was).
- Task 1.3: new `tests/test_architecture_docs.py` — parses `docs/ARCHITECTURE.md`'s `classDiagram` block, flags any class that doesn't exist in `src/scalene/` and has no valid `<<module: file.py>>` stereotype. Proved it's not a no-op with 4 tests against synthetic snippets (a renamed class is flagged, a valid/invalid module stereotype, a real class isn't flagged) rather than only asserting the real doc currently passes.
- `make test`: 275/275 passing.

## Task Description (prior): sec15 rework — rule-driven access control replaces content-scanning
Trin's Phase 3 UAT flag (a blanket `pattern:".*"` + `mode:allow` rule could silently disable all scanning) led to a direct design conversation with the user that replaced the sprint's whole mechanism. New model: two sticky session tags (`trust`: low/med/high; `sensitivity`: public/internal/restricted), a call proceeds only if every resource it touches is either validated+explicitly-allow-ruled or the session is still clean, otherwise blocked. Full spec: `docs/ARCHITECTURE.md` §15.

**What changed:**
- `taint_state.py`: rewrote `TaintState` — `trust`/`sensitivity` string fields replace `has_sensitive_data`/`has_untrusted_data` booleans, ratchet-only escalation (`escalate_trust`/`escalate_sensitivity`), `is_clean` property.
- `resource_verifier.py`: new `decide_access(tool_name, args, config, cache, taint) -> AccessDecision`. Per-resource classification: `confirmed_bad` (scanner found it bad, OR a matched rule's mode isn't `allow` — both block unconditionally, a rule never overrides a real bad finding) / `validated_allow` (rule matched + mode=allow + cache confirms clean — proceeds, escalates sensitivity, bypasses the contamination gate) / `uncleared` (no rule, or rule pending validation — proceeds only if session still clean, escalating trust to low; blocked once already contaminated). Old `evaluate()`/`MatchResult` kept intact (still tested) but no longer wired into the hot path.
- `hook_adapter.py`: `pre_tool_use` now calls `decide_access` directly (no more `MaskingEngine`/payload-field extraction in the main flow). `post_tool_use` reduced to a documented no-op — every resource is knowable from `tool_input` pre-call, so there's nothing left for it to do.
- `monitor_data.py`/`monitor_app.py`: `SessionInfo`/`BlockEvent` (renamed from `MaskEvent`) for the new tags; removed STORY-702's editable-apply-command UI entirely (clearing a destination now takes 2 steps — onboard + rule — not one runnable command).
- `demo/run_demo.py`, `docs/GETTING_STARTED.md`, `docs/USER_GUIDE.md`, `README.md`: fully rewritten for the new model, each verified by running the real commands live before writing them into docs (not transcribed from memory).
- Found and fixed 2 real bugs while testing live: a double "Blocked: Blocked:" prefix in the demo's narration, and `scg onboard` correctly refusing to cache a bad IP-literal target meant the demo's "known-bad overrides a rule" part wasn't actually testing what it claimed (fixed by seeding that cache entry directly, matching what a real background scan would produce).
- `masking.py`/`MaskingEngine`/`scan_text_for_secrets` kept intact and still tested but dormant — not deleted, since whether content-scanning still has a role on top of the access-control decision is explicitly undecided (§15.5), not ruled out.

## Task Description (prior): `*swe impl phase-3` (Sprint 5, STORY-1104, STORY-1103 amendment)

## Task Description (most recent): `*swe impl phase-3` (Sprint 5, STORY-1104, STORY-1103 amendment)
- Task 3.1: `MaskingEngine.decide()` rewritten — drops `taint`/`provenance_risk` entirely, scans every non-null value unconditionally unless `match.mode == "allow"` (skips scan entirely). Signature is now `decide(match, value)`.
- Task 3.2: `hook_adapter.pre_tool_use` updated for the new signature. Also removed the now-dead `taint = TaintState.load(...)` line (it fed only the removed gate) — `post_tool_use` remains the sole writer, still feeding `scg monitor`.
- Task 3.3: split the steady-state perf test in two — pure resource-verification (`Read`, no payload value, still <15ms, STORY-1104 doesn't touch this path) vs. a new `NFR-Perf-UnconditionalScan` test (Bash command with a real scan, measured ~30ms avg, set a 45ms provisional budget with headroom — measured, not assumed).
- Task 3.4: reworked `_suggest_onboard_command`'s message — drops the now-false "stops future masking" claim, adds `_suggest_allow_rule()` (a concrete YAML `mode: allow` rule snippet scoped to the exact untrusted URL). **Found and fixed a real bug while doing this**: `re.escape()`'s backslash-escaped regex is invalid inside a YAML *double*-quoted string — switched the pattern field to single-quoted YAML (backslashes literal there). Rewrote `tests/test_onboard_suggestion_e2e.py` into 2 tests: onboarding alone no longer stops masking; an explicit allow rule does (and doesn't leak to other destinations).
- Also updated `demo/run_demo.py`: Part 3 now shows a trusted destination's secret still getting masked (was the opposite before); new Part 4 demonstrates the `mode: allow` rule + its scoping; renumbered old Part 4 (block) to Part 5. Ran the demo directly end-to-end to confirm the narrative reads coherently, not just that assertions pass.
- Task 3.5: updated `docs/USER_GUIDE.md`'s policy-config section for `rules:`/`sensitivity`/`mode` (incl. `allow`) and the unconditional-scanning behavior change.
- `make test`: 266/266 passing.

## Task Description (prior): `*swe impl phase-2` (Sprint 5, STORY-1101/1102/1103/1105)

## Task Description (most recent): `*swe impl phase-2` (Sprint 5, STORY-1101/1102/1103/1105)
- Task 2.1: rule matching in `resource_verifier.py` — `_resolve_rule_for_resource()` (first rule in declaration order where `tool` regex matches tool_name, `pattern` regex matches `resource.identity`, optional `scanner` filter) + `_resolve_sensitivity_and_mode()` (aggregates across all identified resources in a call via most-restrictive-wins: `restricted`>`internal`>`public`, `block`>`mask`>`allow`).
- Task 2.2: `MatchResult` gains `sensitivity`/`mode` fields, wired into `evaluate()`'s return. `is_sensitive`/`is_trusted` untouched.
- Task 2.3: added the STORY-1105 migration fail-safe test (`test_old_format_host_keyed_cache_entry_does_not_leak_trust` — seeds a raw old-format `reputation:<host>`-keyed cache file, confirms a live call to a path under that host is NOT trusted). STORY-1101's evaluate()-level defect-fix test was already added during Phase 1 review prep.
- 9 new rule-matching tests cover: no-rules default, matching override, non-matching fallback, tool filter, scanner filter, most-restrictive-wins across resources, first-match-wins by declaration order.
- `make test`: 262/262 passing.
- Updated §4's `MatchResult` class diagram box for the new fields.

## Task Description (prior): `*swe impl phase-1` (Sprint 5, STORY-1101/1102/1103/1105)

## Task Description (most recent): `*swe impl phase-1` (Sprint 5, STORY-1101/1102/1103/1105)
- Task 1.1: `URLScanner`'s `_URL_FALLBACK_RE`/`identify()` changed from host-only to full-URL identity (scheme+host+path, query dropped) — the actual STORY-1101 defect fix. `scan()` extracts the host back out via `urlparse` for the underlying host-level reputation heuristic (a URL's path doesn't change whether its host is reputable), but the cache key stays per-URL.
- **Found and fixed a real fallout bug while doing this**: `hook_adapter._suggest_onboard_command()` returned a hardcoded generic placeholder host — that only worked because trust used to be host-level. Broke `tests/test_onboard_suggestion_e2e.py` (a real "run the suggested command, confirm the exact same call stops being masked" test). Fixed by adding `MatchResult.untrusted_url` (resolved in `resource_verifier.evaluate()`, the specific untrusted URL resource actually identified) and wiring it into the suggestion message. Also updated `onboard.py`'s `_resolve_resource` to normalize URL targets the same way (scheme+netloc+path) so `--target` pre-seeds the exact cache key a live call would look up.
- Task 1.2: `PolicyRule` frozen dataclass in `policy_config.py` (tool/pattern/sensitivity/mode/jsonpath/scanner/description, validates sensitivity∈{public,internal,restricted} and mode∈{mask,block} via existing `PolicyConfigError`). `PolicyConfig.rules: tuple[PolicyRule, ...]` parsed from an optional `rules:` YAML list.
- Task 1.3: rewrote this repo's own root `scalene_policy.yaml` — its pre-Sprint-4 `allowlist:` block had been silently dead since E10 shipped (`PolicyConfig.from_yaml` never read it). Replaced with an equivalent `rules:` entry (consolidated 3 old per-tool rules into 1 using `tool: "Read|Write|Edit"`, same pattern/intent). Added a real regression test (`TestRepoOwnPolicyFile`) that parses this exact file, rather than eyeballing it once. §4's class diagram already had a `PolicyRule` box (added when §13.8 was written) — updated `PolicyConfig`/`MatchResult` boxes for the new `rules`/`untrusted_url` fields.
- `make test`: 250/250 passing (was 238 before this phase's new tests).
- Deliberately deferred `sensitivity`/`mode` fields on `MatchResult` to Phase 2 (wrote then removed a premature test) — Phase 1's exit criteria is identity/schema only, no rule-matching logic yet.

## Task Description (prior): `*swe impl phase-5` (Sprint 4, STORY-1005)
New panel in `monitor_app.py`/`monitor_data.py` showing recent scan results, reading `.scalene/scan_cache.json` directly. Full spec: `docs/ARCHITECTURE.md` §13.6, task breakdown in `task.md` Sprint 4 Phase 5.

## Progress
- [x] `ScanCache.all_entries()` — new public method, same locking as `get()`/`put()`.
- [x] `monitor_data.discover_scan_results()` — reads via `all_entries()`, excludes in-flight-only reservations, fails safe to `[]` on corruption (read-only view, must not crash the TUI).
- [x] `monitor_app.py`: third `#scan-results` DataTable panel (Resource/Label/Last Scanned), refreshed every poll tick.
- [x] **Closed Morpheus's 3x-carried-forward note**: `ARCHITECTURE.md` §4's class diagram rewritten for real, `PolicyRule`/`allowlist` replaced with the actual current classes.
- [x] Fixed the same `cache_path`-not-threaded-through-tests gap as Phase 3, this time in `test_monitor_app.py` (14 call sites).
- [x] `tests/test_monitor_data.py` (+6), `tests/test_scan_cache.py` (+2), `tests/test_monitor_app.py` (+4).
- [x] `make test`: 222/222 passing.

## Blockers
None for implementation. Smith's mandatory gate required (task.md — new UI surface, same precedent as Sprint 2's Console Foundations gate).

## Oracle Consultations
None yet.

---
*Last updated: 2026-07-15*
