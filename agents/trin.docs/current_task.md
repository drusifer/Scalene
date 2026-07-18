# Current Task

**Status:** `*qa uat sec15` — PASSED. Closes the UAT gap I flagged when the sprint got superseded (see prior next_steps.md note). Handed to Morpheus for architecture review.
**Assigned to:** Trin
**Started:** 2026-07-18

## Task Description (most recent): `*qa uat sec15` — real adversarial UAT of the rule-driven access control rework
This never got a formal gate when it shipped (implemented directly with the user, mid-conversation, superseding Phase 3's original design). Ran real adversarial tests against `decide_access`:
- Multiple `confirmed_bad` resources in one call → reason message lists both clearly, no crash: `"Blocked: https://evil1... (the scanner found a real issue with it); https://evil2... (...)."`
- A rule with a typo'd `scanner` field (e.g. `"reputatoin"`) → silently doesn't match, falls through to the safe `uncleared` path (proceeds from clean context, trust drops to low) — a broken rule fails toward *more* restrictive, never grants unintended access. Correct, safe failure mode; flagged as a Smith UX note (confusing to debug), not a correctness bug.
- Confirmed the Phase 2 regex-validation protection (`PolicyRule.__post_init__` compiling `tool`/`pattern` at construction) covers this code path too, via the same `_find_matching_rule` helper — no new gap.
- Considered a pre-sec15 session-file back-compat scenario (`has_sensitive_data`/`has_untrusted_data` silently loading as clean under the new schema) — raised it, user explicitly said not to worry about backwards compatibility for this rework. Not a bug per the user's stated intent; noted and dropped, not fixed.
- `make test`: 266/266. **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-3` (Sprint 5, last phase)
Verified the mode=allow aggregation semantics directly against `_MODE_RANK`: an "allow"-matched resource never overrides a stricter "mask"/"block" resolved for a different resource in the same call (most-restrictive-wins already covers this, confirmed via `test_most_restrictive_mode_wins_across_multiple_resources`). Noted (not a defect, a documented characteristic): `mode: allow` suppresses scanning for the *entire* payload value on a matching call, not just content related to the matched resource — this is consistent with the existing structural/coarse-grained masking model (E4), not a new gap introduced here. Also noted (flag for Smith, not blocking): a rule with `pattern: ".*"` + `mode: allow` would functionally disable scanning project-wide at the rule level, even though `PolicyConfig.mode` itself can't be set to `allow` — the global-level guard doesn't prevent an equivalently broad rule. This is a deliberate, hand-authored, reviewable choice (not automatic), so I'm not blocking on it, but flagging it as a real discussion point for the Smith gate. Ran a live `pre_tool_use` call directly (not just unit tests) to confirm the reworked message reads correctly end-to-end — output is clear, matches architecture intent, YAML snippet is valid. Also ran `demo/run_demo.py` directly, confirmed Part 3/4's new narrative is coherent. `make test`: 266/266. **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-2` (Sprint 5)
Adversarial-tested rule matching before approving (Morpheus's Sprint 4 Phase 1 precedent — construct hostile input directly, don't just trust the happy-path tests). Found a real gap: `PolicyRule` didn't validate `tool`/`pattern` compile as valid regex — a config typo (unclosed bracket) would raise `re.error` deep inside `resource_verifier.evaluate()`, crashing `scalene-guard` on every subsequent call that identifies any resource at all, not fail-safe. Sent back to Neo for one fix. **Re-reviewed the fix**: `PolicyRule.__post_init__` now `re.compile()`s both fields, raising `PolicyConfigError` with a clear, specific message (verified directly: `'pattern' is not a valid regex: '[unclosed' (unterminated character set at position 0)`) at rule-construction time — fails loud where a developer is actively editing config, not silently deep in the hot path. Also verified the rule-matching precedence tests (declaration order, most-restrictive-wins, tool/scanner filters) are real and correctly isolate what they claim to test. `make test`: 264/264. **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-1` (Sprint 5)
Verified: (1) `URLScanner.identify()` now produces distinct identities for distinct paths under the same host (`test_distinct_paths_under_same_host_are_separate_resources`) — the actual STORY-1101 fix, confirmed at both the scanner level and the `resource_verifier.evaluate()` level (`test_verified_path_does_not_vouch_for_sibling_path_under_same_host`). (2) `scan()` still runs the host-level reputation heuristic correctly against a full-URL identity (extracts host via `urlparse`, falls back to using identity as-is for bare-host callers — both paths covered). (3) `PolicyRule`/`rules:` parsing rejects invalid `sensitivity`/`mode` with a clear `PolicyConfigError`, not a raw KeyError/traceback. (4) Personally spot-checked `onboard._resolve_resource`'s normalization against 3 edge cases (bare host, trailing slash, query string) — matches what a live `URLScanner.identify()` call would produce, consistent with the real regression test already in `test_onboard.py`. (5) Confirmed the real fallout bug Neo found (onboard-suggestion placeholder) has a genuine end-to-end regression test (`test_onboard_suggestion_e2e.py`) that exercises the real `scg` CLI dispatch, not just the library function. `make test`: 250/250 passing. **Verdict: PASS.**

## Task Description (prior): Sprint 3 Phase 3 (Demo) UAT: PASSED, closing a UAT that never ran back in Sprint 3. Handed to Morpheus.

## Task Description (most recent): `*qa uat phase-3` (Sprint 3, STORY-903) — completing Sprint 3's close
Sprint 3 was never formally closed because this exact UAT never ran before the session moved to unrelated work back in Sprint 3. Ran it now against the demo as it currently exists (post-Sprint-4 messaging/onboarding changes — per user direction, held to current correct behavior, not superseded Sprint 3 wording).

## Progress
- [x] Ran `make demo` for real — reads clearly for a BRD-naive reader (plain language throughout, no "taint"/jargon), correctly shows Sprint 4's current first-sighting wording and re-scoped `scg onboard --target`-only suggestion format.
- [x] `tests/test_demo.py`: 3/3 passing (subprocess-level, asserts the masking marker appears and the fake secret never appears unmasked).
- [x] Confirmed no real network egress: grepped `demo/run_demo.py` for any network-capable import — none exist; the script only ever calls the local `scalene-guard` subprocess, which is itself decision-only by architecture (never performs the tool call).
- [x] `make test`: 230/230 passing (unaffected, demo/test_demo.py already current from Sprint 4's doc-drift fixes).
- [x] **Verdict: PASS.**

## Task Description (prior): `*qa retest phase-5 bug` (Last Scanned column truncation)
Smith found a real rendering-truncation bug during her gate (real screenshot at 120 cols). Neo's 1st fix attempt (shorten timestamp) failed a real re-render check and was correctly abandoned per the anti-loop protocol rather than iterated on. 2nd attempt (move the panel to its own full-width row) — independently re-verified with a DIFFERENT, even longer dataset than either Neo's or Smith's own checks (a deep monorepo path, a longer hostname): every column renders fully, nothing truncated. `make test`: 230/230. **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-5` (Sprint 4, STORY-1005)

## Progress
- [x] Independently grepped for any parallel/duplicated scan_cache.json readers — confirmed `monitor_data.py`'s `discover_scan_results()` (via `ScanCache.all_entries()`) is the only consumer, genuinely satisfying STORY-1005's AC.
- [x] **Found a real coverage gap in Neo's own tests, closed it myself** (same pattern as Sprint 2's mask-event feed and Phase 2's cross-process dedup test): his 4 new panel tests only assert row *counts*, never actual cell content. Added `test_row_content_shows_the_real_resource_and_label_not_just_a_count` — confirms the rendered row actually shows the real identity, label, and a non-empty human-readable timestamp, not just "some row exists."
- [x] `make test`: 223/223 passing (222 + my 1 new test).
- [x] **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-4` (Sprint 4, STORY-1004)

## Progress
- [x] **Real, non-mocked cache-corruption test via the actual installed `scalene-guard` binary** (not a unit test calling Python functions in-process): wrote invalid JSON to a real cache file, piped a real hook payload through the real binary as a subprocess. Confirmed exit code 2, plain-language stderr ("scalene-guard: fatal scanning-machinery failure — Scan cache store ... is corrupted: ..."), empty stdout, no traceback. Also confirmed the ordinary/ok case stays exit 0 with real JSON output, for contrast.
- [x] Independently verified Neo's claim that `ScannerMachineryError` is genuinely unreachable via a real (non-mocked) `scalene-guard` invocation, rather than trusting the code comment — grepped `resource_verifier.py`/`scan_cache.py`/`identify()` myself and confirmed none of them ever call `.scan()`. Confirmed honest framing, not overclaimed.
- [x] **Real, end-to-end onboard-suggestion loop test via the actual installed `scg`/`scalene-guard` binaries** (strongest possible verification — real subprocesses, not function calls): tainted a session, got a real masked response with a real suggested command, ran that exact command through the real `scg` binary, confirmed the cache was written, then confirmed the identical call is now genuinely `allow` with no `updatedInput`/`systemMessage`. The loop Neo and I both confirmed broken in Phase 3 is genuinely closed.
- [x] `make test`: 210/210 passing, 0 skipped.
- [x] **Verdict: PASS.**

## Task Description (prior): `*qa uat phase-3` (Sprint 4, STORY-1002/1003)

## Progress
- [x] Independently grepped `src/scalene/` for `PolicyRule`/`allowlist` — confirmed the class and YAML rule-matching are genuinely gone from `policy_config.py`; remaining hits are `onboard.py` (still legitimately writes the YAML `allowlist` list — expected, unchanged until Phase 4) plus historical/explanatory docstring mentions, not live matching code.
- [x] Verified the first-sighting message wording live (not just read the code): a never-before-seen destination produces "This destination has not yet been verified — Scalene defaults to caution..."; a cached, actually-verified-untrusted destination produces "This destination is known to be untrusted." — correctly distinct, matching Smith's Gate 1/2 note.
- [x] Independently re-ran `tests/test_performance.py`'s both NFR tests myself: `NFR-Perf-Steady-State` (<15ms) and `NFR-Perf-FirstSighting` (<25ms/resource) both pass for real.
- [x] **Independently confirmed the onboard-suggestion regression Neo flagged, rather than trusting the skip reason's claim**: bypassed the `@unittest.skip` decorator and ran the test body directly — reproduced the exact failure (rule written to `scalene_policy.yaml`, identical call still masked afterward with the correct "not yet verified" wording). Not exaggerated, not a false positive.
- [x] `make test`: 200/200 passing, 1 documented skip (the confirmed regression above).
- [x] **Verdict: PASS.** Carrying Neo's Smith-gate flag forward explicitly, independently verified as real — this must not become a generic "Phase 3 done, all green" handoff to Smith.

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
