# Current Task

**Status:** Trin's UAT fix applied (unquoted `--target` placeholder), re-handed to Trin
**Assigned to:** Neo (handing to Trin)
**Started:** 2026-07-09

## Task Description
Smith's UX consult (onboarding-suggestion feature, approved by user) handed off `@Neo *swe impl`: extend `pre_tool_use`'s mask `systemMessage` + audit-log entry to include a ready-to-run `scalene onboard` command built from the real `tool_input`, so a developer never has to hand-write a JSONPath/regex with zero example. Also folded in the previously-diagnosed false-positive-mask-reporting bug (below), since generating a plausible-looking suggested command on top of an already-fabricated "masked" message would have made that bug worse, not better.

## Progress
- [x] Test-first: added 3 failing tests to `tests/test_hook_adapter.py` (suggested-command-in-message, suggested-command-in-audit-log, no-false-mask-report-for-unmapped-tool), confirmed all 3 failed for the right reason before implementing
- [x] `hook_adapter.py`: added `_suggest_onboard_command()` — builds a shell-safe `scalene onboard --list-type trust --tool ... --jsonpath '$.<field>' --pattern '^<escaped-literal>$' --target <placeholder>` command. Chose **trust-list** (not allowlist) because `is_trusted` is the only `MatchResult` field `MaskingEngine.decide()` actually checks in `pre_tool_use` — an allowlist suggestion would not have stopped a repeat of the same call.
- [x] `pre_tool_use`: uses `updated_input is tool_input` identity check (relies on `MaskingEngine.apply_mask`'s existing no-op-returns-same-object behavior — no change needed to `masking.py`) to detect whether a mask actually happened; if not, returns cleanly with no `systemMessage`/audit entry. **This fixes the previously-found false-positive bug** (Read/WebSearch/ToolSearch/unmapped tools were logging "masked" events that masked nothing).
- [x] Wrote a new permanent e2e test (`tests/test_onboard_suggestion_e2e.py`, at the user's request instead of an ad-hoc throwaway script): extracts the real suggested command out of the real `systemMessage`, fills in the target placeholder, runs it through the real `scalene_main` CLI dispatch (not a shortcut into `onboard()`), reloads the policy, and asserts the identical call is no longer masked. Closes the full loop, not just message formatting.
- [x] Manual smoke-test via `.venv/bin/scalene onboard ...` with the exact generated command confirmed it's copy-paste-runnable end-to-end (superseded by the permanent e2e test above)
- [x] Trin's UAT (round 1): **FAILED** — the `--target <placeholder>` token wasn't `shlex.quote()`'d like every other arg; `<`/`>` are shell redirection operators, so pasting the message unedited hit a bash syntax error before `scalene` even ran (Trin confirmed by literally running it).
- [x] Fix: wrapped the placeholder in `shlex.quote()` too (`hook_adapter.py`, one line)
- [x] Added regression test `test_suggested_command_is_valid_shell_syntax_even_unedited` — runs the exact suggested line through `bash -n -c` (syntax check only, no `scalene` on PATH needed) so this bug class can't silently reappear
- [x] `make test`: 88/88 passing (84 prior + 3 unit + 1 e2e + 1 shell-safety regression)

## Blockers
None. Re-handed to Trin for re-verification of just the fix.

## Oracle Consultations
None yet

---
*Last updated: 2026-07-09*
