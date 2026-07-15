# Next Steps

## Immediate Next Action
**STOPPED here per user instruction** ("full run, pause only at Smith gates"). Phase 3 is approved and handed to Smith in CHAT.md, but the real user needs to weigh in before Smith's persona actually runs the gate — do not simulate her sign-off and continue into Phase 4 autonomously.

## Waiting On
Real user input on how to proceed at this Smith gate (in particular: what to do about the onboard-suggestion regression) → Smith (gate) → Neo (Phase 4).

## Planned Work (Phase 4+, once the gate clears)
- [ ] Non-blocking carry-forward from Phase 2: `cache_refresh_worker.py`'s exception handling doesn't cover `ScanCache.put()`, only `scanner.scan()` — bounded/self-healing (5min pending-reservation expiry), but worth a one-line fix (wrap `put()` too) whenever Phase 4 touches this file.
- [ ] Carry forward from Phase 1 review: `Scanner.scan()` never raises today, which means Phase 4's fatal-exit trigger for "scanner raises an unhandled exception" (STORY-1004) has no implementation path yet unless `run_scanner`'s contract changes. Don't let it get assumed-solved.
- [ ] For the fatal-exit phase (4) specifically: personally verify Neo actually checked the real Claude Code hook contract for the exit code rather than assuming, per Smith's Gate 1 note and the standing lesson from the earlier schema-fix bug.
- [ ] Non-blocking documentation debt from Phase 3 review: `ARCHITECTURE.md` §13.2 could use a one-line clarification that the aggregation layer (`resource_verifier.py`) isn't dispatch-free the way the scanner registry is — a future 3rd scanner needs an explicit decision about which `MatchResult` dimension(s) it affects.
- [ ] `ARCHITECTURE.md` §4's class diagram is still stale (still shows `PolicyRule`/`allowlist`) — task 3.2 called for updating it "for real," carried forward again from Neo's Phase 3 handoff.

---
*Last updated: 2026-07-14*
