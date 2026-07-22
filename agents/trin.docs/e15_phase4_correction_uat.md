# Trin — `*qa uat phase-4` re-run — Sprint 9 (E15), mechanism corrected — 2026-07-21

## What changed
Neo reworked Phase 4 per direct user request: a real rule written to a real `scalene_policy.yaml` on first run, replacing the implicit in-memory rule + synthetic `--list` line. Re-ran full UAT against the new mechanism — not treating the earlier approval as still valid, since the underlying code is different.

## Independent verification, went beyond Neo's own tests
- Grepped the whole codebase for leftover references to the removed mechanism (`project_root=`, `implicit default:`, `trust=trusted`) — clean, only the one legitimate `write_default_project_policy(policy_path, project_root=...)` call site in `cli.py` remains.
- **Found a gap in Neo's own multi-onboard reasoning wasn't tested**: his shadowing fix (insert before the auto-created default) was verified for exactly one onboard call. Added `test_multiple_onboards_after_the_default_all_stay_ahead_of_it_in_order` — two sequential onboards after the default exists, confirming both land ahead of it *in onboard order* (not just that "some rule" precedes the default). Caught a trivial bug in my own first draft of this test (asserting literal substring containment against a regex-escaped pattern — `\.` vs `.`) before it could hide a real problem; fixed to use `assertRegex`.
- Re-ran the "timestamp uninitialized" claim myself: confirmed `write_default_project_policy()` never constructs or touches a `ScanCache`/`CacheEntry` object anywhere in its body — grepped for any cache import in `policy_config.py`, none exists.
- Confirmed real end-to-end via the actual `scalene-guard` CLI (not just unit tests) that a fresh project gets the file created correctly on first call, and a second call doesn't duplicate or rewrite it (`test_second_call_reuses_the_existing_file_without_duplicating_the_rule` checks `st_mtime_ns` is unchanged, not just content — a real "did it actually skip the write" check, not just "does the content still look right").

## Regression check
Full suite: `make test` — **388/388** (387 + my 1 new multi-onboard test).

## Verdict

**PASSED.** Handing to Smith — the mandatory gate needs to re-confirm her discoverability requirement against the *new* mechanism (a real rule in a real file), not re-approve the old one.
