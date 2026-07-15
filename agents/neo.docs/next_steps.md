# Next Steps

## Immediate Next Action
Nothing for Neo right now — Sprint 4 Phase 1 is handed off to Trin for UAT (`*qa test all` / phase-1-scoped). Neo's next action is whatever Trin/Morpheus send back: either a fix request on Phase 1, or (if Phase 1 clears) Phase 2 (`*swe impl phase-2`, scan cache store).

## Waiting On
Trin's UAT on Phase 1 (`src/scalene/scanner.py` — both scanners correctly identify resources across all built-in tool shapes + the generic fallback, at parity with today's secrets-scan/reputation-check behavior), then Morpheus's review.

## Planned Work (Sprint 4, in order — see task.md for full phase breakdown)
- [x] Phase 1: `Scanner`/`Resource`/`ScanResult` + `FileScanner` + `URLScanner`, Bash wired into both scanners' fallback. No Smith gate. **Implemented 2026-07-14, awaiting Trin UAT + Morpheus review.**
- [ ] Phase 2 (next once Phase 1 clears): scan cache store (`.scalene/scan_cache.json`, `filelock`), 3-state lookup, background `Popen` refresh with dedup for concurrent first-sighting scans. No Smith gate, but exit criteria requires a real repeated-invocation test proving no orphaned processes. Note for whoever picks this up: the cache-key format shown in `docs/ARCHITECTURE.md` §13.3's JSON example (`"file:///abs/path/..."`) doesn't literally match the `f"{scanner_name}:{resource.identity}"` key formula stated in the same section (`resource.identity` for a file is a plain absolute path, not a `file://` URI, and `scanner_name` is `"secrets"` not `"file"`) — resolve this discrepancy against the literal key formula, not the illustrative example, when building Phase 2.
- [ ] Phase 3: replace `PolicyConfig.evaluate()` call site in `hook_adapter.py`, remove `PolicyRule`/`allowlist` entirely, update `ARCHITECTURE.md` §4's class diagram for real, first-sighting message wording ("not yet verified"), re-verify `tests/test_performance.py`'s <15ms NFR actually still passes. Smith gate required.
- [ ] Phase 4: re-scope `scg onboard` to pre-seed the cache (drop `--tool`/`--jsonpath`/`--pattern`/`--description`), fatal-exit handling in `cli.py` (scanning-machinery failure only, never a scan finding) — **verify the real exit-code effect against Claude Code's actual hook contract before finalizing, don't assume** (same lesson as the earlier `hookSpecificOutput` schema bug). This is also where `FileScanner`/`URLScanner.scan()`'s current parity-only `ok=False` handling (collapses "finding" and "scan machinery broke" into one label) needs to be split apart, per Phase 1's context.md note. Smith gate required.
- [ ] Phase 5: `scg monitor` resource-cache panel. Smith gate required.
- [ ] Loose end from Sprint 3 (not blocking, not forgotten): Phase 3's demo was never UAT'd by Trin, Sprint 3 was never formally closed. Revisit whenever convenient — doesn't block Sprint 4.

---
*Last updated: 2026-07-14*
