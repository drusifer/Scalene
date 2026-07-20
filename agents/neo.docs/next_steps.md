# Next Steps

## Immediate Next Action
Handed to Trin to re-verify the `--help` discoverability fix (2026-07-20) before Smith re-gates. The main sec16 review chain (Trin UAT → Morpheus review) already passed cleanly before this bug surfaced at Smith's gate.

## Waiting On
Trin's re-verification, then Smith's re-test/approval, then retro/Cypher launch (Sprint 7). Whoever picks this up next should read §16 in full — it explicitly supersedes §14.3 for the onboard CLI surface (§14's other sections still hold).

## Planned Work
- [x] Sprint 5 (E11) Phases 1-3 originally implemented against §14.4's masking model, all gated and approved.
- [x] sec15 rework: full replacement of the call-permission mechanism (rule-driven access control), implemented 2026-07-17, `make test` 266/266.
- [x] sec16 rework: `scg onboard` authors a `PolicyRule` in one call instead of only pre-seeding the cache, implemented (direct user session) + picked up/closed out via bob-protocol 2026-07-18, `make test` 289/289.
- [ ] **Not done, worth surfacing**: a real Trin UAT / Morpheus review / Smith gate pass specifically against the sec15 *and* sec16 code (the original Phase 3 gates were for the now-superseded masking design; §16 further changes the onboard CLI surface Smith's Gate 1/2 explicitly locked). If this session's work needs to go through Stage 3 close formally, that gate gap should be closed first, not skipped.
- [ ] `docs/USER_STORIES.md`/`task.md`'s STORY-1101-1105 *and* STORY-501 descriptions still describe designs sec15/sec16 superseded — not updated (Cypher's domain, not done as part of this engineering pass).

---
*Last updated: 2026-07-18*
