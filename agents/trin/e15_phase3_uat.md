# Trin — `*qa uat phase-3` — Sprint 9 (E15) — 2026-07-21

## Checked against artifacts first
`task.md` Sprint 9 Phase 3 exit criteria: a real/simulated URLhaus-flagged host resolves untrusted; a simulated network failure degrades to local-heuristics-only with the marker present, not silently identical to clean. `docs/ARCHITECTURE.md` §18.3.

## Independent adversarial sweep — found a real gap Neo's own file list missed
Neo's fix (env-var gate + `tests/_env_guards.py`, wired into 8 files) was well-reasoned, but I didn't just trust the file list — grepped the whole `tests/` directory myself for anything constructing a `reputation`-scanner `Resource` or calling `refresh_if_needed()`/`.scan()` directly. Found **`tests/test_scan_cache.py`** calls `refresh_if_needed()` directly on cache-miss URL resources (e.g. `"internal.example.com"`) across ~10 test methods — this would have spawned real background subprocesses attempting live URLhaus calls, ungated, since it wasn't on Neo's list (it doesn't literally contain the strings "https://" or "WebFetch" that a naive grep for those terms would catch). Added the same `setUpModule`/`tearDownModule` guard there. Also checked `test_monitor_app.py`/`test_monitor_data.py` (also matched my broader grep for `scanner_name="reputation"`) — confirmed safe, they only construct `Resource`/`CacheEntry` objects directly for TUI-layer tests, never call `refresh_if_needed`/`.scan()`.

## Verified the actual ACs
Reviewed `tests/test_reputation.py`'s `TestURLHausChecker`/`TestCompositeCheck` (11 tests, all mocking `_query_urlhaus` in-process): confirms a real URLhaus-flagged host (`query_status: ok`, an online URL) resolves `is_trusted=False, score=0.0`; confirms a genuine `URLError`/unexpected `query_status` raises `ReputationCheckUnavailable` rather than being treated as a finding; confirms the degraded path's `reason` contains the literal "external reputation check unavailable" marker, distinguishable from a real clean pass. Confirmed any-bad-wins and min-score combination logic against both directions (local-bad+remote-clean stays bad; local-clean+remote-bad becomes bad).

## Regression check
Full suite, re-timed to confirm the network-call regression is actually fixed, not just claimed: `make test` — **371/371 in ~45s** (consistent with the pre-Phase-3 baseline shape; the earlier 57s run before Neo's fix confirmed the live-network problem was real, not theoretical).

## Verdict

**PASSED**, with 1 real gap found and closed during UAT (not deferred). Handing to Morpheus for code review. Flagging for Morpheus/Mouse: **Tank's required review has not happened yet** — this phase cannot close until Tank signs off per `task.md`'s own exit criteria.
