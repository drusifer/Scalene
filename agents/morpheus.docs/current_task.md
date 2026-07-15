# Current Task

**Status:** Sprint 4 Phase 5 review: APPROVED. Handing to Smith for the mandatory gate — **last Sprint 4 phase**, clears into Stage 3 close after this.
**Assigned to:** N/A
**Started:** 2026-07-15
**Completed:** 2026-07-15

## Task Description (most recent): `*lead review phase-5` (Sprint 4, STORY-1005)

## Progress
- [x] Read `monitor_data.discover_scan_results()`/`monitor_app.py`'s new panel against §13.6 — matches exactly, reads the real cache store via `ScanCache.all_entries()`, no parallel bookkeeping
- [x] Reviewed my own §4 class-diagram rewrite (Neo closed my 3x-carried-forward note this phase) for accuracy before considering it done: caught that I'd represented `resource_verifier.evaluate()` — a free function, not a class — as a plain pseudo-class box, which could mislead a reader into thinking a literal `class ResourceVerifier` exists. Fixed with a `<<module: resource_verifier.py>>` stereotype, consistent with the diagram's existing `<<interface>>`/`<<exception>>` stereotype usage.
- [x] `make test`: 223/223 passing (unaffected by the doc fix, confirmed).
- [x] **APPROVED.** Handing to Smith for the mandatory gate.

## Task Description (prior): `*lead review phase-4`

## Task Description (most recent): `*lead review phase-4` (Sprint 4, STORY-1004)

## Progress
- [x] Read `onboard.py`, `scan_cache.py`, `cli.py`, `cache_refresh_worker.py` against §13.4/§13.5 — matches exactly, including the file-identity normalization that keeps onboarding and live evaluation using the same cache key
- [x] Personally re-verified the exit-code fix myself (not just trusting Trin's PreToolUse-only test): confirmed live that `PostToolUse` also correctly returns exit 2 on cache corruption — consistent with the real contract's "exit 2 is non-blocking for PostToolUse but still surfaces stderr" semantics
- [x] Traced `refresh_if_needed()` → `cache.get()`/`try_reserve()` call ordering: confirmed no partial-state issue if `ScanCacheError` fires on the first call (never reaches the second)
- [x] **Non-blocking observation**: `is_fresh()`/`put()`'s direct `os.stat()` calls on a *resource's own file* (not the cache store) aren't wrapped in error handling — a theoretical TOCTOU gap (file vanishes between `os.path.exists()` and `os.stat()`) could raise uncaught. Extremely low likelihood/impact, and out of STORY-1004's specific scope (that's about the cache *store*, not a scanned resource's own filesystem entry) — not worth a fix round.
- [x] Confirmed `scg onboard`'s own CLI exit codes are correctly NOT conflated with `scalene-guard`'s hook-specific exit-2 semantics — `onboard.py` is a normal dev CLI, no Claude Code hook contract governs it, plain `return 1` on any `OnboardError` is the right, boring Unix convention there.
- [x] `make test`: 210/210 passing, 0 skipped.
- [x] **APPROVED.** Handing to Smith for the mandatory gate.

## Carry-forward (not new, flagged again)
`ARCHITECTURE.md` §4's class diagram is still stale (still shows `PolicyRule`/`allowlist`) — flagged at Phase 3 review, flagged again at Phase 4 handoff by Neo, still not done. Third flag. Should happen at Phase 5 or as its own small cleanup — I'll personally check this doesn't slip a fourth time.

## Task Description (prior): `*lead review phase-3`

## Task Description (most recent): `*lead review phase-3` (Sprint 4, STORY-1002/1003)

## Progress
- [x] Read `resource_verifier.py` + both `hook_adapter.py` call sites against §13.1/§13.1.1 — confirmed `MatchResult` shape and `MaskingEngine.decide()`'s content-gating logic are genuinely untouched, exactly as the architecture specified this swap should work
- [x] Confirmed `ScanCache(cache_path)` construction is fresh-per-hook-invocation (no daemon, matches §2's stateless-process-per-hook-call principle)
- [x] **Structural observation (non-blocking, documentation-worthy)**: `resource_verifier.evaluate()` hardcodes exactly two scanner names (`_FILE_SCANNER_NAME`/`_URL_SCANNER_NAME`) mapping to the two fixed `MatchResult` dimensions (sensitivity/trust) — STORY-1002's "adding a scanner is adding an entry, no dispatch code changes" AC holds for the detection/registry layer (`SCANNERS` dict, `identify()`/`scan()`) but NOT for this aggregation layer. A 3rd scanner type would need someone to explicitly decide which `MatchResult` dimension(s) it affects — inherently a human design call given `MatchResult`'s shape is fixed at 2 dimensions, not something "just add a registry entry" can resolve automatically. Not a regression (implicit since Phase 1's registry design), but worth a one-line `ARCHITECTURE.md` §13.2 clarification so a future contributor doesn't assume full dispatch-free extensibility exists at this layer.
- [x] Reviewed Trin's independently-confirmed onboard-suggestion regression myself — agree it's real and significant, not overstated. This is the exact "copy the command, run it, it works" promise that's been gated and re-verified twice already (Sprint 1 UX consult, Sprint 3 Gate 1/2) — from a real user's perspective this is one atomic feature now partially broken, even though internally it's cleanly split across two sequenced phases. **My recommendation for Smith to weigh, not a decision I'm making unilaterally**: this needs her explicit call on whether Phase 3 is shippable with this window open, or whether it should block until Phase 4 closes it.
- [x] `make test`: 200/200 passing, 1 documented skip.
- [x] **APPROVED.** Handing to Smith for the mandatory gate (task.md: "this is the phase where a real behavior/copy change becomes user-visible").

## Resolution (2026-07-14)
User chose "accept the cost, revise the NFR" over the other two options (batch spawns, decouple from sync hot path). Updated both docs to be honest about the real cost rather than let Phase 3's perf test discover it as a surprise:
- `docs/ARCHITECTURE.md` §13.3: split the NFR into `NFR-Perf-Steady-State` (<15ms, unchanged, cached/fresh path) and `NFR-Perf-FirstSighting` (new, provisional **<25ms added latency per newly-identified resource**, headroom over the measured ~16ms worst case) — explicitly flagged for Phase 3 task 3.4 to verify with a real test, not assume.
- `docs/PRD.md`: Sprint 4 Goal 13 and the top-level <15ms success metric both annotated with the 2026-07-14 exception and a pointer to §13.3.
- Deliberately did **not** redesign `refresh_if_needed()`'s spawn mechanism (batching/decoupling) — the added cost is one-time-per-resource and self-amortizing (every subsequent call on that resource falls back to the free steady-state path), judged not worth the added design complexity given the user's choice.

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
