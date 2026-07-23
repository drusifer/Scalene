# Next Steps

## Immediate Next Action
E16 architecture written (`docs/ARCHITECTURE.md` §20, 2026-07-22), handed to Smith for Gate 2. On re-invocation: nothing further from me until Smith's Gate 2 verdict; if approved, hand to Mouse for phase breakdown, then review Mouse's plan (`*lead review sprint plan`) before Neo starts Phase 1.

## Waiting On
Smith's Gate 2 verdict on E16 architecture (§20). My own watch-items for Gate 2 to confirm landed: the STORY-1603 scope correction (block-events-only, not a full call log — flagged back to Cypher/Smith explicitly, §20.3), and the bell()/title attention-signal design (§20.4) answering Smith's Gate 1 note.

## Carried from E16 architecture (real, not sprint-specific)
- §20.3: STORY-1603 was storied as "the tool-call log" but only block events are actually logged today — logging every allowed call too would add unconditional hot-path I/O, an NFR question this project has been burned by assuming before (§13.3/13.5). Deferred, not built, flagged back to Cypher.
- §20.8: `_pending_reviews`' in-memory-only review-queue state doesn't survive a monitor restart — acceptable for v1 per the stateless-TUI-side precedent (sec15's `BlockEvent` docstring), revisit only if it's a real operator complaint.
- §20.6: STORY-601's isolation-mechanism question (local/Docker/cloud) is still not concretely resolved project-wide — STORY-1606 is the second story now blocked on the same still-open Tank question.

## My retro input (for whenever `*sprint retro` happens)
This sprint's real lesson, reinforced twice: writing the whole epic's architecture in one pass, ahead of any implementation, produced real corrections once Neo actually built against it (§18.1's cache_refresh_worker scope, §18.2's now-unreachable resource_verifier addition, a premature diagram entry the drift-guard test caught) — untested assumptions about how *existing* code behaves, only surfaced by tracing real control flow during implementation. Then Phase 4 itself got a live design pivot mid-gate-chain (the user asking to avoid an implicit special case after I'd already architected and gated one) — and that pivot itself surfaced a second real bug (the rule-shadowing hazard) that only existing code review would never have caught either, since it required tracing how `_write_rule()`'s append-only behavior interacts with a *new* broad default rule. Worth naming as a durable pattern: both "claims about existing code" and "claims about how two features interact" need the same verify-don't-assume discipline, and a mid-flight design correction is a legitimate reason to re-run the full gate chain, not a shortcut to skip it.

## Carried watch-items (still real, not sprint-specific)
- §17.7 (STORY-1406, deferred): scanning a tool call's *response* would directly revisit §15's `post_tool_use`-is-a-no-op rationale. Still not touched by E15 — §18.1-18.4 all operate on pre-call identification/scanning, same as everything before it.
- `docs/ARCHITECTURE.md` §5's stale Onboarding sequence diagram (flagged by Neo, Sprint 8 Phase 3) — 4th instance of diagram drift across sprints. Not fixed this pass (E15 didn't touch the onboarding flow's sequence, only its scanner layer) — still open, worth a real automated guard per the Sprint 8 retro backlog rather than another manual catch.
- New from this session: §18.1's deferred item (config-registered scanners can't yet use the subprocess-isolation boundary) — will need its own design pass whenever a real enterprise scanner is actually built, not assumed solved by §18.1's extension point alone.

---
*Last updated: 2026-07-21*
