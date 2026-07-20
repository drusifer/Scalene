**Status:** DONE — sec16 `*swe fix` for Smith's `*user bug` (onboard --help discoverability). Handed to Trin for re-verification.
**Assigned to:** Neo
**Started:** 2026-07-20
**Finished:** 2026-07-20

## Task Description (most recent): `*swe fix` — Smith's sec16 gate bug (`scg onboard --help` discoverability)
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
