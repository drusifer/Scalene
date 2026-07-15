# Current Task

**Status:** Sprint 4 Phase 2 review: APPROVED, with a major flag for Phase 3. Paused for user visibility before Phase 3 starts (not a formal Smith gate, but a real architecture-premise risk).
**Assigned to:** N/A
**Started:** 2026-07-14
**Completed:** 2026-07-14

## Task Description (most recent): `*lead review phase-2` (Sprint 4, STORY-1003)

## Progress
- [x] Read `scan_cache.py`/`cache_refresh_worker.py` against §13.3 — key format matches the literal `f"{scanner_name}:{resource.identity}"` formula (correctly resolved, not the illustrative-but-inconsistent JSON example I flagged after Phase 1)
- [x] Found a real (if bounded) robustness gap myself: `cache_refresh_worker.py`'s `try/except` wraps `scanner.scan()` but not the subsequent `ScanCache.put()` call — confirmed live with a mocked `OSError` on `put()`, the exception propagates uncaught out of `main()`. Bounded impact: this is a detached background worker, so its crash never reaches the parent's already-returned response; practical effect is just that one resource sits in its 5-minute pending-reservation window before self-healing on the next lookup. **Non-blocking** — flagged for Phase 3/4 hardening, not a Phase 2 rejection.
- [x] **Major finding — personally verified the "zero-added-latency" claim from my own §13.3 design and found it does NOT hold**: measured `refresh_if_needed()` on brand-new (never-cached) resources at ~6.6ms avg / ~16ms max per call. Isolated the cause: it's `subprocess.Popen()`'s own spawn-call cost in a fire-and-forget pattern (not waiting between spawns) — reproduced the same ~3.6ms avg / ~19ms max with a trivial no-op command, ruling out the worker script's own complexity as the cause. This is real process-creation cost in this environment, not a measurement artifact.
  - **Why this matters**: §13.3's entire non-regression argument for the "new resource" path rests on it being "identical to today's fail-safe-default behavior... zero-latency." It isn't — it's up to ~16ms of *added* latency on top of whatever `pre_tool_use` already costs (~6ms per Trin's Sprint 1 informal check), which alone could exceed the existing <15ms hot-path NFR on a single first-sighting call, before even accounting for multiple never-seen resources in one call (e.g. a `Bash` command with 2 paths + 1 URL = 3 separate spawns, compounding).
  - **Not a fresh surprise** — this is precisely the risk Smith's Gate 2 watch-item and task.md's Phase 3 task 3.4 ("re-verify <15ms NFR... not assumed compatible") already anticipated. My measurement turns that from a flagged-but-unverified risk into a confirmed, quantified one, which changes Phase 3 from "verify it's probably fine" to "this needs an actual design decision before wiring into the hot path."
- [x] `make test`: 195/195 passing
- [x] **APPROVED** (Phase 2 delivered exactly its own scope correctly) **with the latency finding escalated to the user before Phase 3 begins** — this isn't a formal Smith gate, but building Phase 3 on a performance premise I've now personally disproven risks a lot of wasted downstream work.

## Task Description (prior): `*lead review phase-1` (Sprint 4, STORY-1001/1002)

