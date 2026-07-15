"""Tests for the `scg monitor` data layer (STORY-701/702)."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scalene.monitor_data import (
    AuditTail,
    MaskEvent,
    ScanResultInfo,
    SessionInfo,
    apply_onboard_command,
    discover_scan_results,
    discover_sessions,
)
from scalene.scan_cache import ScanCache
from scalene.scanner import Resource, ScanResult


class TestDiscoverSessions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_state_dir_returns_empty(self):
        missing = self.state_dir / "does-not-exist"
        self.assertEqual(discover_sessions(missing), [])

    def test_empty_state_dir_returns_empty(self):
        self.assertEqual(discover_sessions(self.state_dir), [])

    def test_reads_taint_flags_from_state_file(self):
        (self.state_dir / "abc.json").write_text(
            json.dumps({"session_id": "abc", "has_sensitive_data": True, "has_untrusted_data": False})
        )
        sessions = discover_sessions(self.state_dir)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(
            sessions[0],
            SessionInfo(session_id="abc", has_sensitive_data=True, has_untrusted_data=False, updated_at=sessions[0].updated_at),
        )

    def test_multiple_sessions_sorted_most_recent_first(self):
        import os
        import time

        older = self.state_dir / "older.json"
        newer = self.state_dir / "newer.json"
        older.write_text(json.dumps({"session_id": "older", "has_sensitive_data": False, "has_untrusted_data": False}))
        # Force a distinct, ordered mtime rather than relying on real-clock timing granularity.
        old_time = time.time() - 100
        os.utime(older, (old_time, old_time))
        newer.write_text(json.dumps({"session_id": "newer", "has_sensitive_data": False, "has_untrusted_data": False}))

        sessions = discover_sessions(self.state_dir)
        self.assertEqual([s.session_id for s in sessions], ["newer", "older"])

    def test_malformed_state_file_is_skipped_not_raised(self):
        (self.state_dir / "broken.json").write_text("{not valid json")
        (self.state_dir / "good.json").write_text(
            json.dumps({"session_id": "good", "has_sensitive_data": False, "has_untrusted_data": False})
        )
        sessions = discover_sessions(self.state_dir)
        self.assertEqual([s.session_id for s in sessions], ["good"])


class TestDiscoverScanResults(unittest.TestCase):
    """STORY-1005: scg monitor's resource panel reads .scalene/scan_cache.json
    directly (via ScanCache.all_entries()), not a parallel summary that
    could drift from the real store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_cache_file_returns_empty(self):
        self.assertEqual(discover_scan_results(self.cache_path), [])

    def test_completed_scans_are_listed(self):
        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity="/abs/a.md", scanner_name="secrets"), ScanResult(label="public"))
        cache.put(
            Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
            ScanResult(label="trusted"),
        )

        results = discover_scan_results(self.cache_path)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(r, ScanResultInfo) for r in results))
        identities = {r.identity for r in results}
        self.assertEqual(identities, {"/abs/a.md", "internal.example.com"})

    def test_results_are_newest_first(self):
        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity="/abs/older.md", scanner_name="secrets"), ScanResult(label="public"))
        import time

        time.sleep(0.01)
        cache.put(Resource(kind="file", identity="/abs/newer.md", scanner_name="secrets"), ScanResult(label="public"))

        results = discover_scan_results(self.cache_path)
        self.assertEqual([r.identity for r in results], ["/abs/newer.md", "/abs/older.md"])

    def test_in_flight_reservations_without_a_completed_scan_are_excluded(self):
        # A resource with only a pending_since reservation (no scan finished
        # yet) isn't a real result -- must not show up as if it were one.
        cache = ScanCache(self.cache_path)
        resource = Resource(kind="url", identity="never-finished.example.com", scanner_name="reputation")
        cache.try_reserve(resource)

        results = discover_scan_results(self.cache_path)
        self.assertEqual(results, [])

    def test_corrupted_cache_returns_empty_not_raised(self):
        # A live TUI must not crash on a broken cache store -- this is a
        # read-only monitoring view, not the fatal-exit hook path.
        self.cache_path.write_text("{not valid json")
        self.assertEqual(discover_scan_results(self.cache_path), [])

    def test_result_includes_reason_and_scanner_name(self):
        cache = ScanCache(self.cache_path)
        cache.put(
            Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"),
            ScanResult(label="untrusted", reason="IP-literal targets are untrusted by default"),
        )
        results = discover_scan_results(self.cache_path)
        self.assertEqual(results[0].scanner_name, "reputation")
        self.assertIn("IP-literal", results[0].reason)


