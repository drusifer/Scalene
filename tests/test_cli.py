"""Tests for the `scalene-guard` hook dispatcher and `scalene` CLI (Task 4.1)."""

import io
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import yaml

from scalene.cli import main as guard_main
from scalene.main_cli import main as scalene_main
from scalene.scanner import ScannerMachineryError

from _env_guards import disable_remote_reputation, restore_remote_reputation

# docs/ARCHITECTURE.md sec18.3 (STORY-1503): see _env_guards.py.
setUpModule = disable_remote_reputation
tearDownModule = restore_remote_reputation


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

    def test_post_tool_use_dispatch_returns_empty_and_writes_no_state(self):
        # docs/ARCHITECTURE.md sec15: PostToolUse is a no-op now -- every
        # resource a call touches is known pre-call, so PreToolUse already
        # made the full access decision and updated state.
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
            self.assertFalse((state_dir / "s1.json").exists())

    def test_pre_tool_use_dispatch_updates_state(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            state_dir = tmp_path / "state"
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "WebFetch",
                "tool_input": {"url": "https://never-seen.example.com/x"},
            }
            exit_code, out, err = _run_guard(payload, tmp_path / "scalene_policy.yaml", state_dir)
            self.assertEqual(exit_code, 0)
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


class TestGuardCreatesDefaultProjectPolicy(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.4 (STORY-1504, corrected 2026-07-21): a
    brand-new project (no scalene_policy.yaml yet) gets one real, ordinary
    rule for its own folder written on the very first real hook call --
    not an implicit in-memory special case."""

    def test_first_call_with_no_policy_file_creates_one_with_the_project_rule(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            self.assertFalse(policy_path.exists())
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            exit_code, out, err = _run_guard(payload, policy_path, tmp_path / "state")
            self.assertEqual(exit_code, 0)
            self.assertTrue(policy_path.exists())
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(len(data["rules"]), 1)
            self.assertIn("project folder default", data["rules"][0]["description"])

    def test_second_call_reuses_the_existing_file_without_duplicating_the_rule(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            _run_guard(payload, policy_path, tmp_path / "state")
            first_write_time = policy_path.stat().st_mtime_ns
            _run_guard(payload, policy_path, tmp_path / "state")
            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(len(data["rules"]), 1)  # not duplicated
            self.assertEqual(policy_path.stat().st_mtime_ns, first_write_time)  # not rewritten either

    def test_existing_policy_file_is_never_overwritten(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            policy_path.write_text("defaults:\n  mode: block\n")
            payload = {
                "hook_event_name": "PreToolUse",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "ls"},
            }
            _run_guard(payload, policy_path, tmp_path / "state")
            data = yaml.safe_load(policy_path.read_text())
            self.assertNotIn("rules", data)  # untouched -- caller's own real config

    def test_real_subprocess_end_to_end_creates_and_reuses_the_default(self):
        # Automates the manual verification run during this phase's review
        # (a real `python -m scalene.cli` subprocess, not the in-process
        # guard_main() helper the other tests in this class use) -- same
        # "real binary, not just a function call" precedent as test_demo.py.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            state_dir = tmp_path / "state"
            cache_path = tmp_path / "cache.json"
            target = tmp_path / "main.py"
            payload = json.dumps(
                {
                    "hook_event_name": "PreToolUse",
                    "session_id": "s1",
                    "tool_name": "Read",
                    "tool_input": {"file_path": str(target)},
                }
            )

            def run_guard_subprocess():
                return subprocess.run(
                    [
                        sys.executable,
                        "-m",
                        "scalene.cli",
                        "--policy-path",
                        str(policy_path),
                        "--state-dir",
                        str(state_dir),
                        "--cache-path",
                        str(cache_path),
                    ],
                    input=payload,
                    capture_output=True,
                    text=True,
                    cwd=str(Path(__file__).resolve().parent.parent / "src"),
                    timeout=30,
                )

            self.assertFalse(policy_path.exists())
            first = run_guard_subprocess()
            self.assertEqual(first.returncode, 0, msg=first.stderr)
            result = json.loads(first.stdout)
            self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "allow")
            self.assertTrue(policy_path.exists())

            data = yaml.safe_load(policy_path.read_text())
            self.assertEqual(len(data["rules"]), 1)
            rule = data["rules"][0]
            self.assertEqual(rule["mode"], "allow")
            self.assertEqual(rule["sensitivity"], "internal")
            self.assertIn("project folder default", rule["description"])

            first_write_time = policy_path.stat().st_mtime_ns
            second = run_guard_subprocess()
            self.assertEqual(second.returncode, 0, msg=second.stderr)
            self.assertEqual(policy_path.stat().st_mtime_ns, first_write_time)  # not rewritten
            data_after = yaml.safe_load(policy_path.read_text())
            self.assertEqual(len(data_after["rules"]), 1)  # not duplicated


class TestE15EndToEndUserJourney(unittest.TestCase):
    """Sprint 9 (E15) full user story, encoded as a real, repeatable test
    with assertions -- not an ad-hoc bash transcript, same standing
    discipline as Sprint 8's TestE14EndToEndUserJourney
    (tests/test_onboard.py). Covers all 4 stories together, in one
    realistic session, via the real scalene-guard hook adapter:
    STORY-1504 (a brand-new project gets its own folder auto-trusted,
    and a second clean project file doesn't hit the usual "second
    uncleared resource" wall), STORY-1502 (a hardcoded-restricted path
    still blocks unconditionally, even inside the same project), and
    STORY-1501/1503 indirectly (the default scanner registry + composite
    reputation check are exercised as part of the ordinary call path,
    with SCALENE_SKIP_REMOTE_REPUTATION keeping the reputation check
    local-only per _env_guards.py)."""

    def test_project_files_flow_freely_but_a_restricted_path_still_blocks(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            policy_path = tmp_path / "scalene_policy.yaml"
            state_dir = tmp_path / "state"
            cache_path = tmp_path / "cache.json"
            session_id = "e15-e2e"

            first_file = tmp_path / "src" / "app.py"
            first_file.parent.mkdir()
            first_file.write_text("print('hello')")
            second_file = tmp_path / "src" / "util.py"
            second_file.write_text("def helper(): pass")

            # Step 1: first-ever call in a brand-new project (no policy file
            # yet) -- creates scalene_policy.yaml with the project-folder
            # default rule (STORY-1504), and is allowed (first sighting,
            # session was clean).
            self.assertFalse(policy_path.exists())
            payload_1 = {
                "hook_event_name": "PreToolUse",
                "session_id": session_id,
                "tool_name": "Read",
                "tool_input": {"file_path": str(first_file)},
            }
            exit_code, out, err = _run_guard(payload_1, policy_path, state_dir, cache_path)
            self.assertEqual(exit_code, 0, msg=err)
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")
            self.assertTrue(policy_path.exists())
            rules = yaml.safe_load(policy_path.read_text())["rules"]
            self.assertEqual(len(rules), 1)
            self.assertIn("project folder default", rules[0]["description"])

            # Step 2: pre-seed the cache with a REAL FileScanner result for
            # both files, as if their background first-sighting scans had
            # already completed (decide_access()'s first-sighting path is
            # fire-and-forget async -- same determinism precedent used
            # throughout this sprint's other tests, not a shortcut unique
            # to this one).
            from scalene.scan_cache import ScanCache
            from scalene.scanner import FileScanner, Resource

            cache = ScanCache(cache_path)
            for f in (first_file, second_file):
                resource = Resource(kind="file", identity=str(f), scanner_name="secrets")
                cache.put(resource, FileScanner().scan(resource))

            # Step 3: touching the FIRST file again now resolves as
            # validated_allow (clean scan + the project-folder rule).
            exit_code, out, err = _run_guard(payload_1, policy_path, state_dir, cache_path)
            self.assertEqual(exit_code, 0, msg=err)
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")

            # Step 4: the actual STORY-1504 AC -- touching a SECOND, different
            # clean project file in the same session must not hit the
            # "second uncleared resource in a low-trust session blocks"
            # wall, because it's also validated_allow via the same rule.
            payload_2 = {
                "hook_event_name": "PreToolUse",
                "session_id": session_id,
                "tool_name": "Read",
                "tool_input": {"file_path": str(second_file)},
            }
            exit_code, out, err = _run_guard(payload_2, policy_path, state_dir, cache_path)
            self.assertEqual(exit_code, 0, msg=err)
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "allow")

            # Step 5: STORY-1502 -- a hardcoded-restricted path (/etc) still
            # blocks unconditionally, even in a session that's otherwise
            # been touching only trusted project files.
            payload_restricted = {
                "hook_event_name": "PreToolUse",
                "session_id": session_id,
                "tool_name": "Read",
                "tool_input": {"file_path": "/etc/hostname"},
            }
            restricted_resource = Resource(kind="file", identity="/etc/hostname", scanner_name="secrets")
            cache.put(restricted_resource, FileScanner().scan(restricted_resource))
            exit_code, out, err = _run_guard(payload_restricted, policy_path, state_dir, cache_path)
            self.assertEqual(exit_code, 0, msg=err)
            self.assertEqual(json.loads(out)["hookSpecificOutput"]["permissionDecision"], "deny")


class TestScaleneMainCli(unittest.TestCase):
    def test_onboard_subcommand_dispatches(self):
        # docs/ARCHITECTURE.md sec17 (Sprint 8/E14): --target is gone --
        # onboard now reads a tool call and identifies targets via the
        # scanner registry, confirmed non-interactively via --yes.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            cache_path = tmp_path / "scan_cache.json"
            call_path = tmp_path / "call.json"
            call_path.write_text(f'{{"tool_name": "Read", "tool_input": {{"file_path": "{target}"}}}}')

            exit_code = scalene_main(
                [
                    "onboard",
                    "--call",
                    str(call_path),
                    "--yes",
                    "--mode",
                    "allow",
                    "--cache-path",
                    str(cache_path),
                    "--policy-path",
                    str(tmp_path / "scalene_policy.yaml"),
                ]
            )
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
