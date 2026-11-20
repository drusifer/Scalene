# Neo — Sprint 9 (E15) Phase 4 — correction notes (2026-07-21)

## Why this changed after Phase 4 was already gated and approved
Direct user request, after Smith's gate had already approved the original implicit-in-memory-rule design: "if a yaml doesn't exist then create one with a rule for the project folder but with the timestamp uninitialized so that it scans on first tool use — trying to avoid an implicit special case." Reworked the mechanism accordingly rather than treating the prior approval as locking in a design the user was actively asking to simplify.

## What changed
- **Removed**: `PolicyConfig.project_root` field, `__post_init__`'s implicit-rule construction, `scg onboard --list`'s synthetic default line (and its `project_root` parameter on `_list_inventory()`).
- **Added**: `policy_config.write_default_project_policy(path, project_root)` — writes a real `rules:` entry to a brand-new `scalene_policy.yaml`, same shape as any hand-written or onboard-authored rule. `cli.py`'s `main()` calls it only when the policy file doesn't exist yet, then always loads via the ordinary `PolicyConfig.from_yaml()` — one code path, not two.
- **"Timestamp uninitialized" (user's own phrase)**: confirmed `write_default_project_policy()` never touches `ScanCache` — no pre-seeded entry, so first tool-use against a project file still runs a real scan through the normal `uncleared → validated_allow` progression, identical to any other resource.

## A real bug I found and fixed while implementing this, not assumed away
The new rule's pattern is broad by design (matches almost anything under the project root) and gets written to the file *first*, before any onboarding has ever happened. `_find_matching_rule()` returns the first declaration-order match. If a developer later ran `scg onboard --mode block` on a specific sensitive file *inside* their own project, the existing `_write_rule()` (unchanged since E13/sec16) simply appends new rules to the end of the list — meaning the broad default (already first) would always win, and the developer's explicit, more specific block decision would be silently unreachable forever. This is a real correctness/discoverability bug that would only surface in a two-decision sequence (default created, then something more specific onboarded later) — exactly the kind of thing worth tracing through deliberately, not assuming append-order is always fine.

Fixed by giving the auto-created rule a fixed, shared description (`PROJECT_FOLDER_DEFAULT_DESCRIPTION`, in `policy_config.py`) and having `_write_rule()` insert new rules *before* it when present, rather than always appending at the end. Every other rule-write (no default present) keeps its existing append-at-end behavior — verified via `test_appends_to_an_existing_rules_list_without_clobbering`, unchanged and still passing. New regression test: `test_onboarded_rule_is_inserted_before_the_project_folder_default_not_after`.

## Test changes
- Removed: `test_resource_verifier.py`'s old `TestProjectFolderDefault` tests that used the removed `project_root=` constructor arg and `test_explicit_user_rule_still_wins...` (superseded by the insertion-order fix, which is a stronger, more general guarantee than "wins if present"). Removed `test_onboard.py`'s 2 synthetic-`--list`-line tests. Reverted the 7 "+1 for the implicit rule" count fixes across `test_policy_config.py`/`test_onboard.py` back to their original values (no longer applicable — `from_yaml()` doesn't append anything automatically anymore).
- Added: `test_policy_config.py::TestWriteDefaultProjectPolicy` (5 tests — real file written, parses as an ordinary rule, pattern matches in/out of project root correctly, no cache entry pre-seeded). `test_resource_verifier.py::TestProjectFolderDefault` rewritten against the real written file (4 tests — clean file validated-allow + sensitivity escalation, second file doesn't hit the wall, coexistence with hardcoded-restricted paths, outside-project unaffected). `test_cli.py::TestGuardCreatesDefaultProjectPolicy` (3 tests — first call creates it, second call reuses without duplicating/rewriting, an existing policy file is never touched). `test_onboard.py`'s new insertion-order regression test.

## Verification
`make test`: 387/387. Also ran the real CLI end-to-end (not just unit tests): a fresh `scalene-guard` invocation with no policy file present creates one with exactly the expected rule.

```
$ echo '{"hook_event_name": "PreToolUse", ...}' | python -m scalene.cli --policy-path ./scalene_policy.yaml ...
$ cat scalene_policy.yaml
rules:
- tool: .*
  pattern: ^/tmp/e15_final_check(/|$)
  sensitivity: internal
  mode: allow
  scanner: secrets
  description: project folder default (auto-created)
```
