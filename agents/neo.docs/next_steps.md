# Next Steps

## Immediate Next Action — READ THIS FIRST ON COLD START
**Nothing in-flight.** Both threads below are done, reviewed (where applicable), and **committed + pushed to `origin/main` as `6d350fe`**. Session ended with a clean `/clear` prep, not mid-task.

## Session summary (2026-08-07 → 2026-08-08, cold-start context)
Two distinct pieces of work this session, in order:

1. **`decide_access()` correction (§15.2b)** — the §15.2a "trust but verify" flag left open at the end of the last session (a validated_allow/trust_but_verify resource was bypassing the block-when-contaminated gate unconditionally). Traced the proposed fix by hand against the *entire* existing `decide_access()` test suite before implementing — caught that a naive "any non-public sensitivity blocks" reading would've broken STORY-1504's project-folder convenience feature, surfaced that concretely to the user instead of guessing a 3rd time, landed on a binary gate (`trust=="low" and sensitivity=="restricted"`) after the user simplified the model. Went through the full `*impl` Bloop chain: Trin found a real silent-downgrade bug in the accompanying `RulesScreen` UX (editing a rule with a backlogged `internal`/`med` value silently overwrote it to the default on save) — fixed, re-verified. Morpheus approved (checked it doesn't break his own STORY-1504 design). Smith approved via a real `export_screenshot()` check, 1 non-blocking finding (backlogged values show no visible RadioSet selection when edited — display gap, not data loss).

2. **Test suite speed** — direct user session, not a formal cycle. The full suite was taking ~600-625s; investigated with real measurements (a stdlib-only timing wrapper, since this project doesn't use pytest) rather than guessing. Found and fixed 3 real things: (a) `unittest.IsolatedAsyncioTestCase` hardcodes `asyncio.Runner(debug=True)`, no override hook — measured ~2.4x overhead, fixed via `tests/_fast_async.py`'s `FastIsolatedAsyncioTestCase`; (b) the 2 genuine full end-to-end journey tests (`TestE17`/`TestE18EndToEndUserJourney`) were running on every dev iteration — moved to `tests/uat_test_monitor_app_journeys.py` (named so default `unittest discover` skips it), `make test-uat` runs them for sprint-close sign-off only; (c) real, unrelated bug found along the way: `FileLock()` calls in `scan_cache.py`/`taint_state.py` (×2) all used the library's default `timeout=-1` (block forever on contention) — fixed with `timeout=5` on all three, 2 new regression tests prove a held lock now fails fast instead of hanging. Net result: `make test` (routine dev target) now runs 602 tests in ~74s, not ~600s. `make test-uat` for the full set including the E2E journeys.

Both pieces reviewed live (in conversation) rather than through separate formal Bloop cycles for #2 (direct user session, matching this project's established "implement fast with the user, gate formally after" pattern noted in Smith's own retro history) — no formal Trin/Morpheus/Smith pass has run against #2 specifically. Flagging as real review debt if it matters later, same shape as prior direct-session work in this repo.

## Waiting On
Nothing.

## Carried, not blocking (from `docs/ARCHITECTURE.md` §21.10)
- `ScanCache` freshness for a directory resource keys off the directory's own mtime (doesn't catch a nested file's *contents* changing deeper in the tree) — only matters if directory-target Allow rules become common.
- `Scanner.from_config()` has no `get_config()`/introspection counterpart — nothing concrete wants this yet.
- `PolicyRule.trust` has no CLI (`scg onboard --trust`) or TUI (Allow form) exposure yet — hand-authored in `scalene_policy.yaml` only.
- The pending-review auto-resolution (§21.9) only runs right after a review is explicitly resolved, not on every `poll_data()` tick — a hand-edited policy file won't retroactively clear now-covered reviews until the next resolution happens.
- `docs/ARCHITECTURE.md` §5's Onboarding sequence diagram is still stale (pre-existing, not touched this session either).
- `cache_refresh_worker.py` stays scoped to builtin scanners only (pre-existing, documented gap) — revisit only if a real config-declared scanner ever ships.

---
*Last updated: 2026-07-30*

## Immediate Next Action (prior, 2026-07-21)
Sprint 9 (E15) Phase 4 complete (last phase), handed to Trin for UAT. On re-invocation:
- If Trin/Smith find issues → fix within Phase 4's scope only.
- If they pass → nothing further for Neo this sprint. Sprint moves to close (Oracle groom → Smith end-to-end test → all-persona retro → Cypher launch) — not Neo's steps.

## Sprint 9 (E15) phase tracking — all 4 phases implemented
- [x] Phase 1 — Configurable Scanner Registry. `make test`: 349/349 (+CLI tests → 352).
- [x] Phase 2 — Hardcoded Restricted Paths. `make test`: 360/360.
- [x] Phase 3 — External Reputation Source. `make test`: 371→374/374 (Tank found+we fixed a real Auth-Key gap).
- [x] Phase 4 — Project-Folder Default. `make test`: 381/381. Smith's mandatory gate + final reviews pending.