class TestAuditTail(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.audit_log = Path(self._tmp.name) / "audit.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _append(self, entry: dict) -> None:
        with self.audit_log.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_missing_file_returns_empty(self):
        tail = AuditTail(self.audit_log)
        self.assertEqual(tail.poll(), [])

    def test_reads_mask_events_only_not_onboard_events(self):
        # STORY-701 AC: only surface events where masking actually occurred.
        # onboard.py writes {"event": "onboard", ...} to this same file.
        self._append({"event": "onboard", "rule": {}})
        self._append(
            {
                "event": "mask",
                "session_id": "s1",
                "tool_name": "Bash",
                "payload_field": "command",
                "suggested_onboard_command": "scg onboard ...",
            }
        )
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(
            events,
            [
                MaskEvent(
                    session_id="s1",
                    tool_name="Bash",
                    payload_field="command",
                    suggested_onboard_command="scg onboard ...",
                )
            ],
        )

    def test_reads_block_events_too(self):
        """2026-07-14: mode=block introduced a new audit event type — it must
        surface in the monitor console too, not be silently dropped like
        "onboard" events (which genuinely aren't mask/block activity)."""
        self._append(
            {
                "event": "block",
                "session_id": "s1",
                "tool_name": "Bash",
                "payload_field": "command",
                "suggested_onboard_command": "scg onboard ...",
            }
        )
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event_type, "block")

    def test_second_poll_only_returns_newly_appended_events(self):
        self._append({"event": "mask", "session_id": "s1", "tool_name": "Bash", "payload_field": "command", "suggested_onboard_command": "x"})
        tail = AuditTail(self.audit_log)
        first = tail.poll()
        self.assertEqual(len(first), 1)

        second = tail.poll()
        self.assertEqual(second, [])

        self._append({"event": "mask", "session_id": "s2", "tool_name": "Write", "payload_field": "content", "suggested_onboard_command": "y"})
        third = tail.poll()
        self.assertEqual(len(third), 1)
        self.assertEqual(third[0].session_id, "s2")

    def test_malformed_line_is_skipped_not_raised(self):
        with self.audit_log.open("a") as f:
            f.write("{not valid json\n")
        self._append({"event": "mask", "session_id": "s1", "tool_name": "Bash", "payload_field": "command", "suggested_onboard_command": "x"})
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(len(events), 1)

    def test_can_filter_by_session_id(self):
        self._append({"event": "mask", "session_id": "s1", "tool_name": "Bash", "payload_field": "command", "suggested_onboard_command": "x"})
        self._append({"event": "mask", "session_id": "s2", "tool_name": "Write", "payload_field": "content", "suggested_onboard_command": "y"})
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        s1_only = [e for e in events if e.session_id == "s1"]
        self.assertEqual(len(s1_only), 1)
        self.assertEqual(len(events), 2)


class TestApplyOnboardCommand(unittest.TestCase):
    def test_splits_command_and_runs_it_as_a_subprocess(self):
        # STORY-702: never a reimplementation — must go through the real
        # `scg` CLI as an actual subprocess, not an in-process function call.
        with patch("scalene.monitor_data.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "Rule added: {...}"
            mock_run.return_value.stderr = ""

            ok, output = apply_onboard_command("scg onboard --target https://example.com --tool Bash")

        mock_run.assert_called_once()
        called_argv = mock_run.call_args.args[0]
        self.assertEqual(called_argv, ["scg", "onboard", "--target", "https://example.com", "--tool", "Bash"])
        self.assertTrue(ok)
        self.assertIn("Rule added", output)

    def test_reports_failure_and_stderr_on_nonzero_exit(self):
        with patch("scalene.monitor_data.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 1
            mock_run.return_value.stdout = ""
            mock_run.return_value.stderr = "Onboarding blocked: secrets check failed"

            ok, output = apply_onboard_command("scg onboard --target file:///x --tool Write")

        self.assertFalse(ok)
        self.assertIn("Onboarding blocked", output)

    def test_real_subprocess_end_to_end_against_a_clean_file(self):
        # Real execution, not mocked -- proves this isn't a reimplementation
        # of onboard.py's logic, it's a genuine call to the installed CLI.
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.txt"
            target.write_text("ordinary docs, nothing sensitive")
            cache_path = Path(tmp) / "scan_cache.json"

            command = f"scg onboard --target file://{target} --cache-path {cache_path}"
            ok, output = apply_onboard_command(command)

        self.assertTrue(ok, output)
        self.assertIn("Pre-seeded the scan cache", output)

    def test_real_subprocess_end_to_end_blocks_on_a_real_secret(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target = Path(tmp) / "secret.txt"
            target.write_text(f'aws_key = "{fake_key}"')
            cache_path = Path(tmp) / "scan_cache.json"

            command = f"scg onboard --target file://{target} --cache-path {cache_path}"
            ok, output = apply_onboard_command(command)

        self.assertFalse(ok)
        self.assertIn("secrets check failed", output)
        self.assertFalse(cache_path.exists())

    def test_missing_binary_returns_a_plain_language_failure_not_a_crash(self):
        # Morpheus's Phase 3 review finding: a nonexistent/unreachable binary
        # must never raise FileNotFoundError uncaught — every other error
        # boundary in this codebase returns a result, not an exception.
        ok, output = apply_onboard_command("nonexistent-binary-xyz --foo bar")
        self.assertFalse(ok)
        self.assertIn("nonexistent-binary-xyz", output)

    def test_malformed_quoting_returns_a_plain_language_failure_not_a_crash(self):
        # Morpheus's Phase 3 review finding: a real, easy-to-make typo while
        # hand-editing a target inline (an unbalanced quote) must not crash
        # the whole TUI via an uncaught shlex ValueError.
        ok, output = apply_onboard_command('scg onboard --target "unbalanced')
        self.assertFalse(ok)
        self.assertTrue(output)  # some plain-language reason, not empty

    def test_empty_command_returns_a_plain_language_failure_not_a_crash(self):
        # Found while re-checking Morpheus's finding: a cleared/empty Input
        # submitted (e.g. select-all + delete + Enter) must not crash via
        # subprocess.run([])'s IndexError.
        ok, output = apply_onboard_command("")
        self.assertFalse(ok)
        self.assertTrue(output)


if __name__ == "__main__":
    unittest.main()
