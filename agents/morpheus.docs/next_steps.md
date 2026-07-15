# Next Steps

## Immediate Next Action
Phase 1 APPROVED, handed to Neo for Phase 2. Waiting for Neo's Phase 2 implementation, then `*lead review phase-2`.

## Waiting On
Neo (Phase 2 impl: scan cache store) → Trin (UAT) → me (review).

## Planned Work
- [ ] `*lead review phase-2`: scan cache store + 3-state lookup + background Popen refresh (STORY-1003). Personally verify (don't just trust the handoff) that the "new resource" path is genuinely zero-added-latency, since that's the whole justification for why this isn't a regression risk.
- [ ] For the background-Popen phase specifically: adversarially test what happens on rapid repeated calls to the same never-cached resource (does it spawn N redundant background scans, or dedupe in-flight scans?) — not specified in the architecture, worth catching at review if Neo's implementation doesn't handle it, rather than leaving it to surface later as a real bug like Sprint 2 Phase 3's crash paths did.
- [ ] Confirm `.scalene/scan_cache.json` gets the same `.gitignore` treatment as `.scalene/audit.log`/`state/` — folded into Phase 2 per task.md, verify it actually landed.
- [ ] Carry forward from Phase 1 review: `Scanner.scan()` never raises today, which means Phase 4's fatal-exit trigger for "scanner raises an unhandled exception" (STORY-1004) has no implementation path yet unless `run_scanner`'s contract changes. Watch for this at Phase 3/4 review — don't let it get assumed-solved.
- [ ] `*lead review phase-3` (hook_adapter.py integration, Smith gate) — for the fatal-exit phase (4) specifically, personally verify Neo actually checked the real Claude Code hook contract for the exit code rather than assuming, per Smith's Gate 1 note and the standing lesson from the earlier schema-fix bug.

---
*Last updated: 2026-07-14*
