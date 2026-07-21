# Next Steps

## Immediate Next Action
Sprint 8 (E14) formally closed 2026-07-21 — Trin's Phase 3 verbatim recheck passed, Oracle groomed, Smith's end-to-end test passed, retro compiled, Cypher launched. Nothing in-flight for Neo.

## Waiting On
Nothing. **User direction (2026-07-21): the next sprint will do more scanner work.** Whoever picks up implementation should read `docs/ARCHITECTURE.md` §17 in full first — it's the current onboard design (`identify_targets()`/`onboard_targets()`/`_confirm_targets()`/`_list_inventory()` in `onboard.py`), and note that `onboard()`/`_resolve_resource()` are a deliberately-kept, separate, still-tested single-URI convenience path, not dead code to clean up.

## Carried, not blocking
- `docs/ARCHITECTURE.md` §5's Onboarding sequence diagram is stale (pre-dates even sec16 — still shows the removed `jsonpath`/`pattern`/`allowlist` flow). Flagged, not fixed — Morpheus's or whoever's call when the scanner sprint next touches onboarding.
- Cypher's `next_steps.md` has the full earmarked backlog for the next sprint (STORY-1405/1406, Smith's CLI UX findings, the diagram above) — read that before assuming scope.

---
*Last updated: 2026-07-21*
