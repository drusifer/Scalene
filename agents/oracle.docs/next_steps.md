# Next Steps

## Immediate Next Action
Sprint 9 (E15) groom complete, handed to Smith for the sprint-close end-to-end test (2026-07-21). Nothing else in-flight for Oracle until retro.

## Waiting On
Smith's end-to-end test, then `*sprint retro`, then Cypher's launch.

## Planned Work
- [ ] `agents/CHAT.md` now at 47 live messages post-archive (2026-07-21) — check again at the next groom pass.
- [ ] Watch whether Cypher acts on the STORY-1001 staleness flag (`agents/oracle.docs/e10_story_staleness_flag.md`) — still open across multiple sprints now, worth resolving or explicitly deprioritizing rather than silently carrying forever.
- [ ] `docs/ARCHITECTURE.md` §5's stale "Onboarding" sequence diagram (flagged by Neo, Sprint 8 Phase 3) — still not fixed, carried again.
- [ ] No `*ora tldr` sweep has ever run on the Sprint 4 modules (`resource_verifier.py`, `scan_cache.py`, `scanner.py`, `cache_refresh_worker.py`) — standing item carried since Sprint 2's groom, still not picked up. Now also applies to E15's new modules (`reputation.py`'s new classes, `write_default_project_policy`).
- [ ] `docs/PRD.md`'s top status line was stale since Sprint 4 (fixed this pass) — worth checking it doesn't silently re-drift; consider whether it should just always defer to `USER_STORIES.md` rather than maintain parallel status text at all.

---
*Last updated: 2026-07-21*
