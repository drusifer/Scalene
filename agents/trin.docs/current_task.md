# Current Task

**Status:** Sprint 4 Phase 2 (Scan Cache Store) UAT: PASSED. Handed to Morpheus.
**Assigned to:** Trin
**Started:** 2026-07-14

## Task Description (most recent): `*qa uat phase-2` (Sprint 4, STORY-1003)

## Progress
- [x] Read `scan_cache.py` + `cache_refresh_worker.py` in full against §13.3 and task.md's explicit Phase 2 exit-criteria addition (real repeated-invocation test proving no orphaned processes)
- [x] **Found a real gap in Neo's coverage, closed it myself** (my own standing SDET remit): Neo's dedup test calls `try_reserve()` 5x sequentially in one process — trivially serialized by `FileLock`, doesn't exercise the case that actually matters for a real Claude Code session: two *separate* `scalene-guard` invocations (separate OS processes, no shared memory) racing on the same never-cached resource. Added `test_dedup_holds_under_real_cross_process_concurrency` using a real `ProcessPoolExecutor` (8 genuinely separate OS processes hammering `try_reserve()` on the same resource) — confirmed exactly 1 of 8 wins, every time across 5 repeated runs (checked for a lucky-pass race, not just one green run).
- [x] Independently re-verified the "no orphaned processes" claim myself rather than trusting Neo's test alone: ran the real repeated-invocation test, then checked `ps -eo pid,ppid,stat,cmd | grep defunct` immediately after — no zombies.
- [x] Independently verified the `.gitignore` claim (Neo said "`.scalene/` already covers it," didn't just trust it): created a real `.scalene/scan_cache.json` and ran `git check-ignore -v` — confirmed matched by `.gitignore:199:.scalene/`.
- [x] `make test`: 195/195 passing (194 + my 1 new test)
- [x] **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-1` (Sprint 4, STORY-1001/1002)

## Progress
- [x] Read `src/scalene/scanner.py` in full against `docs/ARCHITECTURE.md` §13.2 and `task.md`'s Phase 1 task table
- [x] **Found a real bug via direct execution, not just code reading**: `FileScanner`'s generic path-fallback regex had no exclusion for URL slashes — `https://host/path` matched as a bogus file path. Confirmed live (not assumed) with `python -c` before filing: `FileScanner.identify("WebFetch", {"url": "https://internal.example.com/reports", ...})` returned a spurious file `Resource`. This wasn't an edge case — it fired on **every** `WebFetch` call, since the fallback scans all string args, not just Bash's. Would have broken the Phase 1 exit criteria ("correctly identify resources across all built-in tool shapes") had it shipped, and downstream in Phase 3 would have made every WebFetch call also trigger a bogus secrets-scan against a non-existent path.
- [x] Sent back to Neo (`*swe fix phase-1 url-path-collision`) rather than fixing it myself — kept the QA/implementation roles separate per protocol.
- [x] Neo added 2 regression tests (confirmed red), fixed via a proper URL-span-exclusion helper (`_find_paths_excluding_urls`) rather than a fragile negative-lookbehind (which I'd have flagged too — lookbehind only blocks the first slash of a URL, not later `/segments`, so it would've been a partial fix)
- [x] Independently re-verified the fix myself post-fix: re-ran the exact repro that found the bug (now `[]`), plus a mixed case (`"cat /etc/passwd && curl https://evil.example.net/x"`) to confirm the fix didn't over-correct and start missing real paths — `FileScanner` still finds `/etc/passwd`, `URLScanner` still finds `evil.example.net`, in the same call
- [x] `make test` (real mkf-wrapped target, not a piped raw `.venv` call — my own standing lesson from Sprint 3): PASSED, exit 0
- [x] 23 tests in `tests/test_scanner.py` cover every built-in tool shape named in task.md's Phase 1 row (Read/Write/Edit known-field, WebFetch known-field + Bash generic fallback for both scanners) plus the URL/path collision regression
- [x] **Verdict: PASS** (after 1 fix round — no third-attempt/Oracle-consult situation, first fix was correct)

## Task Description (prior): `*qa uat phase-2` (Sprint 3, STORY-902)

## Progress
- [x] Read `docs/USER_GUIDE.md` in full — confirmed Smith's Gate 1 note (onboard-suggestion workflow presented as the primary path, manual flags as fallback) actually landed, not just mentioned in the handoff
- [x] Confirmed the policy schema section cross-references `ARCHITECTURE.md`/`BRD.md` rather than duplicating the full schema, and the troubleshooting table accurately reflects Neo's fail-safe fix (didn't re-verify the fix by hand — `tests/test_cli.py::test_malformed_policy_yaml_fails_safe_and_allows` already covers it, and `make test` passing is the check, per this session's correction against redundant manual repros)
- [x] `make test`: 137/137 passing
- [x] `make judge-trace DATE=2026-07-14`: 201 calls, 25 flags cumulative this session (11 `AP-MAKE-PIPE`, 9 `AP-RAW-VENV`, 3 `AP-VIA-READ`, 2 `AP-VIA-GREP`) — real, self-inflicted, same categories as Phase 1's UAT finding, not new code/doc defects. Noting that `AP-MAKE-PIPE`'s own documented fix (`make test-q`) doesn't actually exist as a Makefile target yet — flagging to Bob/Mouse as a real tooling gap, not blocking this phase.
- [x] **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-1` (Sprint 3, STORY-901).

## Progress
- [x] Independently ran all 3 `scalene-guard` invocations from `docs/GETTING_STARTED.md`, copy-pasted verbatim, in a scratch dir — confirmed real masked output + real `.scalene/audit.log` entry, matching the doc exactly (not just trusting Neo's report)
- [x] Did the strongest version of the "clean clone" AC: cloned the actual repo fresh into a separate directory and ran `make setup` for real (21s), then ran the doc's 3 commands against *that* clone's own installed binary — confirms the walkthrough genuinely works starting from nothing, not just in an already-set-up dev tree. Total time clone→masked-event: well under 5 minutes (timing AC formally belongs to Smith's gate, but this rules out any functional failure before she times it)
- [x] Confirmed `README.md` links to the new doc rather than duplicating content (`tests/test_getting_started_docs.py` also checks this)
- [x] `make test`: 127/127 passing
- [x] `make judge-trace DATE=2026-07-14`: 125 calls, 11 real flags this session (5x `AP-RAW-VENV`, 4x `AP-MAKE-PIPE`, 1x `AP-VIA-GREP`, 1x `AP-VIA-READ`) — all from my own ad hoc verification commands (direct `.venv/bin/scalene-guard` invocations instead of a make target, piped `make` output, one grep instead of `via`). Real per the documented rules, not false positives; none are code/doc defects, all self-inflicted process nits during verification. Not blocking, noted per protocol.
- [x] **Verdict: PASS.**

## Blockers
None.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-14*
