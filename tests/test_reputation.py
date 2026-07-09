"""Tests for LocalHeuristicChecker (STORY-501 decision #4, no external API)."""

import unittest

from scalene.reputation import LocalHeuristicChecker, ReputationResult


class TestLocalHeuristicChecker(unittest.TestCase):
    def setUp(self):
        self.checker = LocalHeuristicChecker()

    def test_ordinary_domain_is_trusted(self):
        result = self.checker.check("internal.example.com")
        self.assertIsInstance(result, ReputationResult)
        self.assertTrue(result.is_trusted)

    def test_ipv4_literal_is_untrusted(self):
        result = self.checker.check("203.0.113.42")
        self.assertFalse(result.is_trusted)
        self.assertIn("IP-literal", result.reason)

    def test_ipv6_literal_is_untrusted(self):
        result = self.checker.check("2001:db8::1")
        self.assertFalse(result.is_trusted)
        self.assertIn("IP-literal", result.reason)

    def test_punycode_homograph_is_untrusted(self):
        result = self.checker.check("xn--pple-43d.com")
        self.assertFalse(result.is_trusted)
        self.assertIn("punycode", result.reason.lower())

    def test_suspiciously_long_domain_label_is_untrusted(self):
        result = self.checker.check("a" * 40 + ".com")
        self.assertFalse(result.is_trusted)
        self.assertIn("suspicious", result.reason.lower())

    def test_never_raises_on_malformed_target(self):
        result = self.checker.check("")
        self.assertIsInstance(result, ReputationResult)


if __name__ == "__main__":
    unittest.main()
