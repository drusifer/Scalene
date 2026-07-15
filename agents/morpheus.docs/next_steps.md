# Next Steps

## Immediate Next Action
Resolved and handed to Neo for Phase 3 (`*swe impl phase-3`). Next Morpheus involvement is `*lead review phase-3` once Neo/Trin finish.

## Waiting On
Neo (Phase 3 impl) → Trin (UAT, incl. verifying `NFR-Perf-FirstSighting`'s <25ms provisional budget for real) → me (review) → Smith (gate, required).

## Planned Work (Phase 3+)
- [ ] `*lead review phase-3` (hook_adapter.py integration, Smith gate required): confirm `tests/test_performance.py` gained a real `NFR-Perf-FirstSighting` test (not just the existing steady-state one) and that Neo verified the <25ms provisional budget for real rather than assuming it holds — same standard I just held myself to on the steady-state claim.
- [ ] Non-blocking carry-forward from Phase 2: `cache_refresh_worker.py`'s exception handling doesn't cover `ScanCache.put()`, only `scanner.scan()` — bounded/self-healing (5min pending-reservation expiry), but worth a one-line fix (wrap `put()` too) whenever Phase 3/4 touches this file.
- [ ] Carry forward from Phase 1 review: `Scanner.scan()` never raises today, which means Phase 4's fatal-exit trigger for "scanner raises an unhandled exception" (STORY-1004) has no implementation path yet unless `run_scanner`'s contract changes. Don't let it get assumed-solved.
- [ ] For the fatal-exit phase (4) specifically: personally verify Neo actually checked the real Claude Code hook contract for the exit code rather than assuming, per Smith's Gate 1 note and the standing lesson from the earlier schema-fix bug.

---
*Last updated: 2026-07-14*
