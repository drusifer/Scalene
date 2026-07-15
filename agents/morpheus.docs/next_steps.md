# Next Steps

## Immediate Next Action
**PAUSED for real user visibility** on the latency finding below before Phase 3 (hook integration) starts — not a formal Smith gate, but Phase 3 would otherwise build the hot-path wiring on a performance premise I've now personally measured and disproven. Once the user has weighed in (accept the cost and redesign the NFR conversation, or redesign the spawn mechanism, or something else), hand back to Neo for Phase 3.

## Waiting On
User input on the latency finding → Neo (Phase 3 impl, informed by whatever direction comes back) → Trin (UAT) → me (review) → Smith (gate, required).

## URGENT: Phase 2 latency finding — needs a design decision before Phase 3
`refresh_if_needed()`'s fire-and-forget `subprocess.Popen` spawn costs ~6.6ms avg / ~16ms max per never-cached resource in this environment (measured directly, isolated to the spawn syscall itself — not the worker script). §13.3's "zero-added-latency, not a regression risk" claim for the new-resource path does not hold as currently implemented. Against the existing <15ms hot-path NFR, this is a real risk on any first-sighting call, worse with multiple never-seen resources in one call. Options to weigh (not yet decided, needs input):
- Accept the added latency and revise the NFR/architecture claim honestly (simplest, but changes what "no regression" means for this epic)
- Redesign the spawn to be genuinely cheaper (e.g., a lighter-weight detach mechanism, batching multiple resources into one spawn per call instead of one per resource)
- Decouple the spawn from the synchronous `pre_tool_use` path entirely (e.g., queue in the cache write and let `post_tool_use` or something even less latency-sensitive trigger it)

## Planned Work (once Phase 3 resumes)
- [ ] `*lead review phase-3` (hook_adapter.py integration, Smith gate required): re-verify `tests/test_performance.py`'s <15ms NFR for real, now informed by the above finding rather than hoping it passes.
- [ ] Non-blocking carry-forward from Phase 2: `cache_refresh_worker.py`'s exception handling doesn't cover `ScanCache.put()`, only `scanner.scan()` — bounded/self-healing (5min pending-reservation expiry), but worth a one-line fix (wrap `put()` too) whenever Phase 3/4 touches this file.
- [ ] Carry forward from Phase 1 review: `Scanner.scan()` never raises today, which means Phase 4's fatal-exit trigger for "scanner raises an unhandled exception" (STORY-1004) has no implementation path yet unless `run_scanner`'s contract changes. Don't let it get assumed-solved.
- [ ] For the fatal-exit phase (4) specifically: personally verify Neo actually checked the real Claude Code hook contract for the exit code rather than assuming, per Smith's Gate 1 note and the standing lesson from the earlier schema-fix bug.

---
*Last updated: 2026-07-14*
