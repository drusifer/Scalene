"""Tests for the `scalene-guard` hook dispatcher and `scalene` CLI (Task 4.1)."""

import io
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from scalene.cli import main as guard_main
from scalene.main_cli import main as scalene_main
from scalene.scanner import ScannerMachineryError


def _run_guard(payload, policy_path, state_dir, cache_path=None):
    stdin = io.StringIO(json.dumps(payload))
    stdout = io.StringIO()
    stderr = io.StringIO()
    if cache_path is None:
        cache_path = Path(state_dir).parent / "scan_cache.json"
    with patch("sys.stdin", stdin), patch("sys.stdout", stdout), patch("sys.stderr", stderr):
        exit_code = guard_main(
            ["--policy-path", str(policy_path), "--state-dir", str(state_dir), "--cache-path", str(cache_path)]
        )
    return exit_code, stdout.getvalue(), stderr.getvalue()


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
            exit_code, out, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state")
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
            exit_code, out, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", state_dir)
            self.assertEqual(exit_code, 0)
            self.assertEqual(json.loads(out), {})
            self.assertTrue((state_dir / "s1.json").exists())

    def test_unknown_hook_event_fails_safe_and_allows(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = {"hook_event_name": "SomethingElse", "session_id": "s1"}
            exit_code, out, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state")
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
            exit_code, out, err = _run_guard(payload, policy_path, tmp_path / "state")
            self.assertEqual(exit_code, 0)
            result = json.loads(out)
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")

    def test_corrupted_scan_cache_is_fatal_exit_code_2(self):
        # STORY-1004: the scan cache store itself is unreadable -- a
        # scanning-machinery failure, distinct from an ordinary scan
        # finding, which always stays exit 0. Exit code 2 specifically --
        # verified 2026-07-15 against Claude Code's real hook contract
        # (only exit 2 blocks a PreToolUse call; exit 1 is a documented,
        # easy-to-make mistake that's silently non-blocking).
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "scan_cache.json"
            cache_path.write_text("{not valid json")
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Read",
                "tool_input": {"file_path": str(tmp_path / "some_file.md")},
            }
            exit_code, out, err = _run_guard(
                payload, tmp_path / "scalene_policy.yaml", tmp_path / "state", cache_path=cache_path
            )
            self.assertEqual(exit_code, 2)
            self.assertEqual(out, "")

    def test_fatal_exit_message_is_plain_language_not_a_raw_traceback(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cache_path = tmp_path / "scan_cache.json"
            cache_path.write_text("{not valid json")
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Read",
                "tool_input": {"file_path": str(tmp_path / "some_file.md")},
            }
            _, _, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state", cache_path=cache_path)
            self.assertIn("scalene-guard", err)
            self.assertNotIn("Traceback", err)

    def test_ordinary_scan_finding_stays_exit_zero_not_confused_with_machinery_failure(self):
        # Sanity check: a real, ordinary mask decision (not a machinery
        # failure) must NOT be affected by the new fatal-exit path.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            exit_code, out, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state")
            self.assertEqual(exit_code, 0)
            self.assertEqual(err, "")

    def test_scanner_machinery_error_is_also_fatal_exit_code_2(self):
        # ScannerMachineryError only actually fires inside the detached
        # background worker today (Scanner.scan() never runs synchronously
        # in scalene-guard's own process) -- this test proves the catch
        # clause itself works correctly via a direct patch, as defensive
        # coverage for if that ever changes, not because it's reachable
        # through today's real call graph.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            with patch(
                "scalene.cli.pre_tool_use",
                side_effect=ScannerMachineryError("simulated scanner machinery failure"),
            ):
                exit_code, out, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", tmp_path / "state")
            self.assertEqual(exit_code, 2)
            self.assertIn("scalene-guard", err)
            self.assertNotIn("Traceback", err)

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
            cache_path = tmp_path / "scan_cache.json"

            exit_code = scalene_main(["onboard", "--target", f"file://{target}", "--cache-path", str(cache_path)])
            self.assertEqual(exit_code, 0)
            self.assertTrue(cache_path.exists())

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
