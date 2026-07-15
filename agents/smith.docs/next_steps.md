# Next Steps

## Immediate Next Action
Full sprint end-to-end test passed. Handed to all personas for `*sprint retro`. My own retro input is already drafted below.

## Waiting On
All-persona retro → Cypher launch.

## My retro input (for `*sprint retro`)
- The resource-panel truncation bug is worth naming specifically as this sprint's clearest UX-process lesson: a real rendered screenshot caught something no amount of row-count/content-level testing would have, and the first fix attempt (string-shortening) genuinely wasn't obviously wrong until re-tested against the real render, not a new unit test. Recorded in `agents/oracle.docs/lessons.md`. Worth normalizing "screenshot-check UI changes before approving" as standard practice, not just for TUI-heavy sprints.
- This sprint converged on "use the real installed binaries, not just Python-function-level tests" as the default verification standard for anything touching the live hook contract or onboarding loop — Neo's exit-code dogfooding, Trin's Phase 4 binary-level re-verification, and this end-to-end test all did this. Worth keeping as the default going forward, not something to relax once the novelty wears off.

## Planned Work (Sprint 4 close)
- [ ] Low-priority, non-blocking, still carried: fatal-exit message's raw JSON-parser text tail, onboard success message's internal cache-key format.
- [ ] Sprint 3 was never formally closed — should resolve before or during Sprint 5, whenever that starts.

---
*Last updated: 2026-07-15*
