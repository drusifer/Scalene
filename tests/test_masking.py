"""Tests for MaskingEngine (STORY-401).

2026-07-14: masking is now content-gated (detect-secrets via
secrets_scan.py), not purely provenance-based — a session can be
tainted-sensitive + untrusted and still allow a call through if the specific
payload doesn't actually scan as a real secret (e.g. `ls -la`).
"""

import unittest
from unittest import mock

from scalene.masking import MaskingEngine
from scalene.policy_config import MatchResult
from scalene.taint_state import TaintState

REAL_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)
NOT_A_SECRET = "ls -la"


class TestMaskingEngineDecide(unittest.TestCase):
    def test_masks_when_provenance_risky_and_value_is_a_real_secret(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        decision = engine.decide(taint, match, REAL_SECRET, mode="mask")
        self.assertEqual(decision.action, "mask")
        self.assertTrue(decision.findings)

    def test_blocks_instead_of_masks_when_mode_is_block(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        decision = engine.decide(taint, match, REAL_SECRET, mode="block")
        self.assertEqual(decision.action, "block")
        self.assertTrue(decision.findings)

    def test_allows_when_provenance_risky_but_value_has_no_real_secret(self):
        """The core fix (user-reported): an ordinary command must not be
        masked/blocked just because the session is generically tainted."""
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        decision = engine.decide(taint, match, NOT_A_SECRET, mode="mask")
        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.findings, ())

    def test_allows_when_target_trusted_even_with_a_real_secret(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=True)
        decision = engine.decide(taint, match, REAL_SECRET, mode="mask")
        self.assertEqual(decision.action, "allow")

    def test_allows_when_session_not_sensitive(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=False, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        decision = engine.decide(taint, match, REAL_SECRET, mode="mask")
        self.assertEqual(decision.action, "allow")

    def test_allows_when_session_not_untrusted(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=False)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        decision = engine.decide(taint, match, REAL_SECRET, mode="mask")
        self.assertEqual(decision.action, "allow")

    def test_allows_when_value_is_none(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        decision = engine.decide(taint, match, None, mode="mask")
        self.assertEqual(decision.action, "allow")

    def test_does_not_scan_content_when_provenance_is_already_safe(self):
        """Perf guard: the content scan must not run at all when the
        provenance gate already says allow (untainted/trusted sessions pay
        zero scanning cost)."""
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=False, has_untrusted_data=False)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        with mock.patch("scalene.masking.scan_text_for_secrets") as mock_scan:
            engine.decide(taint, match, REAL_SECRET, mode="mask")
        mock_scan.assert_not_called()


class TestMaskingEngineApplyMask(unittest.TestCase):
    def test_replaces_payload_field_with_literal(self):
        engine = MaskingEngine()
        result = engine.apply_mask({"file_path": "x.txt", "content": "secret"}, "content")
        self.assertEqual(result["content"], MaskingEngine.MASK_LITERAL)

    def test_preserves_non_payload_fields(self):
        engine = MaskingEngine()
        result = engine.apply_mask({"file_path": "x.txt", "content": "secret"}, "content")
        self.assertEqual(result["file_path"], "x.txt")

    def test_is_structural_not_partial_redaction(self):
        engine = MaskingEngine()
        result = engine.apply_mask({"content": "secret key=abc123 more text"}, "content")
        self.assertEqual(result["content"], MaskingEngine.MASK_LITERAL)

    def test_does_not_mutate_input_dict(self):
        engine = MaskingEngine()
        original = {"file_path": "x.txt", "content": "secret"}
        engine.apply_mask(original, "content")
        self.assertEqual(original["content"], "secret")

    def test_never_raises_on_missing_payload_field(self):
        engine = MaskingEngine()
        result = engine.apply_mask({"file_path": "x.txt"}, "content")
        self.assertEqual(result, {"file_path": "x.txt"})

    def test_never_raises_on_none_payload_field(self):
        engine = MaskingEngine()
        result = engine.apply_mask({"file_path": "x.txt"}, None)
        self.assertEqual(result, {"file_path": "x.txt"})

    def test_never_raises_on_non_dict_args(self):
        engine = MaskingEngine()
        result = engine.apply_mask("not-a-dict", "content")
        self.assertEqual(result, "not-a-dict")


if __name__ == "__main__":
    unittest.main()
