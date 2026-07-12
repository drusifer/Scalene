# Current Task

**Status:** `*prompt update judge session` (revised, 2026-07-10) complete — Trin verified, loop closed TES=98.
**Assigned to:** N/A (no active task)
**Started:** 2026-07-10

## Task Description (most recent): `*prompt update judge session` (revised)
Address Smith's 2026-07-10 findings (bugs S-003, S-004) plus wire the newly-fixed `make judge-trace` tool into the judge loop's own docs so future runs use real data by default.

## Progress
- [x] Wired `make judge-trace` into `agents/skills/judge/SKILL.md` Step 1 as the required method — explicitly calls out that hand-reconstructing from `agents/CHAT.md` is wrong (CHAT.md is process-adherence evidence, not tool-call evidence)
- [x] Wired the same into `agents/trin.docs/SKILL.md`'s Tooling section
- [x] S-003/S-004 (habitual `make test|tail`, via-bypass — both real violations of already-correct, already-written rules, not documentation gaps): added concrete incident anchors citing today's real counts (39, 13) to `agents/neo.docs/SKILL.md`, and gave Trin's UAT gate an actual checkpoint — `make judge-trace` now runs before any phase sign-off (`agents/trin.docs/SKILL.md` Test Workflow step 4) — instead of relying on recall of prose that was already correct
- [x] Recorded a durable lesson in `agents/oracle.docs/lessons.md`: "A Written Rule Nobody Checks Is Not an Enforced Rule"
- [x] Handed to Trin, who verified via rerun + confirmed `make test` still green

## Task Description (prior): `*prompt update judge session` (2026-07-08/09 loop)
Address the 3 findings from Smith's first `*qa judge session` TES scoring (S1-001, S1-002, S1-003).

## Progress
- [x] S1-001: added a concrete anchor sentence to `agents/skills/bloop/SKILL.md` rule #6 (No Sub-Skill Re-Invocation)
- [x] S1-002: saved a persistent cross-session memory (`feedback_git_stash_care.md`) — not a project-local skill edit, since the lesson isn't Scalene-specific
- [x] S1-003: added a conditional `3b` Smith UX-gate step to the `*impl` chain in `agents/skills/bloop/SKILL.md`, mirroring the existing conditional Tank step, plus a rule that prior-plan "Smith re-engages" notes make that phase's step mandatory
- [x] Ran `make test` — 77/77 still passing (doc-only changes, no code touched)

## Blockers
None

## Oracle Consultations
None yet

---
*Last updated: 2026-07-10*
