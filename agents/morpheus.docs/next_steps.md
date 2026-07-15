# Next Steps

## Immediate Next Action
Phase 4 approved, handed to Smith for the mandatory gate.

## Waiting On
Smith (Phase 4 gate) → Neo (Phase 5, once cleared).

## Planned Work (Phase 5)
- [ ] `*lead review phase-5` (`scg monitor` resource panel, Smith gate required): confirm the panel reads `.scalene/scan_cache.json` directly with no separate/duplicated bookkeeping (STORY-1005 AC), same poll-based pattern as the existing Sessions/Mask-events panels.
- [ ] **Make sure `ARCHITECTURE.md` §4's class diagram actually gets updated this phase** — flagged at Phase 3, flagged again at Phase 4, don't let it become a fourth carry-forward. This is the last phase of Sprint 4; if it doesn't happen here, it needs to become an explicit standalone cleanup task before sprint close.
- [ ] Non-blocking, low-priority: `is_fresh()`/`put()`'s `os.stat()` calls on a scanned resource's own file aren't wrapped in error handling (TOCTOU). Not urgent, note for a future pass if anyone's back in `scan_cache.py`.

---
*Last updated: 2026-07-15*
