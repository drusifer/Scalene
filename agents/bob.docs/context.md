# Agent Local Context: Bob

## Recent Decisions
- `*prompt update judge session` (2026-07-09): addressed all 3 findings from Smith's session TES scoring.
  - **S1-001** (double `Skill(make)` call): rule #6 in `agents/skills/bloop/SKILL.md` was already explicit and was still violated — added a concrete "this actually happened" anchor sentence rather than more abstract rule text, since the rule text alone clearly wasn't sufficient the first time.
  - **S1-002** (`git stash -u` care lapse): not project-specific, so fixed via a persistent cross-session memory entry (`feedback_git_stash_care.md`) rather than a project skill edit — a skill file only this project would see is the wrong scope for a general git-safety lesson.
  - **S1-003** (Smith's planned UX gate never ran): this was the substantive one. The `*impl` chain in `agents/skills/bloop/SKILL.md` had no Smith step at all, so any sprint plan that wrote "Smith re-engages post-Phase-N" was writing a promise the chain couldn't keep. Added a conditional `3b` Smith UX-gate step (mirroring the existing conditional Tank step), with an explicit rule that a prior planning artifact's "Smith re-engages" note makes that phase's Smith step **mandatory**, not just a default heuristic.

## Key Findings
- Two of the three findings were "the rule already existed and was still violated" (S1-001) vs. "the rule never existed" (S1-003) — different root causes needing different fixes. More prose doesn't help the first kind; concrete anchoring might. A missing chain step needs an actual structural addition, which is what S1-003 got.
- Didn't touch anything in `src/scalene/` or the Makefile — none of the 3 findings were code bugs, matching Smith's routing (all → Bob, none → Neo).

## Important Notes
- Sprint 1 is closed but S1-003's retroactive fix (running an actual `*user test` against the real `scalene-guard` binary) is still open — Smith's `next_steps.md` tracks this, not mine.

---
*Last updated: 2026-07-09*
