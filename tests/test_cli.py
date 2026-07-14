"""Tests for the `scalene-guard` hook dispatcher and `scalene` CLI (Task 4.1)."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from scalene.cli import main as guard_main
from scalene.main_cli import main as scalene_main


def _run_guard(payload, policy_path, state_dir):
    stdin = io.StringIO(json.dumps(payload))
    stdout = io.StringIO()
    with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
        exit_code = guard_main(["--policy-path", str(policy_path), "--state-dir", str(state_dir)])
    return exit_code, stdout.getvalue()


class TestGuardCliDispatch(unittest.TestCase):
    def test_pre_tool_use_dispatch_returns_allow(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            exit_code, out = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state")
            self.assertEqual(exit_code, 0)
            result = json.loads(out)
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_post_tool_use_dispatch_updates_state(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_dir = tmp_path / "state"
            payload = {
                "hook_event_name": "PostToolUse",
                "session_id": "s1",
                "tool_name": "Read",
                "tool_input": {},
                "tool_response": {"file_path": "secrets.env"},
            }
            exit_code, out = _run_guard(payload, tmp_path / "scalene_policy.yaml", state_dir)
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(out), {})
            self.assertTrue((state_dir / "s1.json").exists())

    def test_unknown_hook_event_fails_safe_and_allows(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = {"hook_event_name": "SomethingElse", "session_id": "s1"}
            exit_code, out = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state")
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(out), {})

    def test_malformed_policy_yaml_fails_safe_and_allows(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            policy_path.write_text(": not: valid: yaml: [")
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            exit_code, out = _run_guard(payload, policy_path, tmp_path / "state")
            self.assertEqual(exit_code, 0)
            result = json.loads(out)
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_malformed_stdin_fails_safe_and_allows(self):
        stdin = io.StringIO("not valid json")
        stdout = io.StringIO()
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            with patch("sys.stdin", stdin), patch("sys.stdout", stdout):
                exit_code = guard_main(
                    ["--policy-path", str(tmp_path / "scalene_policy.yaml"), "--state-dir", str(tmp_path / "state")]
                )
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(stdout.getvalue()), {})


class TestScaleneMainCli(unittest.TestCase):
    def test_onboard_subcommand_dispatches(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            policy_path = tmp_path / "scalene_policy.yaml"

            exit_code = scalene_main(
                [
                    "onboard",
                    "--list-type", "allowlist",
                    "--tool", "Read",
                    "--jsonpath", "$.file_path",
                    "--pattern", r"\.md$",
                    "--target", str(target),
                    "--policy-path", str(policy_path),
                ]
            )
            self.assertEqual(exit_code, 0)
            self.assertTrue(policy_path.exists())

    def test_monitor_subcommand_dispatches(self):
        # Only tests dispatch wiring — monitor.main's own behavior (incl. the
        # missing-textual-extra fallback) is covered in test_monitor_cli.py.
        # Must patch the _SUBCOMMANDS dict entry itself (not the `monitor_main`
        # name) since the dict already bound the real function object at
        # import time — patching the module attribute alone would not stop
        # the real TUI from launching (and hanging) in this test.
        mock_monitor = Mock(return_value=0)
        with patch.dict("scalene.main_cli._SUBCOMMANDS", {"monitor": mock_monitor}):
            exit_code = scalene_main(["monitor"])
        mock_monitor.assert_called_once_with([])
        self.assertEqual(exit_code, 0)

    def test_unknown_subcommand_returns_error(self):
        exit_code = scalene_main(["bogus"])
        self.assertNotEqual(exit_code, 0)

    def test_no_subcommand_returns_error(self):
        exit_code = scalene_main([])
        self.assertNotEqual(exit_code, 0)


if __name__ == "__main__":
    unittest.main()
