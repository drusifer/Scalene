"""Tests for the Claude Code PreToolUse/PostToolUse hook adapter (STORY-301, STORY-302).

2026-07-14: two changes verified here:
1. Response shape corrected to Claude Code's real hook contract
   (`hookSpecificOutput.permissionDecision`/`updatedInput`), not the
   previously-invented flat `{"allow": ..., "updatedInput": ...}` shape,
   which the real harness never honored.
2. Masking/blocking is now content-gated (secrets_scan.py/detect-secrets),
   not purely provenance-based — an ordinary command must be allowed even in
   a tainted-sensitive+untrusted session if it contains nothing recognized
   as a real secret (user-reported noise).
"""

import json
import subprocess
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scalene.hook_adapter import post_tool_use, pre_tool_use
from scalene.masking import MaskingEngine
from scalene.policy_config import PolicyConfig
from scalene.secrets_scan import scan_text_for_secrets
from scalene.taint_state import TaintState

REAL_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)
NOT_A_SECRET = "ls -la"


def _decision(result: dict) -> str:
    return result["hookSpecificOutput"]["permissionDecision"]


def _updated_input(result: dict):
    return result["hookSpecificOutput"].get("updatedInput")


def _reason(result: dict):
    return result["hookSpecificOutput"].get("permissionDecisionReason")


