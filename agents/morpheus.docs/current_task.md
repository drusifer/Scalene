# Current Task

**Status:** Sprint 4 plan reviewed and LOCKED. Handed Phase 1 to Neo.
**Assigned to:** N/A (planning finished; next is Phase 1 implementation)
**Started:** 2026-07-14
**Completed:** 2026-07-14

## Task Description
`*lead arch sprint` (Sprint 4), following Smith's Gate 1 approval on Cypher's E10 stories (STORY-1001 through 1005).

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
