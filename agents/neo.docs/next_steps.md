# Next Steps

## Immediate Next Action
Nothing for Neo right now — Sprint 4 Phase 2 is handed off to Trin for UAT. Neo's next action is whatever Trin/Morpheus send back: either a fix request on Phase 2, or (if Phase 2 clears) Phase 3 (`*swe impl phase-3`, hook integration — Smith gate required, largest phase so far).

## Waiting On
Trin's UAT on Phase 2 (`src/scalene/scan_cache.py` + `cache_refresh_worker.py`), then Morpheus's review.

## Planned Work (Sprint 4, in order — see task.md for full phase breakdown)
- [x] Phase 1: `Scanner`/`Resource`/`ScanResult` + `FileScanner` + `URLScanner`. **Implemented, Trin UAT PASSED (1 fix round), Morpheus APPROVED.**
- [x] Phase 2: scan cache store + 3-state lookup + background `Popen` refresh w/ dedup. **Implemented 2026-07-14, awaiting Trin UAT + Morpheus review.**
- [ ] Phase 3 (next once Phase 2 clears): replace `PolicyConfig.evaluate()` call site in `hook_adapter.py` with `scanner.SCANNERS` + `scan_cache.refresh_if_needed` — for each identified `Resource`, no cache entry means apply today's `sensitive_by_default`/`untrusted_by_default` exactly as now (this is the "zero added latency" path both Trin's and Morpheus's Phase 2 review should have already confirmed); remove `PolicyRule`/`allowlist` entirely; update `ARCHITECTURE.md` §4's class diagram for real; first-sighting message wording ("not yet verified", distinct from a known-bad decision); re-verify `tests/test_performance.py`'s <15ms NFR actually still passes with resource identification + cache lookup in the hot path. **Smith gate required** — this is the phase where behavior/copy actually changes for a real user.
- [ ] Phase 4: re-scope `scg onboard` to pre-seed the cache (drop `--tool`/`--jsonpath`/`--pattern`/`--description`), fatal-exit handling in `cli.py` — **verify the real exit-code effect against Claude Code's actual hook contract before finalizing, don't assume** (same lesson as the earlier `hookSpecificOutput` schema bug). Also the place to resolve Morpheus's Phase 1 carry-forward note: `FileScanner`/`URLScanner.scan()` never raise today (any `run_scanner` failure — finding or machinery breakage — becomes a `ScanResult` label), so STORY-1004's "scanner raises" fatal trigger has no implementation path yet; either give `run_scanner`'s `{"ok","reason"}` contract a real distinguishing signal, or lean entirely on the cache-store-corruption trigger for this phase. Smith gate required.
- [ ] Phase 5: `scg monitor` resource-cache panel, reads `.scalene/scan_cache.json` directly (same poll-based pattern as existing panels). Smith gate required.
- [ ] Loose end from Sprint 3 (not blocking, not forgotten): Phase 3's demo was never UAT'd by Trin, Sprint 3 was never formally closed. Revisit whenever convenient — doesn't block Sprint 4.

---
*Last updated: 2026-07-14*
