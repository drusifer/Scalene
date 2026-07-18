"""Tests for MaskingEngine (STORY-401, STORY-1104).

2026-07-14: masking is content-gated (detect-secrets via secrets_scan.py),
not purely provenance-based — a payload doesn't get masked/blocked just
because it looks generically risky (e.g. `ls -la`); it must actually scan
as a real secret.

2026-07-17 (docs/ARCHITECTURE.md sec14.4, STORY-1104): content-scanning is
now unconditional — the taint/provenance_risk gate is removed entirely.
Every non-null payload value is scanned regardless of session taint or
destination trust; `match.mode` (resolved per-call by resource_verifier,
sec14.1) decides mask/block/allow. The sole remaining way to skip scanning
is an explicit `mode: allow` rule (sec14.4 amendment) — never session state.
"""

import unittest
from unittest import mock

from scalene.masking import MaskingEngine
from scalene.policy_config import MatchResult

REAL_SECRET = "AKIAIOSFODNN7EXAMPLE"  # AWS access-key-ID shape (detect-secrets recognizes this)
NOT_A_SECRET = "ls -la"


class TestMaskingEngineDecide(unittest.TestCase):
    def test_masks_a_real_secret_by_default(self):
        engine = MaskingEngine()
        match = MatchResult(is_sensitive=True, is_trusted=False, mode="mask")
        decision = engine.decide(match, REAL_SECRET)
        self.assertEqual(decision.action, "mask")
        self.assertTrue(decision.findings)

    def test_blocks_instead_of_masks_when_mode_is_block(self):
        engine = MaskingEngine()
        match = MatchResult(is_sensitive=True, is_trusted=False, mode="block")
        decision = engine.decide(match, REAL_SECRET)
        self.assertEqual(decision.action, "block")
        self.assertTrue(decision.findings)

    def test_allows_when_value_has_no_real_secret(self):
        """The core fix (user-reported, 2026-07-14): an ordinary command
        must not be masked/blocked just because it looks generically risky."""
        engine = MaskingEngine()
        match = MatchResult(is_sensitive=True, is_trusted=False, mode="mask")
        decision = engine.decide(match, NOT_A_SECRET)
        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.findings, ())

    def test_masks_a_real_secret_even_when_destination_is_trusted(self):
        # STORY-1104: trust no longer exempts a call from scanning --
        # this is the entire point of "unconditional baseline."
        engine = MaskingEngine()
        match = MatchResult(is_sensitive=True, is_trusted=True, mode="mask")
        decision = engine.decide(match, REAL_SECRET)
        self.assertEqual(decision.action, "mask")

    def test_allows_when_value_is_none(self):
        engine = MaskingEngine()
        match = MatchResult(is_sensitive=True, is_trusted=False, mode="mask")
        decision = engine.decide(match, None)
        self.assertEqual(decision.action, "allow")

    def test_mode_allow_skips_scanning_entirely_even_for_a_real_secret(self):
        # sec14.4 amendment: the sole remaining, deliberate exception --
        # reachable only via an explicit rule (resource_verifier's job to
        # resolve), never automatic.
        engine = MaskingEngine()
        match = MatchResult(is_sensitive=True, is_trusted=False, mode="allow")
        with mock.patch("scalene.masking.scan_text_for_secrets") as mock_scan:
            decision = engine.decide(match, REAL_SECRET)
        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.findings, ())
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
