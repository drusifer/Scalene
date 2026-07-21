# Next Steps

## Immediate Next Action
`*user test E14` complete (2026-07-21) — full sprint end-to-end PASSED, encoded as a permanent test (`TestE14EndToEndUserJourney`) after a user correction against ad-hoc bash verification. Handed to all for `*sprint retro`.

## Waiting On
Nothing blocking. My retro input: I'd already been corrected once this session (mid-sprint, an individual finding) for ad-hoc bash verification, then repeated the same shortcut at the full-sprint-close scale before being corrected again. Worth internalizing harder, not just for this session: even (especially) a "just confirming the whole thing works" moment at sprint close should default to a real test, same standard as any single bug repro — the scale of the check doesn't change the rule.

## Retro input carried from Sprint 7 (for whenever the next retro happens after this one)
Sprint 7's lesson: "implement fast with the user, gate formally after" is validated as workable here — but only because the gate chain runs every time, not skipped because the code already works.

## Retro input carried from Sprint 7 (for whenever the next retro happens)
This sprint (Sprint 7) was the second time in a row (after sec15) that a direct-user-design correction shipped ahead of formal review, and the second time in a row the after-the-fact gate chain caught something real. Worth naming as validation that "implement fast with the user, gate formally after" is a workable pattern here — but only because the gate chain is actually run every time, not skipped because the code already works.

## Retro input carried from sec15 (for whenever `*sprint retro` happens next)
Nothing blocking. My own retro input (for `*sprint retro`): the central lesson of this sprint is that my mandatory Phase 3 gate — specifically the instruction to *run the software adversarially*, not just review it — is what caught a defect that fully passed code review and every unit test written against its own acceptance criteria. Worth naming as validation that the gate's "actually run it" requirement isn't ceremony.

## My retro input (for `*sprint retro`)
- The resource-panel truncation bug is worth naming specifically as this sprint's clearest UX-process lesson: a real rendered screenshot caught something no amount of row-count/content-level testing would have, and the first fix attempt (string-shortening) genuinely wasn't obviously wrong until re-tested against the real render, not a new unit test. Recorded in `agents/oracle.docs/lessons.md`. Worth normalizing "screenshot-check UI changes before approving" as standard practice, not just for TUI-heavy sprints.
- This sprint converged on "use the real installed binaries, not just Python-function-level tests" as the default verification standard for anything touching the live hook contract or onboarding loop — Neo's exit-code dogfooding, Trin's Phase 4 binary-level re-verification, and this end-to-end test all did this. Worth keeping as the default going forward, not something to relax once the novelty wears off.

## Planned Work (Sprint 4 close)
- [ ] Low-priority, non-blocking, still carried: fatal-exit message's raw JSON-parser text tail, onboard success message's internal cache-key format.
- [x] Sprint 3 formally closed 2026-07-16.

## Immediate Next Action (Sprint 5 / E11)
Gate 2 approved. Waiting on Mouse's phase breakdown, then implementation. On re-invocation:
- Any phase Mouse marks Smith-gated: review per this epic's precedent (§14, e11_gate1/gate2_review.md).
- At sprint close: run the mandatory end-to-end user test — actually verify (a) `scg onboard --target` still works as a single flag, (b) a mask event on a previously-untainted session produces the same systemMessage/audit-log signal as before, (c) the `NFR-Perf-UnconditionalScan` latency claim holds for real, not just per-phase unit tests.

---
*Last updated: 2026-07-17*
