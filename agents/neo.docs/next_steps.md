# Next Steps

## Immediate Next Action
Nothing for Neo right now — Sprint 4 Phase 4 is handed off to Trin for UAT. **This phase has a mandatory Smith gate** — she specifically flagged two things to check: the onboard-suggestion loop must be genuinely closed (it is), and the exit code must be verified for real, not assumed (it is — done empirically, see context.md).

## Waiting On
Trin's UAT on Phase 4 → Morpheus's review → **Smith's gate (required)** → Phase 5.

## Planned Work (Sprint 4, in order — see task.md for full phase breakdown)
- [x] Phase 1: **Trin UAT PASSED (1 fix round), Morpheus APPROVED.**
- [x] Phase 2: **Implemented, Trin UAT PASSED, Morpheus APPROVED with an escalated latency finding — resolved by user decision (accept cost, revise NFR).**
- [x] Phase 3: hook integration + first-sighting messaging + split NFR. **Trin UAT PASSED, Morpheus APPROVED, Smith's gate APPROVED** (user decision: accept the onboard-suggestion regression window, proceed to Phase 4).
- [x] Phase 4: `scg onboard` re-scope (closes the regression) + fatal-exit handling (exit code verified empirically as 2, not assumed). **Implemented 2026-07-15, awaiting Trin UAT + Morpheus review + Smith's mandatory gate.**
- [ ] Phase 5 (next once Smith's Phase 4 gate clears): `scg monitor` resource-cache panel, reads `.scalene/scan_cache.json` directly (same poll-based pattern as existing panels). Smith gate required.
- [ ] `ARCHITECTURE.md` §4's class diagram is still stale (still shows `PolicyRule`/`allowlist`) — flagged twice now (Phase 3, Phase 4), still not done. Should happen in Phase 5 or as a standalone cleanup — don't let it linger a third time.
- [ ] Loose end from Sprint 3 (not blocking, not forgotten): Sprint 3 Phase 3's demo was never UAT'd by Trin, Sprint 3 was never formally closed. Revisit whenever convenient.
- [ ] Dev-environment note, not a task: this repo's own `.claude/settings.json` wires the real, editable-installed `scalene-guard` as this session's own hook — `.scalene/scan_cache.json` in the repo root will legitimately fill up during any dev session here, that's not a leak. It was also directly useful this phase: real empirical verification of the exit-code question, not just documentation reading.

---
*Last updated: 2026-07-15*
