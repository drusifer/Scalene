# Bug S1-003: Smith's planned post-Phase-2 UX test gate never ran

**Severity**: P2 — Sprint 1 was declared closed without a planned quality gate having executed
**Filed by**: Smith
**Route to**: Bob (process/chain-definition gap, not a code bug)

---

## Reproduction

`task.md`'s Notes section (written by Mouse, approved by Morpheus, 2026-07-02) explicitly states:

> "Smith re-engages post-Phase 2 for `*user test` against real hook behavior (not just spec review)."

Smith's own `next_steps.md` from Gate 2 (2026-07-02) recorded the same expectation:

> "Run `*user test` against the real hook adapter once it exists"

Sprint 1 executed all 4 phases via `/bloop *impl Sprint 1` and closed successfully — but Smith was never invoked again after Gate 2. No `*user test` occurred against the real `pre_tool_use`/`post_tool_use` behavior once it existed (Phase 2 onward).

## Expected

Either Smith runs a real UX test pass on the hook adapter post-Phase-2 (as planned), or the plan is explicitly revised (by Mouse/Morpheus) to drop that gate with a documented reason.

## Actual

The gate silently never happened. `task.md` and Morpheus's final Phase 4 review both say Sprint 1 is closed with no mention that this planned Smith gate was skipped.

## Root Cause

The `/bloop *impl <phase>` chain, as defined in `agents/skills/bloop/SKILL.md`, is `Neo → Trin → Morpheus → [Tank if deploy in scope] → [context check]`. **Smith is not a step in the `*impl` chain at all.** Mouse/Morpheus documented an expectation in `task.md` that the executable process they were about to run doesn't actually include. The gap is a mismatch between the sprint plan's stated expectations and the loop definition that executed it, not a case of the agent forgetting a step mid-session.

## Impact

Sprint 1 shipped a working DLP hook adapter with 77 passing unit/perf tests, but zero UX/usability testing against real hook behavior — only spec-level review (Gate 1/2) ever happened. This is a real quality gap for a tool whose entire value proposition is not disrupting the developer's workflow (STORY-401's "not block the call... workflow isn't interrupted").

## Recommended Fix

Bob should reconcile this for future sprints: either (a) add an explicit optional Smith step to the `*impl` chain definition when a phase is UX-relevant (mirroring how Tank is already conditionally included for deploy-scoped phases), or (b) have Mouse's phase-breakdown step cross-check any "re-engage persona X" notes against the actual loop chain being used, and flag mismatches before the sprint starts rather than after it closes. Given Sprint 1 already shipped, recommend a lightweight retroactive `*user test` pass against the real `scalene-guard` binary before the next sprint starts, rather than leaving this gap open indefinitely.
