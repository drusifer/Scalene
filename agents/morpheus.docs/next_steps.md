# Next Steps

## Immediate Next Action
Sprint 4 plan is locked. Waiting for Neo's Phase 1 implementation, then `*lead review phase-1`.

## Waiting On
Neo (Phase 1 impl) → Trin (UAT) → me (review).

## Planned Work
- [ ] `*lead review sprint plan` once Mouse posts phases — expect roughly: (1) Scanner protocol + FileScanner/URLScanner + registry, (2) scan cache store + 3-state lookup + background Popen refresh, (3) hook_adapter.py integration (replace PolicyConfig.evaluate() call site, update §4 class diagram for real), (4) scg onboard re-scope, (5) fatal-exit handling + exit-code verification, (6) scg monitor resource panel.
- [ ] `*lead review` each phase — for the fatal-exit phase specifically, personally verify Neo actually checked the real Claude Code hook contract for the exit code rather than assuming, per Smith's Gate 1 note and the standing lesson from the earlier schema-fix bug.
- [ ] For the background-Popen phase: adversarially test what happens on rapid repeated calls to the same never-cached resource (does it spawn N redundant background scans, or dedupe in-flight scans?) — not specified in the architecture, worth catching at review if Neo's implementation doesn't handle it, rather than leaving it to surface later as a real bug like Sprint 2 Phase 3's crash paths did.
- [ ] Confirm this repo's own `.scalene/scan_cache.json` doesn't collide with anything already in `.gitignore` (it should — same treatment as `.scalene/audit.log`/`state/`).

---
*Last updated: 2026-07-14*
