# Current Task

**Status:** Sprint 4 phase breakdown written to `task.md`. Handed to Morpheus for plan review.
**Assigned to:** Mouse
**Started:** 2026-07-14

## Task Description
`*sm plan sprint` (Sprint 4), per the `*plan sprint` Bloop chain, following Smith's Gate 2 approval on Morpheus's E10 architecture (`docs/ARCHITECTURE.md` §13).

## Progress
- [x] Read Cypher's stories (E10, STORY-1001-1005), Morpheus's architecture (§13, incl. the full-replacement decision), and both Smith gate notes (first-sighting message wording; fatal-exit plain-language + verified exit code) plus her 2 Gate 2 watch-items (perf NFR re-verification, concurrent-scan dedup)
- [x] 5 phases, hard-dependency-ordered (unlike Sprint 3's foundational-but-parallel phases) — this genuinely can't be built out of order: scanners before cache, cache before hook integration, hook integration + cache before onboard/monitor consumers
- [x] Phase 1 — Scanner Protocol & Built-in Scanners: no Smith gate (internal, no user-facing change yet)
- [x] Phase 2 — Scan Cache Store: no Smith gate (internal); folded Smith's dedup watch-item and Morpheus's orphaned-process devops note into its exit criteria rather than a separate Tank phase
- [x] Phase 3 — Hook Integration & First-Sighting Messaging: Smith gate required (real behavior + copy become user-visible here); folded the perf-NFR re-verification watch-item in as its own task (3.4) rather than assuming it
- [x] Phase 4 — scg onboard Re-scope & Fatal Exit: Smith gate required (operator-facing CLI change + fatal-exit UX); folded the exit-code verification-not-assumption requirement in as its own task (4.3)
- [x] Phase 5 — scg monitor Resource Panel: Smith gate required, same precedent as Sprint 2's Console Foundations
- [x] Confirmed no Tank phase — no daemon, background scans are one-shot detached subprocesses; `.scalene/scan_cache.json` needs `.gitignore` treatment, folded into Phase 2
- [x] Wrote all 5 phases into `task.md`, updated header status

## Blockers
Waiting on Morpheus's `*lead review sprint plan` before Phase 1 can start.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-14*
