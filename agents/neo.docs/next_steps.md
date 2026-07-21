# Next Steps

## Immediate Next Action
Phase 3 complete, handed to Trin. Per Mouse's plan, Phase 3 gets no separate Smith gate — Trin re-runs `docs/GETTING_STARTED.md`'s onboarding section verbatim (real doc-touching-phase standard) instead, then this closes out to Oracle/Smith/retro/Cypher for the whole sprint.

## Waiting On
Trin's Phase 3 verification. She should know: `onboard()`/`_resolve_resource()` were **not** deleted (see current_task.md's scope revision — they cover real, distinct URI-scheme-validation behavior with no equivalent in the new flow, kept deliberately, not an oversight). Also carried: `docs/ARCHITECTURE.md` §5's Onboarding sequence diagram is stale (pre-dates even sec16) — flagged for Morpheus, not fixed by me, since it's outside Mouse's named Phase 3 scope and diagram-drift calls have historically been Morpheus's to make.

## Planned Work
- [x] Sprint 5 (E11) Phases 1-3 originally implemented against §14.4's masking model, all gated and approved.
- [x] sec15 rework: full replacement of the call-permission mechanism (rule-driven access control), implemented 2026-07-17, `make test` 266/266.
- [x] sec16 rework: `scg onboard` authors a `PolicyRule` in one call instead of only pre-seeding the cache, implemented (direct user session) + picked up/closed out via bob-protocol 2026-07-18, `make test` 289/289.
- [ ] **Not done, worth surfacing**: a real Trin UAT / Morpheus review / Smith gate pass specifically against the sec15 *and* sec16 code (the original Phase 3 gates were for the now-superseded masking design; §16 further changes the onboard CLI surface Smith's Gate 1/2 explicitly locked). If this session's work needs to go through Stage 3 close formally, that gate gap should be closed first, not skipped.
- [ ] `docs/USER_STORIES.md`/`task.md`'s STORY-1101-1105 *and* STORY-501 descriptions still describe designs sec15/sec16 superseded — not updated (Cypher's domain, not done as part of this engineering pass).

---
*Last updated: 2026-07-18*
