# Next Steps

## Immediate Next Action
Sprint 4 Phase 3 UAT passed, handed to Morpheus. **This phase has a mandatory Smith gate** — after Morpheus's review, make sure Smith gets the onboard-suggestion regression flagged explicitly and prominently, not buried in a routine handoff.

## Waiting On
Morpheus (Phase 3 review) → Smith (mandatory UX gate — real behavior/copy change, plus the confirmed onboard-suggestion regression needs her explicit call) → Neo (Phase 4, once Smith clears).

## Planned Work (Sprint 4)
- [ ] Phase 4 UAT (Smith gate required): a real cache-store-corruption scenario and a real scanner-crash scenario both need to actually produce the documented non-zero exit — don't accept "the code looks like it would" without triggering both for real. Also confirm `test_onboard_suggestion_e2e.py` is un-skipped and genuinely passing again once `scg onboard` is re-scoped — that's the test that will finally close the loop Neo/I both confirmed broken in Phase 3.
- [ ] Phase 5 UAT (Smith gate required): confirm `scg monitor`'s new resource panel reflects real cache content, no separate/duplicated bookkeeping (STORY-1005 AC).
- [ ] Standing lesson reconfirmed a third time this sprint: verify behavioral/regression claims by actually running the code, not trusting a written explanation even when it's well-documented. Phase 3: bypassed Neo's `@unittest.skip` decorator and ran the onboard-suggestion test body directly rather than accepting his skip-reason text at face value — reproduced the exact same failure independently.

## Loose end (not blocking, from Sprint 3)
- [ ] Phase 3 UAT: run `tests/test_demo.py`, confirm no real network egress occurs via code inspection. Sprint 3 was never formally closed — revisit whenever convenient, doesn't block Sprint 4.
- [ ] `make judge-trace` cumulative flags were climbing last sprint (11 → 25), mostly `AP-MAKE-PIPE`/`AP-RAW-VENV` from my own ad hoc verification commands. This phase's UAT used `make test` (mkf-wrapped) instead of a piped raw venv call — keep that habit. `make test-q` (the documented fix) still doesn't exist as a target; still a real tooling gap to raise with Bob/Mouse.

---
*Last updated: 2026-07-14*
