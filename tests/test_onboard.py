"""Tests for the `scg onboard` CLI/library function (STORY-501).

2026-07-15 (Sprint 4 Phase 4, docs/ARCHITECTURE.md sec13.4): re-scoped to
pre-seed the resource cache instead of writing a scalene_policy.yaml rule.
`--tool`/`--jsonpath`/`--pattern`/`--description` are gone; `--target`'s
URI scheme still resolves the scanner exactly as before.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.onboard import OnboardError, onboard
from scalene.scan_cache import ScanCache


class TestOnboardFileTarget(unittest.TestCase):
    def test_clean_target_seeds_the_cache_as_public(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            cache_path = tmp_path / "scan_cache.json"

            result = onboard(f"file://{target}", cache_path=cache_path)
            self.assertEqual(result["label"], "public")

            entry = ScanCache(cache_path).get(result["resource"])
            self.assertIsNotNone(entry)
            self.assertEqual(entry.label, "public")

    def test_secrets_found_blocks_onboarding_with_clear_reason_and_no_cache_write(self):
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "leaky.env"
            # Fake key built via concatenation, not a contiguous literal a
            # secret scanner would flag in this source file.
            fake_key = "AKIA" + "ABCDEFGHIJKLMNOP"
            target.write_text(f"AWS_KEY={fake_key}")
            cache_path = tmp_path / "scan_cache.json"

            with self.assertRaises(OnboardError) as ctx:
                onboard(f"file://{target}", cache_path=cache_path)
            self.assertIn("secrets", str(ctx.exception).lower())
            self.assertFalse(cache_path.exists())

    def test_seeded_identity_matches_live_evaluation_normalization(self):
        # The cache key onboard() writes must match what FileScanner
        # produces during a real hook call for the same file, or
        # pre-seeding silently does nothing.
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            target = tmp_path / "clean.md"
            target.write_text("ordinary docs")
            cache_path = tmp_path / "scan_cache.json"

            from scalene.scanner import FileScanner

            result = onboard(f"file://{target}", cache_path=cache_path)
            live_resources = FileScanner().identify("Read", {"file_path": str(target)})
            self.assertEqual(len(live_resources), 1)
            self.assertEqual(result["resource"].identity, live_resources[0].identity)


class TestOnboardUrlTarget(unittest.TestCase):
    def test_trusted_domain_seeds_the_cache_as_trusted(self):
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            result = onboard("https://internal.example.com", cache_path=cache_path)
            self.assertEqual(result["label"], "trusted")

            entry = ScanCache(cache_path).get(result["resource"])
            self.assertEqual(entry.label, "trusted")

    def test_untrusted_ip_target_blocks_onboarding_with_no_cache_write(self):
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            with self.assertRaises(OnboardError) as ctx:
                onboard("https://203.0.113.42", cache_path=cache_path)
            self.assertTrue(str(ctx.exception))
            self.assertFalse(cache_path.exists())

    def test_unknown_scheme_blocks_with_no_cache_write(self):
        with TemporaryDirectory() as tmp:
            cache_path = Path(tmp) / "scan_cache.json"
            with self.assertRaises(OnboardError):
                onboard("ftp://x.md", cache_path=cache_path)
            self.assertFalse(cache_path.exists())


if __name__ == "__main__":
    unittest.main()
