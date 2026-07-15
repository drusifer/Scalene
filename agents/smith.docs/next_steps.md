# Next Steps

## Immediate Next Action
Phase 3 gate approved, handed to Neo for Phase 4. My next involvement is Phase 4's mandatory gate (`scg onboard` re-scope + fatal-exit handling).

## Waiting On
Neo (Phase 4 impl) → Trin (UAT) → Morpheus (review) → me (gate, required).

## Planned Work
- [ ] Phase 4 gate: **the onboard-suggestion regression must actually be closed by this phase** — confirm `tests/test_onboard_suggestion_e2e.py` is un-skipped and genuinely passing again, not just that `scg onboard`'s CLI got new flags. This is the direct payoff of accepting the Phase 3 window; if it's not closed here, escalate immediately rather than letting it slide to Phase 5.
- [ ] Personally verify (not assume) what a non-zero `scalene-guard` exit actually does in a real Claude Code session — same standard as the earlier schema-fix work, this is explicitly flagged as unverified-until-checked in the architecture.
- [ ] Confirm the fatal-exit message is genuinely plain-language (no raw traceback) for both failure modes (cache-store corruption, scanner crash).
- [ ] Phase 5 gate: confirm `scg monitor`'s new resource panel reads clearly, no jargon, consistent with the existing Sessions/Mask-events panels' style.
- [ ] Sprint 3's Phase 3 demo gate precedent still applies whenever Sprint 3 is formally closed (retro not yet done) — not urgent, just not forgotten.

---
*Last updated: 2026-07-14*
