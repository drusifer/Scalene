# Next Steps

## Immediate Next Action — READ THIS FIRST ON COLD START
**The `decide_access()` correction from the last session is DONE and implemented** — §15.2b's model (see `context.md`) is live in `src/scalene/resource_verifier.py` and `src/scalene/monitor_app.py`, 602/602 at `make test`, **not yet committed to git**. This work has gone through Neo's implementation but not yet Trin UAT / Morpheus review / Smith UX gate — that's the actual next step on cold start: continue the `*impl`-style Bloop chain (`*chat @trin *qa uat decide_access-correction` or resume via `*chat @trin` directly), not re-litigate the design again. The design itself should be treated as settled unless the user raises something new.

If Trin/Morpheus/Smith all pass: commit + ask the user before pushing (this repo's own established pattern — see e.g. `e6d3bbe`'s commit message for the style/scope convention).

**Also carried, lower priority**: the masking mechanism itself (mode=mask actually transforming/downgrading content instead of just blocking, e.g. "return only HTTP/exit status, not full content") was explicitly deferred by the user as "not demo-ready" — backlog item, not scoped to any sprint yet. `docs/ARCHITECTURE.md` §15.5 already flags masking's role as undecided; this adds a concrete design direction to that open question, not a resolution of it.

## Session summary (2026-08-07 → 2026-08-08, cold-start context)
Sprint 12 (E18) + 4 live-usage bugs + "trust but verify" (§15.2a) → committed/pushed as `e6d3bbe` → session cleared → **resumed 2026-08-08**: the §15.2a correction flagged at the end of the last session was worked through properly this time — traced the proposed fix by hand against the entire existing `decide_access()` test suite *before* implementing (caught that a naive reading would've broken STORY-1504's project-folder convenience feature), surfaced that concretely to the user instead of guessing a 3rd time, got the model simplified to binary in response, implemented it (§15.2b), added the Mode-responsive `RulesScreen` UX to match. 602/602 tests. Uncommitted.

## Waiting On
Trin's UAT pass on this session's uncommitted `decide_access()`/`RulesScreen` changes (in progress via the `*impl` Bloop chain — see `agents/CHAT.md` for the live handoff).

## Carried, not blocking (from `docs/ARCHITECTURE.md` §21.10)
- `ScanCache` freshness for a directory resource keys off the directory's own mtime (doesn't catch a nested file's *contents* changing deeper in the tree) — only matters if directory-target Allow rules become common.
- `Scanner.from_config()` has no `get_config()`/introspection counterpart — nothing concrete wants this yet.
- `PolicyRule.trust` has no CLI (`scg onboard --trust`) or TUI (Allow form) exposure yet — hand-authored in `scalene_policy.yaml` only.
- The pending-review auto-resolution (§21.9) only runs right after a review is explicitly resolved, not on every `poll_data()` tick — a hand-edited policy file won't retroactively clear now-covered reviews until the next resolution happens.
- `docs/ARCHITECTURE.md` §5's Onboarding sequence diagram is still stale (pre-existing, not touched this session either).
- `cache_refresh_worker.py` stays scoped to builtin scanners only (pre-existing, documented gap) — revisit only if a real config-declared scanner ever ships.

---
*Last updated: 2026-07-30*

## Immediate Next Action (prior, 2026-07-21)
Sprint 9 (E15) Phase 4 complete (last phase), handed to Trin for UAT. On re-invocation:
- If Trin/Smith find issues → fix within Phase 4's scope only.
- If they pass → nothing further for Neo this sprint. Sprint moves to close (Oracle groom → Smith end-to-end test → all-persona retro → Cypher launch) — not Neo's steps.

## Sprint 9 (E15) phase tracking — all 4 phases implemented
- [x] Phase 1 — Configurable Scanner Registry. `make test`: 349/349 (+CLI tests → 352).
- [x] Phase 2 — Hardcoded Restricted Paths. `make test`: 360/360.
- [x] Phase 3 — External Reputation Source. `make test`: 371→374/374 (Tank found+we fixed a real Auth-Key gap).
- [x] Phase 4 — Project-Folder Default. `make test`: 381/381. Smith's mandatory gate + final reviews pending.
