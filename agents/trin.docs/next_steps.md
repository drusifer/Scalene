# Next Steps

## Immediate Next Action
Sprint 4 Phase 4 UAT passed, handed to Morpheus. **Mandatory Smith gate next.**

## Waiting On
Morpheus (Phase 4 review) → Smith (mandatory gate — confirm the onboard-suggestion loop and exit-code verification hold up under her own check too) → Neo (Phase 5, once Smith clears).

## Planned Work (Sprint 4)
- [ ] Phase 5 UAT (Smith gate required): confirm `scg monitor`'s new resource panel reflects real cache content, no separate/duplicated bookkeeping (STORY-1005 AC).
- [ ] Standing lesson reconfirmed a fourth time this sprint: real subprocess/binary tests beat unit-test-level function calls for closing-the-loop claims. This phase's onboard-suggestion re-verification used the actual installed `scg`/`scalene-guard` binaries end-to-end, not just calling Python functions — caught nothing new this time, but it's the right default for "does the user-facing promise actually work" questions.

## Loose end (not blocking, from Sprint 3)
- [ ] Sprint 3 Phase 3's demo was never UAT'd, Sprint 3 was never formally closed. Revisit whenever convenient — doesn't block Sprint 4.
- [ ] `make judge-trace` cumulative flags were climbing last sprint. `make test-q` (the documented fix) still doesn't exist as a target — still a real tooling gap to raise with Bob/Mouse eventually.

---
*Last updated: 2026-07-15*
