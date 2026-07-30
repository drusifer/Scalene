"""Tests for `scg monitor`'s CLI entrypoint (STORY-701) — specifically
the plain-language fallback when the optional `monitor` extra isn't
installed, since `textual` must never be a hard dependency of the base
package (docs/ARCHITECTURE.md sec 11.1)."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from scalene import monitor


class TestMonitorMain(unittest.TestCase):
    def test_missing_textual_extra_prints_plain_language_install_hint(self):
        # Setting a sys.modules entry to None deterministically forces the
        # next `import`/`from ... import` of it to raise ImportError,
        # regardless of whether it's already cached from another test.
        with patch.dict(sys.modules, {"scalene.monitor_app": None}):
            with patch("sys.stderr") as mock_stderr:
                exit_code = monitor.main([])

        self.assertEqual(exit_code, 1)
        printed = "".join(call.args[0] for call in mock_stderr.write.call_args_list)
        self.assertIn("pip install scalene-guard[monitor]", printed)


class TestMonitorMainPathFlags(unittest.TestCase):
    """2026-07-30 (direct user report: "monitor decisions not persisting
    across sessions"): `scg monitor` had no way to pin its 4 state paths
    explicitly -- every one defaulted to cwd-relative, so launching it from
    a different directory than intended silently pointed it at a different
    .scalene/ and scalene_policy.yaml, indistinguishable from "it forgot".
    These tests confirm the new flags (matching `scg onboard`'s existing
    --policy-path/--cache-path names) actually reach MonitorApp's
    constructor, not just that argparse itself accepts them."""

    def test_default_paths_match_the_hook_adapters_own_defaults(self):
        with patch("scalene.monitor_app.MonitorApp") as mock_app_cls:
            monitor.main([])
        _, kwargs = mock_app_cls.call_args
        self.assertEqual(kwargs["policy_path"], Path("scalene_policy.yaml"))
        self.assertEqual(kwargs["cache_path"], Path(".scalene") / "scan_cache.json")
        self.assertEqual(kwargs["state_dir"], Path(".scalene") / "state")
        self.assertEqual(kwargs["audit_log_path"], Path(".scalene") / "audit.log")
        mock_app_cls.return_value.run.assert_called_once()

    def test_explicit_flags_are_passed_through_to_monitor_app(self):
        with patch("scalene.monitor_app.MonitorApp") as mock_app_cls:
            monitor.main(
                [
                    "--policy-path", "/tmp/x/policy.yaml",
                    "--cache-path", "/tmp/x/cache.json",
                    "--state-dir", "/tmp/x/state",
                    "--audit-log-path", "/tmp/x/audit.log",
                ]
            )
        _, kwargs = mock_app_cls.call_args
        self.assertEqual(kwargs["policy_path"], Path("/tmp/x/policy.yaml"))
        self.assertEqual(kwargs["cache_path"], Path("/tmp/x/cache.json"))
        self.assertEqual(kwargs["state_dir"], Path("/tmp/x/state"))
        self.assertEqual(kwargs["audit_log_path"], Path("/tmp/x/audit.log"))


if __name__ == "__main__":
    unittest.main()
