# Next Steps

## Immediate Next Action
Sprint 4 Phase 2 UAT passed, handed to Morpheus. No Smith gate on Phase 2. Next Trin involvement is Phase 3 UAT (hook integration, Smith gate required) once Neo implements it — this is the largest/riskiest phase so far.

## Waiting On
Morpheus (Phase 2 review) → Neo (Phase 3 impl: hook_adapter.py integration, PolicyRule removal, first-sighting messaging) → me (Phase 3 UAT) → Smith (UX gate).

## Planned Work (Sprint 4)
- [ ] Phase 3 UAT (Smith gate required): re-run `tests/test_performance.py`'s <15ms NFR for real once resource identification + cache lookup are in the hot path — Smith's Gate 2 watch-item, don't assume compatible. Also confirm `PolicyRule`/`allowlist` is genuinely fully removed (grep, don't trust), and that the first-sighting message reads as "not yet verified" distinctly from a known-bad decision (Smith's own note, but worth an independent read before it even reaches her).
- [ ] Phase 4 UAT (Smith gate required): a real cache-store-corruption scenario and a real scanner-crash scenario both need to actually produce the documented non-zero exit — don't accept "the code looks like it would" without triggering both for real.
- [ ] Standing lesson reconfirmed twice now: verify behavioral/concurrency claims by actually running the code, not just reading it. Phase 1: WebFetch/FileScanner URL collision, code-reading alone would likely have missed it. Phase 2: added a real cross-process concurrency test (`ProcessPoolExecutor`, 8 real OS processes) for the dedup claim rather than accepting Neo's same-process sequential test as sufficient — ran it 5x to rule out a lucky pass on a genuine race, not just once.

## Loose end (not blocking, from Sprint 3)
- [ ] Phase 3 UAT: run `tests/test_demo.py`, confirm no real network egress occurs via code inspection. Sprint 3 was never formally closed — revisit whenever convenient, doesn't block Sprint 4.
- [ ] `make judge-trace` cumulative flags were climbing last sprint (11 → 25), mostly `AP-MAKE-PIPE`/`AP-RAW-VENV` from my own ad hoc verification commands. This phase's UAT used `make test` (mkf-wrapped) instead of a piped raw venv call — keep that habit. `make test-q` (the documented fix) still doesn't exist as a target; still a real tooling gap to raise with Bob/Mouse.

---
*Last updated: 2026-07-14*
