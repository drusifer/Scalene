# Sprint 4 Phase 4 Handoff (2026-07-15)

## Summary
`scg onboard` re-scoped per §13.4: `--target` only, resolves scanner from URI scheme, runs `scan()` synchronously, writes into `.scalene/scan_cache.json`. **This closes the Phase 3 regression** — `test_onboard_suggestion_e2e.py` is un-skipped and genuinely passing; the suggested-command loop works end-to-end again.

STORY-1004 fatal exit built for real: `ScannerMachineryError`/`ScanCacheError` distinguish scanning-machinery failures from ordinary findings; `cli.py` catches both narrowly and exits non-zero with a plain-language stderr message.

## Exit code: verified empirically, not assumed
This repo dogfoods itself — `.claude/settings.json` wires the real, editable-installed `scalene-guard` as this session's own hook. I corrupted the real `.scalene/scan_cache.json` and ran a real tool call: exit code 1 (my initial choice) had **zero blocking effect** — the call proceeded completely normally. Cross-checked against Claude Code's real hook docs (fetched fresh): only exit code **2** blocks a `PreToolUse` call; exit 1 is an explicitly documented, easy-to-make mistake. Changed the implementation from 1 to 2. Restored the real cache from a backup immediately afterward — no lasting effect on repo state.

## Also fixed while wiring this up
- `scan_cache.py`'s corruption handling changed from Phase 2's "fail-safe to empty" to raising `ScanCacheError` — intentional now that a clean fatal-exit path exists; silently treating corruption as empty would quietly degrade protection forever.
- `FileLock` acquisition itself could raise an uncaught `PermissionError` — wrapped via a new `_locked()` helper, verified with a real read-only-directory test.
- Closed Morpheus's Phase 2 carry-forward note: `cache_refresh_worker.py` now covers the cache-write step in its exception handling too.
- Doc-drift fixes required to keep `make test` green: `USER_GUIDE.md`, `SETUP.md`, `GETTING_STARTED.md` (regenerated against real current output, not memory).

210/210 tests passing, 0 skipped.

## For Smith's gate specifically
Two things she asked to be confirmed: (1) the onboard-suggestion loop is genuinely closed — yes, ran it live. (2) the exit code is verified for real — yes, both empirically against this repo's own live hook and against Claude Code's official docs.