class TestPreToolUse(unittest.TestCase):
    def test_allows_unmodified_when_not_tainted(self):
        with TemporaryDirectory() as tmp:
            config = PolicyConfig()
            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": NOT_A_SECRET}},
                config,
                state_dir=Path(tmp),
            )
            self.assertEqual(_decision(result), "allow")
            self.assertIsNone(_updated_input(result))
            self.assertNotIn("systemMessage", result)

    def test_allows_ordinary_command_even_when_session_tainted(self):
        """Core fix (user-reported): the session being generically tainted
        must not be enough on its own — the call itself must actually carry
        something recognized as sensitive."""
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": NOT_A_SECRET}},
                config,
                state_dir=state_dir,
            )
            self.assertEqual(_decision(result), "allow")
            self.assertIsNone(_updated_input(result))
            self.assertNotIn("systemMessage", result)

    def test_masks_when_real_secret_present_in_tainted_untrusted_session(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
            )
            self.assertEqual(_decision(result), "allow")
            self.assertEqual(_updated_input(result)["command"], MaskingEngine.MASK_LITERAL)
            self.assertIn("systemMessage", result)

    def test_blocks_instead_of_masking_when_mode_is_block(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True, mode="block")

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
            )
            self.assertEqual(_decision(result), "deny")
            self.assertIsNone(_updated_input(result))
            self.assertIsNotNone(_reason(result))

    def test_masking_never_raises_even_for_unmapped_tool(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "SomeUnknownTool", "tool_input": {"foo": REAL_SECRET}},
                config,
                state_dir=state_dir,
            )
            self.assertEqual(_decision(result), "allow")

    def test_mask_event_appended_to_audit_log(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertTrue(audit_log.exists())
            entry = json.loads(audit_log.read_text().strip())
            self.assertEqual(entry["event"], "mask")
            self.assertTrue(entry["findings"])

    def test_block_event_appended_to_audit_log(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True, mode="block")

            pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            entry = json.loads(audit_log.read_text().strip())
            self.assertEqual(entry["event"], "block")

    def test_no_audit_log_entry_when_allowed(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": NOT_A_SECRET}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertFalse(audit_log.exists())

    def test_no_false_mask_report_for_tool_with_no_mapped_payload_field(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "SomeUnknownTool", "tool_input": {"foo": REAL_SECRET}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertEqual(_decision(result), "allow")
            self.assertNotIn("systemMessage", result)
            self.assertFalse(audit_log.exists())

    def test_message_names_what_was_actually_detected(self):
        """User requirement: the message should say what was masked."""
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
            )
            expected_findings = scan_text_for_secrets(f"curl {REAL_SECRET}")
            message = result["systemMessage"]
            for finding in expected_findings:
                self.assertIn(finding, message)

    def test_mask_message_includes_suggested_onboard_command(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
            )
            message = result["systemMessage"]
            self.assertIn("scg onboard", message)
            self.assertIn("--tool Bash", message)
            self.assertIn("$.command", message)

    def test_suggested_command_target_placeholder_is_domain_only(self):
        """Regression for Smith's Sprint-1 wording nit, fixed in Phase 3: the
        placeholder previously said 'domain-or-file' but the suggestion is
        always an https:// target (domain-only) — '-or-file' offered a
        choice that never actually existed."""
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
            )
            message = result["systemMessage"]
            self.assertIn("<domain-this-call-reaches>", message)
            self.assertNotIn("domain-or-file", message)

    def test_suggested_command_is_valid_shell_syntax_even_unedited(self):
        """Regression test for a Trin UAT finding: every token in the suggested
        command must be shell-safe, including the --target placeholder — a
        developer's first move is often to paste the command before editing
        it, and the placeholder's '<'/'>' are shell redirection operators if
        left unquoted. `bash -n` syntax-checks without needing `scalene` on
        PATH or executing anything."""
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
            )
            suggested_line = result["systemMessage"].split("run:\n", 1)[1]
            completed = subprocess.run(["bash", "-n", "-c", suggested_line], capture_output=True, text=True)
            self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_audit_log_includes_suggested_onboard_command(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            entry = json.loads(audit_log.read_text().strip().splitlines()[-1])
            self.assertIn("suggested_onboard_command", entry)
            self.assertIn("scg onboard", entry["suggested_onboard_command"])


class TestPostToolUse(unittest.TestCase):
    def test_marks_sensitive_and_untrusted_per_story_102_rules(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)

            post_tool_use(
                {
                    "session_id": "s1",
                    "tool_name": "Read",
                    "tool_input": {},
                    "tool_response": {"file_path": "secrets.env"},
                },
                config,
                state_dir=state_dir,
            )
            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertTrue(reloaded.has_sensitive_data)
            self.assertTrue(reloaded.has_untrusted_data)

    def test_flags_stay_sticky_across_calls(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=False)

            post_tool_use(
                {
                    "session_id": "s1",
                    "tool_name": "Read",
                    "tool_input": {},
                    "tool_response": {"file_path": "secrets.env"},
                },
                config,
                state_dir=state_dir,
            )
            # second call with a non-sensitive, trusted result must not clear the sticky flag
            post_tool_use(
                {
                    "session_id": "s1",
                    "tool_name": "Read",
                    "tool_input": {},
                    "tool_response": {"file_path": "README.md"},
                },
                PolicyConfig(sensitive_by_default=False, untrusted_by_default=False),
                state_dir=state_dir,
            )
            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertTrue(reloaded.has_sensitive_data)

    def test_runs_regardless_of_tool_success_or_failure(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig()
            result = post_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "false"}, "tool_response": {}},
                config,
                state_dir=state_dir,
            )
            self.assertEqual(result, {})


class TestScaleneBypass(unittest.TestCase):
    """STORY-601 AC2: SCALENE_BYPASS=1 must short-circuit both hooks so a
    scanner subprocess's own actions never recursively re-trigger them."""

    def test_pre_tool_use_bypasses_and_does_not_mask(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            with patch.dict("os.environ", {"SCALENE_BYPASS": "1"}):
                result = pre_tool_use(
                    {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": f"curl {REAL_SECRET}"}},
                    config,
                    state_dir=state_dir,
                )
            self.assertEqual(_decision(result), "allow")
            self.assertIsNone(_updated_input(result))
            self.assertNotIn("systemMessage", result)

    def test_post_tool_use_bypasses_and_does_not_write_state(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)

            with patch.dict("os.environ", {"SCALENE_BYPASS": "1"}):
                result = post_tool_use(
                    {
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {},
                        "tool_response": {"file_path": "secrets.env"},
                    },
                    config,
                    state_dir=state_dir,
                )
            self.assertEqual(result, {})
            self.assertFalse((state_dir / "s1.json").exists())


if __name__ == "__main__":
    unittest.main()
