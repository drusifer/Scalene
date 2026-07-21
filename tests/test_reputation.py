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

    def test_punycode_only_trigger_also_scores_two_thirds(self):
        # Trin's UAT (Sprint 8/E14 Phase 1): the score assertion for a
        # single trigger was only ever checked against the IP-literal case
        # -- confirming it independently for the other 2 heuristics is real
        # coverage, not a duplicate of an existing test.
        result = self.checker.check("xn--pple-43d.com")
        self.assertAlmostEqual(result.score, 2 / 3)

    def test_suspiciously_long_domain_label_is_untrusted(self):
        result = self.checker.check("a" * 40 + ".com")
        self.assertFalse(result.is_trusted)
        self.assertIn("suspicious", result.reason.lower())

    def test_suspicious_length_only_trigger_also_scores_two_thirds(self):
        result = self.checker.check("a" * 40 + ".com")
        self.assertAlmostEqual(result.score, 2 / 3)

    def test_never_raises_on_malformed_target(self):
        result = self.checker.check("")
        self.assertIsInstance(result, ReputationResult)

    def test_clean_target_has_a_perfect_score(self):
        # docs/ARCHITECTURE.md sec17.6: reputation score is 1.0 - (triggered
        # heuristics / 3), so a clean target scores 1.0 exactly.
        result = self.checker.check("internal.example.com")
        self.assertEqual(result.score, 1.0)

    def test_single_triggered_heuristic_scores_two_thirds(self):
        result = self.checker.check("203.0.113.42")
        self.assertAlmostEqual(result.score, 2 / 3)

    def test_two_triggered_heuristics_score_one_third_and_both_reasons_present(self):
        # sec17.6: check() must evaluate all 3 heuristics, not short-circuit
        # on the first match -- a target that's both punycode-prefixed AND
        # has a suspiciously long label must reflect both in the score and
        # in the combined reason, not just whichever heuristic ran first.
        target = "xn--" + "a" * 30 + ".com"
        result = self.checker.check(target)
        self.assertFalse(result.is_trusted)
        self.assertAlmostEqual(result.score, 1 / 3)
        self.assertIn("punycode", result.reason.lower())
        self.assertIn("suspicious", result.reason.lower())

    def test_is_trusted_still_false_if_any_single_heuristic_trips(self):
        # Evaluating all 3 heuristics (for the score) must not change
        # is_trusted's existing any-trip-fails meaning.
        result = self.checker.check("xn--pple-43d.com")
        self.assertFalse(result.is_trusted)


if __name__ == "__main__":
    unittest.main()
