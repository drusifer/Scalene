"""Tests for resource verification (STORY-1002, STORY-1003) -- replaces
PolicyConfig.evaluate()'s PolicyRule/allowlist matching (docs/ARCHITECTURE.md
sec13.1, full replacement). Returns the same MatchResult shape
pre_tool_use/post_tool_use already consume (sec13.1.1), so this module is
the only thing that changes -- MaskingEngine.decide() is untouched.
"""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.policy_config import MatchResult, PolicyConfig
from scalene.resource_verifier import evaluate
from scalene.scan_cache import ScanCache
from scalene.scanner import Resource, ScanResult


class TestNoResourcesIdentified(unittest.TestCase):
    """A call with nothing file- or URL-shaped in its args -- must fall back
    to the config defaults exactly like today's PolicyConfig.evaluate() did
    when no allowlist rule matched."""

    def test_falls_back_to_defaults_when_nothing_identified(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)
            result = evaluate("Bash", {"command": "echo hello"}, config, cache)
            self.assertIsInstance(result, MatchResult)
            self.assertTrue(result.is_sensitive)
            self.assertFalse(result.is_trusted)
            self.assertFalse(result.fail_safe_triggered)

    def test_respects_non_default_config_when_nothing_identified(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(sensitive_by_default=False, untrusted_by_default=False)
            result = evaluate("Bash", {"command": "echo hello"}, config, cache)
            self.assertFalse(result.is_sensitive)
            self.assertTrue(result.is_trusted)


class TestCachedResourceResolution(unittest.TestCase):
    def test_known_public_file_is_not_sensitive(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("ordinary text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(target), scanner_name="secrets"), ScanResult(label="public"))

            config = PolicyConfig(sensitive_by_default=True, untrusted_by_default=True)
            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertFalse(result.is_sensitive)
            self.assertFalse(result.fail_safe_triggered)

    def test_known_sensitive_file_is_sensitive(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "secret.env"
            target.write_text("AWS_KEY=fake")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="file", identity=str(target), scanner_name="secrets"),
                ScanResult(label="sensitive", reason="Possible AWS Access Key"),
            )

            config = PolicyConfig(sensitive_by_default=False)
            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertTrue(result.is_sensitive)

    def test_known_trusted_host_is_trusted(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )

            config = PolicyConfig(untrusted_by_default=True)
            result = evaluate("WebFetch", {"url": "https://internal.example.com/api"}, config, cache)
            self.assertTrue(result.is_trusted)
            self.assertFalse(result.fail_safe_triggered)

    def test_known_untrusted_host_is_not_trusted(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(
                Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="IP-literal targets are untrusted by default"),
            )

            config = PolicyConfig(untrusted_by_default=False)
            result = evaluate("WebFetch", {"url": "https://203.0.113.42/api"}, config, cache)
            self.assertFalse(result.is_trusted)


class TestFailSafeTriggered(unittest.TestCase):
    """sec13.1.1: fail_safe_triggered now means "at least one identified
    resource had no cache entry and fell back to defaults" -- not the old
    JSONPath-evaluation-failure meaning."""

    def test_never_before_seen_file_triggers_fail_safe_and_uses_default(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "never_seen.md"
            target.write_text("text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(sensitive_by_default=True)

            result = evaluate("Read", {"file_path": str(target)}, config, cache)
            self.assertTrue(result.is_sensitive)  # sensitive_by_default applied
            self.assertTrue(result.fail_safe_triggered)

    def test_never_before_seen_url_triggers_fail_safe_and_uses_default(self):
        with TemporaryDirectory() as tmp:
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            config = PolicyConfig(untrusted_by_default=True)

            result = evaluate("WebFetch", {"url": "https://never-seen.example.com/x"}, config, cache)
            self.assertFalse(result.is_trusted)  # not untrusted_by_default applied
            self.assertTrue(result.fail_safe_triggered)

    def test_fail_safe_not_triggered_when_everything_identified_is_cached(self):
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "clean.md"
            target.write_text("text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(target), scanner_name="secrets"), ScanResult(label="public"))
            cache.put(
                Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
                ScanResult(label="trusted"),
            )
            config = PolicyConfig()

            result = evaluate(
                "Bash",
                {"command": f"cat {target} && curl https://internal.example.com/x"},
                config,
                cache,
            )
            self.assertFalse(result.fail_safe_triggered)

    def test_first_sighting_spawns_exactly_one_background_scan_per_resource(self):
        # Confirms this module actually calls refresh_if_needed (side effect:
        # a background scan gets triggered), not just is_fresh-style checks.
        with TemporaryDirectory() as tmp:
            target = Path(tmp) / "never_seen.md"
            target.write_text("text")
            cache_path = Path(tmp) / "scan_cache.json"
            cache = ScanCache(cache_path)
            config = PolicyConfig()

            from unittest.mock import patch

            with patch("scalene.scan_cache.subprocess.Popen") as mock_popen:
                evaluate("Read", {"file_path": str(target)}, config, cache)

            mock_popen.assert_called_once()


class TestMultipleResourcesAnySemantics(unittest.TestCase):
    """Mirrors the old PolicyRule model's ANY-match semantics for parity
    (sec13.1.1: same MatchResult shape, same downstream handling) -- a call
    touching multiple resources of one kind is sensitive/untrusted unless
    ALL of them individually resolve to a clean/trusted label."""

    def test_one_sensitive_file_among_several_makes_the_call_sensitive(self):
        with TemporaryDirectory() as tmp:
            clean = Path(tmp) / "clean.md"
            clean.write_text("text")
            secret = Path(tmp) / "secret.env"
            secret.write_text("AWS_KEY=fake")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(clean), scanner_name="secrets"), ScanResult(label="public"))
            cache.put(
                Resource(kind="file", identity=str(secret), scanner_name="secrets"),
                ScanResult(label="sensitive", reason="AWS key"),
            )
            config = PolicyConfig(sensitive_by_default=False)

            result = evaluate("Bash", {"command": f"cat {clean} {secret}"}, config, cache)
            self.assertTrue(result.is_sensitive)

    def test_all_public_files_makes_the_call_not_sensitive(self):
        with TemporaryDirectory() as tmp:
            a = Path(tmp) / "a.md"
            a.write_text("text")
            b = Path(tmp) / "b.md"
            b.write_text("text")
            cache = ScanCache(Path(tmp) / "scan_cache.json")
            cache.put(Resource(kind="file", identity=str(a), scanner_name="secrets"), ScanResult(label="public"))
            cache.put(Resource(kind="file", identity=str(b), scanner_name="secrets"), ScanResult(label="public"))
            config = PolicyConfig(sensitive_by_default=True)

            result = evaluate("Bash", {"command": f"cat {a} {b}"}, config, cache)
            self.assertFalse(result.is_sensitive)


if __name__ == "__main__":
    unittest.main()
