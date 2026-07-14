# Next Steps

## Immediate Next Action
Start Sprint 4 Phase 1 (`*swe impl phase-1`): Scanner protocol + `FileScanner` + `URLScanner`. Read `docs/ARCHITECTURE.md` §13.2 and `task.md`'s Sprint 4 Phase 1 task table first. TDD test-first as always.

## Waiting On
Nothing — this is mine to start.

## Planned Work (Sprint 4, in order — see task.md for full phase breakdown)
- [ ] Phase 1 (next): `Scanner`/`Resource`/`ScanResult` + `FileScanner` + `URLScanner`, Bash wired into both scanners' fallback. No Smith gate.
- [ ] Phase 2: scan cache store (`.scalene/scan_cache.json`, `filelock`), 3-state lookup, background `Popen` refresh with dedup for concurrent first-sighting scans. No Smith gate, but exit criteria requires a real repeated-invocation test proving no orphaned processes.
- [ ] Phase 3: replace `PolicyConfig.evaluate()` call site in `hook_adapter.py`, remove `PolicyRule`/`allowlist` entirely, update `ARCHITECTURE.md` §4's class diagram for real, first-sighting message wording ("not yet verified"), re-verify `tests/test_performance.py`'s <15ms NFR actually still passes. Smith gate required.
- [ ] Phase 4: re-scope `scg onboard` to pre-seed the cache (drop `--tool`/`--jsonpath`/`--pattern`/`--description`), fatal-exit handling in `cli.py` (scanning-machinery failure only, never a scan finding) — **verify the real exit-code effect against Claude Code's actual hook contract before finalizing, don't assume** (same lesson as the earlier `hookSpecificOutput` schema bug). Smith gate required.
- [ ] Phase 5: `scg monitor` resource-cache panel. Smith gate required.
- [ ] Loose end from Sprint 3 (not blocking, not forgotten): Phase 3's demo was never UAT'd by Trin, Sprint 3 was never formally closed. Revisit whenever convenient — doesn't block Sprint 4.

---
*Last updated: 2026-07-14*
