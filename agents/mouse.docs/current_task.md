# Current Task

**Status:** Sprint 10 (E16) phase breakdown written to `task.md`. Handed to Morpheus for plan review.
**Assigned to:** Mouse
**Started:** 2026-07-22

## Task Description (most recent): `*sm plan sprint E16`
6 phases from STORY-1601-1606 (`docs/USER_STORIES.md`) + `docs/ARCHITECTURE.md` §20. Phase 1 (retry guidance + audit-log schema) is a hard prerequisite for Phase 2 (tagged log UI) and Phase 4 (dashboard); Phase 3 (scanner activity) and Phase 6 (read-only boundary) are independent and could reorder without disruption. Two mandatory Smith gates: Phase 2 (accessibility — color-stripped render) and Phase 5 (the epic's core Verify/Allow/Deny flow, same weight as prior mandatory onboard-flow gates). Phase 6 has a required Tank task, same standing pattern as Sprint 9's Phase 3. Recorded the mid-planning STORY-1603 scope correction (block-only → full log, user-corrected a cost-conflation error) directly in `task.md`'s Notes so the phase history isn't silently rewritten. Handed to Morpheus (`*lead review sprint plan`).

## Task Description (prior): Sprint 9 (E15) phase breakdown written to `task.md`. Handed to Morpheus for plan review.
**Started:** 2026-07-21

## Task Description (most recent): `*sm plan sprint` (Sprint 9 / E15)
Following Smith's Gate 2 approval on Morpheus's §18 architecture. 4 phases, sequenced by story order (1501→1502→1503→1504) rather than a hard technical dependency chain — only real shared-file overlap is Phase 1's `PolicyConfig` field additions (`scanners`, `project_root`), which Phases 2-4 all build on incidentally, not because 1502/1503/1504 depend on each other. Explicitly flagged in task.md's Notes that Phase 3 (Tank-gated) and Phase 4 (Smith-gated) have no dependency on each other and could reorder if Tank's review runs long — pre-empting a "re-planning = plan failure" misread if that happens, per Sprint 3's retro lesson about a 3rd status bucket for exactly this shape.
Gate placement: Phase 1/2 get no Smith gate (no new CLI/interactive surface, matches Sprint 8 Phase 1's precedent). Phase 3 gets a **required Tank task**, sequenced last within the phase per standing protocol (new outbound network dependency). Phase 4 gets the **mandatory Smith gate** — this is where Smith's Gate 1 hard requirement (STORY-1504 discoverability) actually gets built and must be verified live, same weight as Sprint 8's Phase 2 pty-gate.
Handed to Morpheus (`*lead review sprint plan`).

## Task Description (prior): `*sm plan sprint` (Sprint 8 / E14)

## Task Description (most recent): `*sm plan sprint` (Sprint 8 / E14)
Following Smith's Gate 2 approval on Morpheus's §17 architecture. 3 hard-dependency-ordered phases (§17.1/17.2's rewrite is load-bearing for everything downstream — same chain shape as Sprint 4/5, not Sprint 3's parallel-capable one): Phase 1 (reputation score + new target-identification core, no Smith gate — internal/library-level, no usable CLI change yet), Phase 2 (confirmation + per-target scan/write + `--list`, **Smith gate required** — this is where the real interactive/CLI surface lands, including her Gate 1 hard requirement's actual implementation), Phase 3 (demo/docs/existing-test reconciliation, no separate Smith gate — Trin's UAT re-runs doc examples verbatim instead, matching the project's standing practice for doc-only phases). Folded Smith's Gate 1 breaking-change-surface grep directly into Phase 3's 3 tasks by name, not left as prose — every file she found is a named task. Folded her Gate 2 mixed-sensitivity note into Phase 2's exit criteria explicitly. No Tank phase (no infra/daemon change).

## Task Description (prior): `*sm plan sprint` (Sprint 5)
Following Smith's Gate 2 approval on Morpheus's E11 architecture (`docs/ARCHITECTURE.md` §14). Broke into 3 hard-dependency-ordered phases (schema → matching → wiring, same shape as Sprint 4's chain, not Sprint 3's parallel-capable one): Phase 1 (resource identity fix + rule schema, no Smith gate — no user-facing surface yet, `scg onboard` explicitly untouched), Phase 2 (rule matching + `MatchResult` extension, no Smith gate — still nothing consumes the new fields), Phase 3 (unconditional masking wiring + docs, **Smith gate required** — this is where the actual user-visible behavior change lands). Folded Morpheus's real-migration-test-case finding (repo's own dead `allowlist:` block) into Phase 1 task 1.3 rather than a separate task. Folded the `NFR-Perf-UnconditionalScan` verification requirement into Phase 3 task 3.3 as a named task, not left as prose. No Tank phase (confirmed via §14.7 — no daemon/infra change).

## Task Description (prior): `*sm plan sprint` (Sprint 4), per the `*plan sprint` Bloop chain, following Smith's Gate 2 approval on Morpheus's E10 architecture (`docs/ARCHITECTURE.md` §13).

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
