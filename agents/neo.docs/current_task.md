# Current Task

**Status:** DONE — Sprint 4 Phase 4 (scg onboard Re-scope & Fatal Exit) implemented, awaiting Trin UAT + Morpheus review + Smith's mandatory gate.
**Assigned to:** Neo
**Started:** 2026-07-15
**Finished:** 2026-07-15

## Task Description: `*swe impl phase-4` (Sprint 4, STORY-1004)
Rewrite `scg onboard` to pre-seed the cache; fatal-exit handling in `cli.py`; verify the real exit-code effect against Claude Code's actual hook contract before finalizing. Full spec: `docs/ARCHITECTURE.md` §13.4/§13.5, task breakdown in `task.md` Sprint 4 Phase 4.

## Progress
- [x] Task 4.1: `onboard.py` rewritten — `--target` only, resolves scanner from URI scheme, runs `scan()` synchronously, writes into `.scalene/scan_cache.json`. File identity normalization matches `FileScanner.identify()` exactly (tested).
- [x] **Closes the Phase 3 regression**: `hook_adapter._suggest_onboard_command` rebuilt around `--target` alone; `test_onboard_suggestion_e2e.py` un-skipped and genuinely passing — the full suggested-command loop works again.
- [x] Task 4.2: fatal-exit handling in `cli.py` — `except (ScanCacheError, ScannerMachineryError)`, deliberately narrow, not a bare `except Exception`.
- [x] Built the actual `ScannerMachineryError`/`ScanCacheError` distinguishing machinery (didn't exist before this phase — Morpheus's Phase 1 carry-forward note confirmed and resolved: `Scanner.scan()` never raised before, now does on machinery failure specifically).
- [x] Changed `scan_cache.py`'s corruption handling from Phase 2's original "fail-safe to empty" to raising `ScanCacheError` — intentional, documented evolution now that a clean fatal-exit boundary exists.
- [x] Found and fixed a real gap: `FileLock` *acquisition* itself (not just read/write) could raise an uncaught `PermissionError` — wrapped via a new `_locked()` context manager, verified with a real chmod'd read-only-directory test.
- [x] Closed Morpheus's Phase 2 carry-forward note: `cache_refresh_worker.py`'s exception handling now covers the cache-write step too.
- [x] Task 4.3: **verified the real exit code empirically**, using this repo's own dogfooded `scalene-guard` hook (`.claude/settings.json` wires the real, editable-installed binary as this session's own hook) — corrupted the real cache, confirmed live that exit code 1 (the initial provisional choice) has zero blocking effect on a real tool call. Cross-checked against Claude Code's real hook docs (fetched fresh): only exit code 2 blocks `PreToolUse`. Changed from 1 to 2. Restored the real cache from backup afterward — no lasting effect on repo state.
- [x] Doc-drift fixes (blocking `make test`, not optional polish): `USER_GUIDE.md`, `SETUP.md`, `GETTING_STARTED.md` (literal output regenerated against real current behavior, not memory).
- [x] `make test`: 210/210 passing, **0 skipped** (Phase 3's regression is closed).

## Blockers
None for implementation. Smith's mandatory gate is required before this phase ships (task.md) — she specifically asked to confirm the onboard-suggestion loop is closed (it is) and the exit code is verified, not assumed (it is, empirically).

## Oracle Consultations
None yet.

---
*Last updated: 2026-07-15*
