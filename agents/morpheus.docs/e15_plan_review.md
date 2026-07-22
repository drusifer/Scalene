# Morpheus — `*lead review sprint plan` — E15 (2026-07-21)

Reviewed Mouse's 4-phase breakdown (`task.md`, Sprint 9) against `docs/ARCHITECTURE.md` §18.

## Alignment check
- Phase 1 (1.1-1.3) covers §18.1 completely: `load_scanners()`, `PolicyConfig.scanners`, the validation-move, and the threading change across `resource_verifier.py`/`onboard.py`/`cache_refresh_worker.py`. Correctly flagged as no-gate (no new CLI surface).
- Phase 2 (2.1-2.2) covers §18.2 completely, including the shared `is_hardcoded_restricted()` helper so `FileScanner` and `resource_verifier.py` can't drift independently.
- Phase 3 (3.1-3.3) covers §18.3 completely, and correctly sequences the required Tank review last within the phase, per standing protocol — not skipped, not merged into Neo's task.
- Phase 4 (4.1-4.3) covers §18.4 completely, including the `project_root` wiring in *both* `cli.py` branches (the detail that makes this apply to a genuinely zero-config new project, not just ones with an existing policy file) — this was the easiest part of §18.4 to under-specify, and Mouse's task 4.1 named it explicitly. Good.

## Sequencing
Mouse's own plan flags that Phases 2-4 depend on Phase 1 only incidentally (shared `PolicyConfig` fields), not on each other. Agreed — confirmed against §18 myself: nothing in §18.2/18.3/18.4's design reads any output of another. The explicit note that Phase 3 (Tank-gated) and Phase 4 (Smith-gated) could reorder if Tank's review runs long is the right call to make *now*, not discover mid-sprint — approved as written.

## Gate placement
No objection. Phase 4 carrying the mandatory Smith gate is correct — it's where STORY-1504's discoverability hard requirement actually gets built, same precedent as Sprint 8 putting its mandatory gate wherever the real interactive/user-facing surface landed, not by rote position.

## Verdict

**APPROVED. Sprint 9 plan LOCKED.** No adjustment requested. Handing Phase 1 to Neo.
