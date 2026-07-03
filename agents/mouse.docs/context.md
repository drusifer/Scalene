# Agent Local Context: Mouse

## Recent Decisions
- Broke Sprint 1 into 4 phases (Foundations → Hook Adapter/Masking → Onboarding/Isolation → Packaging/Perf/Full UAT), each 3 tasks, sequenced by dependency (masking needs the policy engine; onboarding only needs the config engine, not the hook adapter, so it could theoretically parallel Phase 2 — kept it sequential for now since this is a single-implementer sprint, not parallel teams).
- **No Tank phase** — per architecture (`docs/ARCHITECTURE.md` §9), `SCALENE_BYPASS` is subprocess-local, not CI/system-scoped, and STORY-501's original external-API concern was resolved by Morpheus's `LocalHeuristicChecker` decision. Documented this explicitly in `task.md` so it doesn't look like an oversight, and flagged to reassess if onboarding scope grows to include a real threat-intel API later.

## Key Findings
- Each of the 9 user stories maps cleanly to exactly one phase task except STORY-501, which spans two tasks (3.1 the checker/scan itself, 3.3 the confirmation UX Smith asked for at Gate 1) — split deliberately so the UX-visibility work doesn't get treated as an afterthought bundled into 3.1.
- Phase 4 task 4.2 (perf verification) exists specifically because Smith flagged the <15ms NFR as untested-so-far at Gate 2 — made it an explicit task rather than assuming Trin would catch it incidentally during UAT.

## Important Notes
- `task.md` created at repo root as the sprint task board (single source of truth per Mouse's SKILL.md).
- This is sprint-planning Step 3 of `*plan sprint`. Next: Morpheus reviews the phase plan (Step 3a) against `docs/ARCHITECTURE.md` before it's locked. No Tank step (3b) needed per the no-Tank-phase decision above.

---
*Last updated: 2026-07-02*
