"""Tests for the Claude Code PreToolUse/PostToolUse hook adapter (STORY-301, STORY-302)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scalene.hook_adapter import post_tool_use, pre_tool_use
from scalene.masking import MaskingEngine
from scalene.policy_config import PolicyConfig
from scalene.taint_state import TaintState


class TestPreToolUse(unittest.TestCase):
    def test_returns_allow_and_updated_input_shape(self):
        with TemporaryDirectory() as tmp:
            config = PolicyConfig()
            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}},
                config,
                state_dir=Path(tmp),
            )
            self.assertIn("allow", result)
            self.assertIn("updatedInput", result)

    def test_allows_unmodified_when_not_tainted(self):
        with TemporaryDirectory() as tmp:
            config = PolicyConfig()
            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}},
                config,
                state_dir=Path(tmp),
            )
            self.assertTrue(result["allow"])
            self.assertEqual(result["updatedInput"], {"command": "ls"})
            self.assertNotIn("systemMessage", result)

    def test_masks_when_session_tainted_sensitive_and_target_untrusted(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "curl secret"}},
                config,
                state_dir=state_dir,
            )
            self.assertTrue(result["allow"])
            self.assertEqual(result["updatedInput"]["command"], MaskingEngine.MASK_LITERAL)
            self.assertIn("systemMessage", result)

    def test_masking_never_raises_even_for_unmapped_tool(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            taint = TaintState(
                session_id="s1", has_sensitive_data=True, has_untrusted_data=True, state_dir=state_dir
            )
            taint.save()
            config = PolicyConfig(untrusted_by_default=True)

            result = pre_tool_use(
                {"session_id": "s1", "tool_name": "SomeUnknownTool", "tool_input": {"foo": "bar"}},
                config,
                state_dir=state_dir,
            )
            self.assertTrue(result["allow"])

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
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "curl secret"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertTrue(audit_log.exists())
            self.assertIn("mask", audit_log.read_text())

    def test_no_audit_log_entry_when_not_masked(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            audit_log = Path(tmp) / "audit.log"
            config = PolicyConfig()

            pre_tool_use(
                {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "ls"}},
                config,
                state_dir=state_dir,
                audit_log_path=audit_log,
            )
            self.assertFalse(audit_log.exists())


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
            self.assertIn("sanitizedOutput", result)


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
                    {"session_id": "s1", "tool_name": "Bash", "tool_input": {"command": "curl secret"}},
                    config,
                    state_dir=state_dir,
                )
            self.assertTrue(result["allow"])
            self.assertEqual(result["updatedInput"], {"command": "curl secret"})
            self.assertNotIn("systemMessage", result)

    def test_post_tool_use_bypasses_and_does_not_write_state(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)

            with patch.dict("os.environ", {"SCALENE_BYPASS": "1"}):
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
            self.assertFalse((state_dir / "s1.json").exists())


if __name__ == "__main__":
    unittest.main()
