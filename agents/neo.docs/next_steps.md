# Next Steps

## Immediate Next Action
Sprint 9 (E15) Phase 4 complete (last phase), handed to Trin for UAT (2026-07-21). On re-invocation:
- If Trin/Smith find issues → fix within Phase 4's scope only.
- If they pass → nothing further for Neo this sprint. Sprint moves to close (Oracle groom → Smith end-to-end test → all-persona retro → Cypher launch) — not Neo's steps.

## Waiting On
Trin's Phase 4 UAT, then Smith's mandatory gate (her own Gate 1 hard requirement), then Morpheus's Phase 4 review.

## Sprint 9 (E15) phase tracking — all 4 phases implemented
- [x] Phase 1 — Configurable Scanner Registry. `make test`: 349/349 (+CLI tests → 352).
- [x] Phase 2 — Hardcoded Restricted Paths. `make test`: 360/360.
- [x] Phase 3 — External Reputation Source. `make test`: 371→374/374 (Tank found+we fixed a real Auth-Key gap).
- [x] Phase 4 — Project-Folder Default. `make test`: 381/381. Smith's mandatory gate + final reviews pending.

## Carried, not blocking
- `docs/ARCHITECTURE.md` §5's Onboarding sequence diagram is still stale — not touched by E15 either so far.
- `cache_refresh_worker.py` stays scoped to builtin scanners only (documented gap in the code itself, Phase 1) — revisit only if a real config-declared scanner ever ships.

---
*Last updated: 2026-07-21*
