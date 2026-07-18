# Next Steps

## Immediate Next Action (superseded — read this first on cold start)
My 3-phase breakdown for Sprint 5 (`task.md`) was against §14.4's masking design and got fully implemented+gated through Phase 3 — but Phase 3's gate found a real gap that led to replacing the entire mechanism (`docs/ARCHITECTURE.md` §15, rule-driven access control). Implemented directly with the user, not phased through me. `task.md`'s Sprint 5 phase descriptions are now stale relative to what actually shipped.

## Waiting On
Nothing blocking. If this resumes formally, `task.md`'s Sprint 5 section needs a real update to reflect the sec15 rework (or an explicit note that it superseded the original 3-phase plan) — hasn't been done.

## Planned Work
- [ ] Track the single required Smith gate this sprint (Phase 3 only — Phases 1-2 are internal/schema-only, no user-facing surface changes).
- [ ] Watch Phase 3 closely at UAT — Trin needs to confirm the existing mask systemMessage/audit-log signal still fires correctly for a newly-triggered mask (a call that used to be silently skipped), not just that new tests pass.
- [ ] Sprint 3's prior "never formally closed" issue is resolved (closed 2026-07-16) — no longer a carry-forward item.

---
*Last updated: 2026-07-17*
