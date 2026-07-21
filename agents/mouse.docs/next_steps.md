# Next Steps

## Immediate Next Action
Sprint 8 (E14) 3-phase breakdown written to `task.md`, handed to Morpheus for plan review.

## Waiting On
Morpheus's `*lead review sprint plan` verdict.

## Planned Work
- [ ] Track the single required Smith gate this sprint (Phase 2 only — Phase 1 is internal, Phase 3 is doc/demo reconciliation with Trin re-verification instead of a full gate).
- [ ] Watch Phase 2 closely at UAT — Trin needs to run the real interactive CLI (confirmation prompt, `--yes`, `--only` including a deliberately-wrong identity, the no-TTY fail-fast case, and the mixed-sensitivity `--only`-twice case Smith flagged at Gate 2), not just unit-test the library functions.
- [ ] Watch Phase 3 at UAT: Trin re-runs `docs/GETTING_STARTED.md`'s onboarding section verbatim against the real installed binary — must match byte-for-byte, same standing practice as every prior doc-touching phase.
- [ ] Prior Sprint 5 stale-phase-description issue (superseded mid-gate by sec15) is a closed, historical item now — Sprint 5 was formally closed 2026-07-18. No longer a carry-forward.

---
*Last updated: 2026-07-20*
