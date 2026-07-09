"""Tests for MaskingEngine (STORY-401)."""

import unittest

from scalene.masking import MaskingEngine
from scalene.policy_config import MatchResult
from scalene.taint_state import TaintState


class TestMaskingEngineDecide(unittest.TestCase):
    def test_trigger_condition_all_three_true(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        self.assertTrue(engine.decide(taint, match).should_mask)

    def test_no_mask_when_target_trusted(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=True)
        self.assertFalse(engine.decide(taint, match).should_mask)

    def test_no_mask_when_session_not_sensitive(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=False, has_untrusted_data=True)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        self.assertFalse(engine.decide(taint, match).should_mask)

    def test_no_mask_when_session_not_untrusted(self):
        engine = MaskingEngine()
        taint = TaintState(session_id="s1", has_sensitive_data=True, has_untrusted_data=False)
        match = MatchResult(is_sensitive=True, is_trusted=False)
        self.assertFalse(engine.decide(taint, match).should_mask)


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
