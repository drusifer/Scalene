# Next Steps

## Immediate Next Action
Nothing for Neo right now — Sprint 4 Phase 3 is handed off to Trin for UAT. **This phase has a mandatory Smith gate** (task.md) — do not let Phase 4 start until Smith has explicitly signed off, and make sure she's specifically told about the onboard-suggestion e2e regression (see below), not just handed a generic "Phase 3 done."

## Waiting On
Trin's UAT on Phase 3 → Morpheus's review → **Smith's gate (required, real user-facing behavior/copy change)** → then Phase 4.

## Must-surface item for Smith's gate
`tests/test_onboard_suggestion_e2e.py` is `@unittest.skip`'d, not passing: the suggested `scg onboard` command (shown in every mask/block message) no longer actually works — running it exactly as suggested no longer un-masks a future identical call, since the read side (`resource_verifier`) moved to the scan cache in this phase but the write side (`scg onboard`) doesn't move until Phase 4. Confirmed live, not assumed. This is real regressed behavior for the exact "copy-paste this command" feature Smith personally scrutinized in Sprint 1 (her UX consult) and re-checked in Sprint 3's Gate 1/2 — she needs to decide whether Phase 3 can ship with this window open, or whether Phase 4 needs to be pulled forward/merged.

## Planned Work (Sprint 4, in order — see task.md for full phase breakdown)
- [x] Phase 1: **Trin UAT PASSED (1 fix round), Morpheus APPROVED.**
- [x] Phase 2: **Implemented, Trin UAT PASSED (found+added a real cross-process concurrency test), Morpheus APPROVED with an escalated latency finding — resolved by user decision (accept cost, revise NFR).**
- [x] Phase 3: hook integration + first-sighting messaging + split NFR. **Implemented 2026-07-14, awaiting Trin UAT + Morpheus review + Smith's mandatory gate.**
- [ ] Phase 4 (after Smith's Phase 3 gate clears): re-scope `scg onboard` to pre-seed the cache (drop `--tool`/`--jsonpath`/`--pattern`/`--description`, write directly into `scan_cache.json`) — this is also what un-skips `test_onboard_suggestion_e2e.py`. Fatal-exit handling in `cli.py` — **verify the real exit-code effect against Claude Code's actual hook contract before finalizing, don't assume**. Also resolve Morpheus's Phase 1 carry-forward: `FileScanner`/`URLScanner.scan()` never raise today, so STORY-1004's "scanner raises" fatal trigger has no implementation path yet. Smith gate required.
- [ ] Phase 5: `scg monitor` resource-cache panel, reads `.scalene/scan_cache.json` directly. Smith gate required.
- [ ] `ARCHITECTURE.md` §4's class diagram is now stale in a second way (still shows `PolicyRule`/`allowlist`) — task 3.2 called for updating it "for real," not done yet. Do this in Phase 4 alongside the onboard re-scope, or as its own small cleanup — don't let it linger further.
- [ ] Loose end from Sprint 3 (not blocking, not forgotten): Phase 3's (Sprint 3's) demo was never UAT'd by Trin, Sprint 3 was never formally closed. Revisit whenever convenient.
- [ ] Dev-environment note, not a task: this repo's own `.claude/settings.json` wires the real, editable-installed `scalene-guard` as this session's own hook — `.scalene/scan_cache.json` in the repo root will legitimately fill up during any dev session here, that's not a leak.

---
*Last updated: 2026-07-14*
