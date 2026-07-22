"""Tests for LocalHeuristicChecker (STORY-501 decision #4, no external API)."""

import json
import os
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from scalene.reputation import (
    LocalHeuristicChecker,
    ReputationCheckUnavailable,
    ReputationResult,
    URLHausChecker,
    _query_urlhaus,
    composite_check,
)

_AUTH_KEY_ENV_VAR = "SCALENE_URLHAUS_AUTH_KEY"


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


class TestQueryUrlhausAuthKey(unittest.TestCase):
    """Tank's Phase 3 finding (2026-07-21): the real endpoint requires an
    Auth-Key, contrary to sec18.3's original (docs-based) assumption."""

    def test_missing_auth_key_raises_unavailable_without_sending_a_request(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(_AUTH_KEY_ENV_VAR, None)
            with patch("urllib.request.urlopen") as mock_urlopen:
                with self.assertRaises(ReputationCheckUnavailable) as ctx:
                    _query_urlhaus("example.com", timeout=3.0)
                mock_urlopen.assert_not_called()
        self.assertIn(_AUTH_KEY_ENV_VAR, str(ctx.exception))

    def test_present_auth_key_is_sent_as_a_request_header(self):
        mock_response = MagicMock()
        mock_response.read.return_value = json.dumps({"query_status": "no_results"}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        with patch.dict(os.environ, {_AUTH_KEY_ENV_VAR: "fake-test-key"}):
            with patch("urllib.request.urlopen", return_value=mock_response) as mock_urlopen:
                result = _query_urlhaus("example.com", timeout=3.0)
        self.assertEqual(result, {"query_status": "no_results"})
        sent_request = mock_urlopen.call_args[0][0]
        self.assertEqual(sent_request.get_header("Auth-key"), "fake-test-key")

    def test_urlhaus_checker_check_surfaces_the_missing_key_as_unavailable(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop(_AUTH_KEY_ENV_VAR, None)
            with self.assertRaises(ReputationCheckUnavailable):
                URLHausChecker().check("example.com")


class TestURLHausChecker(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.3 (STORY-1503). Mocks the isolated HTTP
    call (_query_urlhaus) rather than hitting a live network -- this
    project has no live-network tests anywhere else either."""

    def test_no_results_is_trusted(self):
        with patch("scalene.reputation._query_urlhaus", return_value={"query_status": "no_results"}):
            result = URLHausChecker().check("clean-host.example.com")
            self.assertTrue(result.is_trusted)
            self.assertEqual(result.score, 1.0)

    def test_listed_with_an_online_url_is_untrusted(self):
        payload = {"query_status": "ok", "urls": [{"url_status": "online"}]}
        with patch("scalene.reputation._query_urlhaus", return_value=payload):
            result = URLHausChecker().check("bad-host.example.com")
            self.assertFalse(result.is_trusted)
            self.assertEqual(result.score, 0.0)
            self.assertTrue(result.reason)

    def test_listed_but_every_url_offline_is_trusted(self):
        # A host that once hosted malware but has since been cleaned up --
        # not the same as actively malicious right now.
        payload = {"query_status": "ok", "urls": [{"url_status": "offline"}]}
        with patch("scalene.reputation._query_urlhaus", return_value=payload):
            result = URLHausChecker().check("formerly-bad.example.com")
            self.assertTrue(result.is_trusted)

    def test_network_error_raises_reputation_check_unavailable_not_a_finding(self):
        with patch(
            "scalene.reputation._query_urlhaus",
            side_effect=urllib.error.URLError("no route to host"),
        ):
            with self.assertRaises(ReputationCheckUnavailable):
                URLHausChecker().check("anything.example.com")

    def test_unexpected_query_status_raises_unavailable_not_treated_as_a_finding(self):
        with patch("scalene.reputation._query_urlhaus", return_value={"query_status": "invalid_host"}):
            with self.assertRaises(ReputationCheckUnavailable):
                URLHausChecker().check("not-a-real-hostname")


class TestCompositeCheck(unittest.TestCase):
    """docs/ARCHITECTURE.md sec18.3 (STORY-1503): always runs the local
    heuristics, combines with URLHausChecker when reachable, degrades
    visibly when it isn't."""

    def test_clean_locally_and_clean_externally_is_trusted_with_a_perfect_score(self):
        with patch("scalene.reputation._query_urlhaus", return_value={"query_status": "no_results"}):
            result = composite_check("internal.example.com")
            self.assertTrue(result.is_trusted)
            self.assertEqual(result.score, 1.0)

    def test_clean_locally_but_urlhaus_flags_it_is_untrusted(self):
        # any-bad-wins: a real external finding must override a clean local
        # heuristic result, not the other way around.
        payload = {"query_status": "ok", "urls": [{"url_status": "online"}]}
        with patch("scalene.reputation._query_urlhaus", return_value=payload):
            result = composite_check("internal-looking-but-actually-malicious.example.com")
            self.assertFalse(result.is_trusted)
            self.assertEqual(result.score, 0.0)

    def test_ip_literal_locally_flagged_stays_untrusted_even_if_urlhaus_is_clean(self):
        with patch("scalene.reputation._query_urlhaus", return_value={"query_status": "no_results"}):
            result = composite_check("203.0.113.42")
            self.assertFalse(result.is_trusted)
            self.assertAlmostEqual(result.score, 2 / 3)  # min(local=2/3, remote=1.0)

    def test_unreachable_source_degrades_to_local_only_with_a_visible_marker(self):
        # Smith's Gate 1 non-blocking note: this must NOT look identical to
        # a real external check having passed clean.
        with patch(
            "scalene.reputation._query_urlhaus",
            side_effect=urllib.error.URLError("timed out"),
        ):
            result = composite_check("internal.example.com")
            self.assertTrue(result.is_trusted)  # local heuristics alone are clean
            self.assertIn("external reputation check unavailable", result.reason)

    def test_degraded_result_still_reflects_a_real_local_finding_in_the_reason(self):
        with patch(
            "scalene.reputation._query_urlhaus",
            side_effect=urllib.error.URLError("timed out"),
        ):
            result = composite_check("203.0.113.42")
            self.assertFalse(result.is_trusted)
            self.assertIn("IP-literal", result.reason)
            self.assertIn("external reputation check unavailable", result.reason)


if __name__ == "__main__":
    unittest.main()
