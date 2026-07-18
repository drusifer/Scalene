# Next Steps

## Immediate Next Action
Nothing in-flight for Neo. The sec15 rework (rule-driven access control) is implemented and all 266 tests pass, but it happened as direct engineering work with the user, not through the Bloop chain — Phase 1-3's original Trin UAT / Morpheus review / Smith gate never re-ran against this replacement. If the sprint resumes through the formal protocol, that review debt is real and should be flagged, not silently treated as already covered.

## Waiting On
Nothing. Whoever picks this up next (any persona) should read `docs/ARCHITECTURE.md` §15 first — it's the actual current design, superseding §14.4 for the call-permission decision (§14's other sections — §14.1-14.3, 14.5-14.7 — still hold, only masking's role changed).

## Planned Work
- [x] Sprint 5 (E11) Phases 1-3 originally implemented against §14.4's masking model, all gated and approved.
- [x] sec15 rework: full replacement of the call-permission mechanism (rule-driven access control), implemented 2026-07-17, `make test` 266/266.
- [ ] **Not done, worth surfacing**: a real Trin UAT / Morpheus review / Smith gate pass specifically against the sec15 code (the original Phase 3 gates were for the now-superseded masking design). If this session's work needs to go through Stage 3 close formally, that gate gap should be closed first, not skipped.
- [ ] `docs/USER_STORIES.md`/`task.md`'s STORY-1101-1105 descriptions still describe the masking-centric design — not updated to match sec15 (Cypher's domain, not done as part of this engineering pass).

---
*Last updated: 2026-07-17*
