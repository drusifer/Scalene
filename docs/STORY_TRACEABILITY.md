# Story → Test Traceability (Sprint 1 Task 4.3)

Every acceptance criterion in `docs/USER_STORIES.md`, mapped to the specific test(s) that verify it. Built for Trin's full cross-story UAT pass. Two AC bullets are flagged as **design-verified, not test-verified** — noted explicitly rather than glossed over.

## STORY-101 — Sticky taint flags

| AC | Test |
|---|---|
| Both flags default `false` at session start | `test_taint_state.py::TestTaintStateDefaults::test_flags_default_false` |
| A flag flipped `true` never reverts except explicit reset | `test_taint_state.py::TestTaintStateSticky::test_mark_sensitive_is_sticky`, `test_mark_untrusted_is_sticky`, `test_no_public_api_flips_true_back_to_false_except_reset` |
| Flag state queryable without re-scanning prior calls | `test_taint_state.py::TestTaintStatePersistence::test_queryable_without_rescanning_prior_calls` |

## STORY-102 — Provenance matching sets flags

| AC | Test |
|---|---|
| Rule matching runs on every tool result via `post_tool_call` | `test_hook_adapter.py::TestPostToolUse::test_marks_sensitive_and_untrusted_per_story_102_rules`, `test_runs_regardless_of_tool_success_or_failure` |
| Matching sensitive inventory sets only `has_sensitive_data` | `test_policy_config.py::TestPolicyConfigEvaluate::test_no_match_falls_back_to_defaults` (isolates is_sensitive independent of is_trusted) |
| Non-match against trusted inventory sets only `has_untrusted_data` | same as above; also `test_hook_adapter.py::TestPostToolUse` |
| Both flags can be true simultaneously (Triangle-of-Doom) | `test_policy_config.py::test_both_flags_can_be_true_simultaneously` |

## STORY-201 — YAML policy schema

| AC | Test |
|---|---|
| Schema supports both list sections w/ tool/jsonpath/pattern/description | `test_policy_config.py::TestPolicyConfigLoading::test_from_yaml_parses_full_schema` |
| Schema supports `defaults` section | same test; `test_from_yaml_applies_defaults_when_sections_missing` |
| JSONPath matches nested params, `$.command`, URLs, file paths, DB table/column | `test_policy_config.py::TestPolicyConfigEvaluate::test_matches_nested_json_parameters`, `test_matches_shell_command_string`, `test_matches_url_path`, `test_matches_db_table_column_target` |
| Invalid YAML fails with clear error, not silent no-op | `test_policy_config.py::test_invalid_yaml_raises_clear_error_not_silent_noop`, `test_rule_missing_required_field_raises` |

## STORY-202 — Fail-safe JSONPath evaluation

| AC | Test |
|---|---|
| Parse/match failure → `sensitive=true, trusted=false` | `test_policy_config.py::test_malformed_jsonpath_fails_safe` |
| Fail-safe path is logged, not silent | `test_policy_config.py::test_fail_safe_path_is_logged_not_silent` (uses `assertLogs`) |

## STORY-301 — PreToolUse hook

| AC | Test |
|---|---|
| Hook receives full tool name + payload before execution | `test_hook_adapter.py::TestPreToolUse::test_returns_allow_and_updated_input_shape` |
| Evaluation completes in <15ms (NFR-Performance) | `test_performance.py::test_evaluation_stays_under_15ms_budget` (formal; supersedes Phase 2/3 informal sanity checks) |
| Decision is execute-directly or execute-with-masked-payload | `test_hook_adapter.py::test_allows_unmodified_when_not_tainted`, `test_masks_when_session_tainted_sensitive_and_target_untrusted` |
| Cross-platform (NFR-Portability) | **Design-verified, not test-verified**: pure Python + `pathlib`/`filelock`, no OS-specific syscalls, no daemon/background process (architecture §2 "no daemon required"). No Docker/cloud test matrix exists in this repo to exercise this directly. |

## STORY-302 — PostToolUse hook

| AC | Test |
|---|---|
| Runs after every call, success or failure | `test_hook_adapter.py::TestPostToolUse::test_runs_regardless_of_tool_success_or_failure` |
| Updates flags per STORY-102 rules | `test_hook_adapter.py::test_marks_sensitive_and_untrusted_per_story_102_rules`, `test_flags_stay_sticky_across_calls` |
| Sanitized (post-masking) output returned to context window | Satisfied by design: masking happens in `pre_tool_use` before the tool executes, so `post_tool_use`'s `tool_response` already reflects it; see `hook_adapter.post_tool_use` docstring. |

## STORY-401 — Structural masking

| AC | Test |
|---|---|
| Trigger: sensitive AND untrusted AND target untrusted | `test_masking.py::TestMaskingEngineDecide` (4 tests covering all combinations) |
| Replaces payload field with mask literal | `test_masking.py::test_replaces_payload_field_with_literal` |
| Structural/blind, not partial redaction | `test_masking.py::test_is_structural_not_partial_redaction` |
| Non-payload arguments preserved | `test_masking.py::test_preserves_non_payload_fields` |
| Never throws a runtime error | `test_masking.py::test_never_raises_on_missing_payload_field`, `test_never_raises_on_none_payload_field`, `test_never_raises_on_non_dict_args`; `test_hook_adapter.py::test_masking_never_raises_even_for_unmapped_tool` |

## STORY-501 — Onboarding CLI

| AC | Test |
|---|---|
| Accepts tool/jsonpath/pattern, writes to `scalene_policy.yaml` on success | `test_onboard.py::TestOnboardAllowlist::test_clean_target_writes_rule_and_returns_diff`, `TestOnboardTrustList::test_trusted_domain_writes_rule` |
| Allowlist: secrets scan first, fails with clear reason if found | `test_onboard.py::test_secrets_found_blocks_onboarding_with_clear_reason_and_no_write`; `test_secrets_scan.py` (detection logic) |
| Trust-list: reputation lookup first, failure blocks onboarding | `test_onboard.py::test_untrusted_ip_target_blocks_onboarding_with_no_write`; `test_reputation.py` (detection logic) |
| Attributable (git-committed) for compliance audit trail | Resolved architecturally (`ARCHITECTURE.md` §8): `onboard()` produces a diff + `audit.log` entry for the developer to review/commit themselves rather than auto-committing. Covered by `test_onboard.py::test_clean_target_writes_rule_and_returns_diff` (diff+audit log) — **no auto-commit exists, by design, so "git-committed" is a developer action this tool enables, not one it performs.** |

## STORY-601 — Scanner isolation

| AC | Test |
|---|---|
| Scanner processes isolated (separate process/sandbox) | `test_subprocess_isolation.py::test_subprocess_runs_as_separate_process` (asserts real `subprocess.run` invocation) + real end-to-end subprocess tests in the same file |
| `SCALENE_BYPASS=1` prevents recursive hook re-triggering | `test_subprocess_isolation.py::test_subprocess_env_includes_scalene_bypass`; `test_hook_adapter.py::TestScaleneBypass` (both `pre_tool_use` and `post_tool_use` short-circuit) |

---

**Summary:** `docs/USER_STORIES.md` has 31 AC bullets across the 9 stories (verified by direct count, not estimated). 29 of 31 are directly test-verified. 2 are design-verified only (STORY-301 cross-platform NFR-Portability; STORY-302's "sanitized output" is a consequence of ordering, not a separate mechanism) — flagged above rather than silently counted as tested. (Trin UAT note: an earlier draft of this doc mis-stated this as "33 of 35" — corrected during Phase 4 UAT.)