## Progress
- [x] Read `src/scalene/scanner.py` in full against §13.2's spec — `Scanner` Protocol, `Resource`/`ScanResult` dataclasses, `SCANNERS` registry all match the architecture literally (field names, registry shape)
- [x] Confirmed extensibility AC (STORY-1002): adding a 3rd scanner is only a `SCANNERS` dict entry, no dispatch code elsewhere references `FileScanner`/`URLScanner` by name
- [x] Independently adversarially probed `identify()`/`scan()` myself before approving (my own standing habit, not just trusting Trin's UAT): mixed non-string arg values (int/None/bool alongside strings), empty args dicts, empty-string known-field values — all degrade cleanly, no crash, no spurious resource
- [x] Reviewed Trin's finding + Neo's fix (URL/path collision — every `WebFetch` call was producing a bogus file resource) — the fix (span-exclusion against a full-URL regex) is structurally sound, not a patch that just moves the bug; confirmed it handles the general case (arbitrarily many `/segments` in a URL path), not just the one repro string
- [x] **Confirmed a design note Neo already self-flagged holds up under review, not a fresh finding**: `FileScanner.scan()`/`URLScanner.scan()` never raise — any `run_scanner` failure (real finding *or* scanner-machinery breakage) collapses into a `ScanResult` label. §13.2's docstring implies scan() raising is *one* of STORY-1004's two fatal triggers (the other being cache-store corruption, unrelated to scan()). Since `run_scanner`'s existing `{"ok": bool, "reason": str}` contract (Sprint 1, unchanged) doesn't distinguish "finding" from "infra failure" either, this isn't a Phase 1 regression — it's a pre-existing ambiguity Neo faithfully preserved and correctly deferred to Phase 4, not silently swallowed. Confirmed it's captured in Neo's `next_steps.md` so Phase 4 doesn't rediscover it from scratch.
- [x] Confirmed no `hook_adapter.py`/`policy_config.py` changes leaked into this phase — `scanner.py` is genuinely standalone, matches Phase 1's scope exactly
- [x] `make test`: 176/176 passing
- [x] **APPROVED.** No Tank/Smith gate needed (internal component, correct per task.md).

## Task Description (prior): `*lead arch sprint` (Sprint 4), following Smith's Gate 1 approval on Cypher's E10 stories (STORY-1001 through 1005).

## Progress
- [x] Resolved Cypher's explicit open question: **full replacement** of `PolicyConfig.allowlist`/`PolicyRule` (the tool/jsonpath/pattern/target model shipped one commit before this epic), not coexistence — the defect this epic fixes is structural to pattern-matching itself, keeping it around anywhere would leave the hole open on that path.
- [x] Designed `Scanner` protocol + registry (`identify()`/`scan()`), `Resource`/`ScanResult` types — extensible per STORY-1002, reused existing `FileScanner`≈`secrets_scan.py`/`URLScanner`≈`LocalHeuristicChecker` logic rather than rewriting it
- [x] Decided Bash gets no dedicated scanner type — its command string is fed into FileScanner's and URLScanner's existing generic-fallback detection instead of duplicating shape-detection regexes in a third scanner
- [x] Designed the scan cache (`.scalene/scan_cache.json`, `filelock`-protected like `taint_state.py`) and its 3-state lookup table (none/fresh/expired) per STORY-1003 — confirmed the "new resource" path adds zero latency (identical to today's fail-safe-default behavior) since it never blocks on a scan, only seeds the cache in the background
- [x] Designed "background" as a detached `Popen` (no `.wait()`) subprocess, consistent with the existing SCALENE_BYPASS isolation pattern — no daemon introduced
- [x] Confirmed `mtime`-only staleness for files (no hashing) per explicit user direction
- [x] Re-scoped `scg onboard` to pre-seed the cache (drops `--tool`/`--jsonpath`/`--pattern`/`--description` entirely) rather than writing a policy rule
- [x] Specified the fail-safe-exit-0 vs fatal-exit-nonzero boundary precisely (STORY-1004): ordinary scan findings stay exit 0; only scanning-*machinery* failure (cache store broken, scanner crash) is fatal. Provisional exit code 1, explicitly flagged for Neo to verify against the real Claude Code hook contract before shipping — not assumed, same lesson as the earlier schema fix
- [x] Documented exactly how this integrates with the unchanged `MaskingEngine.decide()` content-gating path (§13.1.1) — two different checks, only one is being replaced
- [x] `scg monitor` gets a new resource-cache panel (STORY-1005), same poll-based pattern as existing panels
- [x] Flagged §4's class diagram as stale-until-implementation (predates §13, will need a real update once Neo's classes exist)

## Progress (plan review, 2026-07-14)
- [x] Verified Mouse's 5-phase breakdown matches §13 exactly: scanners → cache → hook integration → onboard/monitor consumers, correctly hard-dependency-ordered (not foundational-but-parallel like Sprint 3)
- [x] Verified Smith gate placement (Phases 3-5 gated, Phases 1-2 not) matches expectation — Phases 1-2 are internal, no user-facing surface yet
- [x] Verified both Smith Gate 2 watch-items (dedup, perf re-verification) and my own devops note (orphaned processes) are folded into named tasks (2.3, 3.4, folded into Phase 2 exit criteria), not left as loose prose
- [x] Confirmed no Tank phase needed
- [x] **APPROVED. Sprint 4 plan LOCKED.**

## Blockers
None — handed Phase 1 to Neo.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-14*
