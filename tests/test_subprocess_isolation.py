"""Tests for scanner subprocess isolation (STORY-601)."""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from scalene.subprocess_isolation import run_scanner


class TestRunScannerSecrets(unittest.TestCase):
    def test_clean_file_passes(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("just some ordinary docs")
            result = run_scanner("secrets", str(target))
            self.assertTrue(result["ok"])

    def test_file_with_secret_fails_with_clear_reason(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "leaky.env"
            # Fake key built via concatenation, not a contiguous literal a
            # secret scanner would flag in this source file.
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            result = run_scanner("secrets", str(target))
            self.assertFalse(result["ok"])
            self.assertTrue(result["reason"])


class TestRunScannerReputation(unittest.TestCase):
    def test_trusted_domain_passes(self):
        result = run_scanner("reputation", "internal.example.com")
        self.assertTrue(result["ok"])

    def test_ip_literal_target_fails(self):
        result = run_scanner("reputation", "203.0.113.42")
        self.assertFalse(result["ok"])
        self.assertTrue(result["reason"])


class TestRunScannerIsolation(unittest.TestCase):
    def test_subprocess_env_includes_scalene_bypass(self):
        # STORY-601 AC2: scanner subprocess must carry SCALENE_BYPASS=1 so hooks
        # don't recursively re-trigger on the scanner's own actions.
        with patch("scalene.subprocess_isolation.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"ok": true, "reason": ""}'
            run_scanner("reputation", "example.com")
            _, kwargs = mock_run.call_args
            self.assertEqual(kwargs["env"]["SCALENE_BYPASS"], "1")

    def test_subprocess_runs_as_separate_process(self):
        # STORY-601 AC1: real subprocess.run invocation, not an in-process call.
        with patch("scalene.subprocess_isolation.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = '{"ok": true, "reason": ""}'
            run_scanner("reputation", "example.com")
            args, _ = mock_run.call_args
            self.assertIn("scalene.scan_worker", args[0])

    def test_unknown_scan_type_fails_safe(self):
        result = run_scanner("bogus_scan_type", "whatever")
        self.assertFalse(result["ok"])

    def test_unknown_scan_type_is_marked_as_machinery_error(self):
        # STORY-1004: distinguishes "the scan couldn't run" from an ordinary
        # finding, so Scanner.scan() knows to raise instead of returning a
        # ScanResult.
        result = run_scanner("bogus_scan_type", "whatever")
        self.assertTrue(result["machinery_error"])

    def test_never_raises_when_subprocess_itself_errors(self):
        with patch("scalene.subprocess_isolation.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("no such executable")
            result = run_scanner("reputation", "example.com")
            self.assertFalse(result["ok"])
            self.assertTrue(result["reason"])

    def test_subprocess_error_is_marked_as_machinery_error(self):
        with patch("scalene.subprocess_isolation.subprocess.run") as mock_run:
            mock_run.side_effect = OSError("no such executable")
            result = run_scanner("reputation", "example.com")
            self.assertTrue(result["machinery_error"])

    def test_malformed_subprocess_output_is_marked_as_machinery_error(self):
        with patch("scalene.subprocess_isolation.subprocess.run") as mock_run:
            mock_run.return_value.returncode = 0
            mock_run.return_value.stdout = "not valid json"
            result = run_scanner("reputation", "example.com")
            self.assertFalse(result["ok"])
            self.assertTrue(result["machinery_error"])

    def test_ordinary_finding_is_not_marked_as_machinery_error(self):
        result = run_scanner("reputation", "203.0.113.42")
        self.assertFalse(result["ok"])
        self.assertFalse(result.get("machinery_error", False))


if __name__ == "__main__":
    unittest.main()
