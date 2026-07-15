# Next Steps

## Immediate Next Action
Filed a real bug (Last Scanned column truncation) to Trin for triage. Phase 5 gate is withheld until it's fixed and re-verified — I'll re-run the same real-screenshot check once Trin/Neo say it's addressed, not just trust a "fixed" claim.

## Waiting On
Trin (triage) → Neo (fix) → Trin (re-verify) → me (re-test the real render, then gate).

## Planned Work
- [ ] Once the fix comes back: re-render the real screenshot myself at the same 120-col width and confirm the column is actually legible now, not just that a test asserts a shorter string.
- [ ] Low-priority, non-blocking, carried from Phase 4: the fatal-exit message's tail embeds a raw JSON-parser error string (not a traceback, but not fully plain-language either); the onboard success message shows the internal `scanner_name:identity` cache-key format. Neither urgent — revisit only if there's a natural polish pass.
- [ ] Sprint 3's Phase 3 demo gate precedent still applies whenever Sprint 3 is formally closed (retro not yet done) — not urgent, just not forgotten.
- [ ] Sprint 4 close (once Phase 5's gate clears): end-to-end user testing across the whole sprint (`*user test` + `*user feedback`), then the all-persona retro.

---
*Last updated: 2026-07-15*
