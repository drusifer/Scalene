# Current Task

**Status:** Sprint 4 Phase 1 review: APPROVED. Handed Phase 2 to Neo.
**Assigned to:** N/A (Phase 1 review finished; next is Phase 2 implementation)
**Started:** 2026-07-14
**Completed:** 2026-07-14

## Task Description (most recent): `*lead review phase-1` (Sprint 4, STORY-1001/1002)

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
