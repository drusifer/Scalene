# Next Steps

## Immediate Next Action
Sprint 4 Phase 1 UAT passed (after 1 fix round), handed to Morpheus. No Smith gate on Phase 1. Next Trin involvement is Phase 2 UAT (scan cache store) once Neo implements it.

## Waiting On
Morpheus (Phase 1 review) → Neo (Phase 2 impl: `.scalene/scan_cache.json`) → me (Phase 2 UAT).

## Planned Work (Sprint 4)
- [ ] Phase 2 UAT: real repeated-invocation test proving no orphaned `Popen` processes (task.md's explicit exit-criteria addition for Phase 2) — don't accept a code-read claim on this one, actually spawn and check process state.
- [ ] Phase 3 UAT (Smith gate required): re-run `tests/test_performance.py`'s <15ms NFR for real once resource identification + cache lookup are in the hot path — Smith's Gate 2 watch-item, don't assume compatible.
- [ ] Standing lesson reconfirmed this phase: verify behavioral claims by actually running the code (`python -c` repro), not just reading it — that's exactly how Phase 1's WebFetch/FileScanner collision bug was caught before it shipped, code-reading alone would likely have missed it since the regex looked reasonable in isolation.

## Loose end (not blocking, from Sprint 3)
- [ ] Phase 3 UAT: run `tests/test_demo.py`, confirm no real network egress occurs via code inspection. Sprint 3 was never formally closed — revisit whenever convenient, doesn't block Sprint 4.
- [ ] `make judge-trace` cumulative flags were climbing last sprint (11 → 25), mostly `AP-MAKE-PIPE`/`AP-RAW-VENV` from my own ad hoc verification commands. This phase's UAT used `make test` (mkf-wrapped) instead of a piped raw venv call — keep that habit. `make test-q` (the documented fix) still doesn't exist as a target; still a real tooling gap to raise with Bob/Mouse.

---
*Last updated: 2026-07-14*
