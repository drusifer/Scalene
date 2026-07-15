# Next Steps

## Immediate Next Action
Sprint 4 Phase 5 UAT passed, handed to Morpheus. **Mandatory Smith gate next — last Sprint 4 phase.** Once that clears, Sprint 4 implementation is complete and moves to Stage 3 close.

## Waiting On
Morpheus (Phase 5 review) → Smith (mandatory gate) → Sprint 4 close (Oracle groom → Smith end-to-end test → all-persona retro → Cypher launch).

## Planned Work (Sprint 4 close, once Phase 5 gate clears)
- [ ] Smith's end-to-end user testing across the whole sprint (`*user test` + `*user feedback`) — this is broader than any single phase gate, covers the full E10 feature as a real user would experience it.
- [ ] My own retro input when `*sprint retro` happens: test coverage/regression themes across all 5 phases — real cross-process concurrency test (Phase 2), real installed-binary verification for the fatal-exit/onboard-suggestion loop (Phase 4), row-content-not-just-count gaps found twice this sprint (Sprint 2's mask feed, this phase's resource panel) — worth naming as a recurring pattern in retro, not just fixing case-by-case.

## Loose end (not blocking, from Sprint 3)
- [ ] Sprint 3 Phase 3's demo was never UAT'd, Sprint 3 was never formally closed. Should probably resolve before or during Sprint 4's own close — two open sprints stacking up gets confusing.
- [ ] `make judge-trace` cumulative flags were climbing last sprint. `make test-q` (the documented fix) still doesn't exist as a target — still a real tooling gap to raise with Bob/Mouse eventually.

---
*Last updated: 2026-07-15*
