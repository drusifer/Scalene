# Next Steps

## Immediate Next Action
None for Morpheus right now. `*sprint go` was invoked by the user to formalize the §13.8 design as a real sprint (likely "Sprint 5" / a new epic, call it E11 for now — not yet officially numbered by Cypher). **Cypher is next**: write user stories capturing what §13.8 already designed, so it goes through Smith's Gate 1 like every other sprint has.

## Waiting On
Cypher (write E11 stories) → Smith (Gate 1) → Morpheus (formal architecture pass — §13.8 is a strong draft but has an explicit "not yet decided" list to resolve: exact JSONPath for "any argument," scanner-inference rules, on-disk schema, `scg onboard` mapping) → Smith (Gate 2) → Mouse (phase breakdown) → Morpheus (plan review) → implementation Bloop.

## Planned Work
- [ ] When architecture comes back to me (post-Cypher-stories, pre-Gate-2): resolve §13.8's explicit open questions into concrete decisions, not leave them as TBD through implementation.
- [ ] Whichever phase implements this: re-verify the latency/NFR story again once rule-matching (regex evaluation per call) is back in the hot path — same "measure, don't assume" discipline as Sprint 4 Phase 2's finding. Rule matching could plausibly cost more than the current hardcoded scanner `identify()` methods, especially if a project accumulates many rules.
- [ ] Flag to whoever phases this: this changes a shipped, closed-sprint on-disk format (`scan_cache.json`'s key scheme, if URL identity moves from host to full-path) and `scalene_policy.yaml`'s schema (allowlist returns, differently shaped) — needs a real migration/compatibility story, not just "old projects re-onboard everything." Not addressed in §13.8, worth surfacing at Cypher's story-writing stage.

---
*Last updated: 2026-07-17*
