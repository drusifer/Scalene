"""Tests for TaintState (STORY-101)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.taint_state import TaintState


class TestTaintStateDefaults(unittest.TestCase):
    def test_flags_default_false(self):
        state = TaintState(session_id="s1")
        self.assertFalse(state.has_sensitive_data)
        self.assertFalse(state.has_untrusted_data)


class TestTaintStateSticky(unittest.TestCase):
    def test_mark_sensitive_is_sticky(self):
        state = TaintState(session_id="s1")
        state.mark_sensitive()
        self.assertTrue(state.has_sensitive_data)
        state.mark_sensitive()
        self.assertTrue(state.has_sensitive_data)

    def test_mark_untrusted_is_sticky(self):
        state = TaintState(session_id="s1")
        state.mark_untrusted()
        self.assertTrue(state.has_untrusted_data)

    def test_no_public_api_flips_true_back_to_false_except_reset(self):
        state = TaintState(session_id="s1")
        state.mark_sensitive()
        state.mark_untrusted()
        # only reset() may revert flags
        state.reset()
        self.assertFalse(state.has_sensitive_data)
        self.assertFalse(state.has_untrusted_data)


class TestTaintStatePersistence(unittest.TestCase):
    def test_load_missing_session_returns_defaults(self):
        with TemporaryDirectory() as tmp:
            state = TaintState.load("nonexistent", state_dir=Path(tmp))
            self.assertFalse(state.has_sensitive_data)
            self.assertFalse(state.has_untrusted_data)

    def test_save_then_load_round_trips_sticky_flags(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.mark_sensitive()
            state.save()

            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertTrue(reloaded.has_sensitive_data)
            self.assertFalse(reloaded.has_untrusted_data)

    def test_queryable_without_rescanning_prior_calls(self):
        # Loading state must not require replaying/re-scanning any tool-call
        # history — it's a flat O(1) file read of the persisted flags.
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.mark_sensitive()
            state.mark_untrusted()
            state.save()

            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertTrue(reloaded.has_sensitive_data)
            self.assertTrue(reloaded.has_untrusted_data)

    def test_reset_clears_persisted_state_file(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.mark_sensitive()
            state.save()
            self.assertTrue((state_dir / "s1.json").exists())

            state.reset()
            self.assertFalse((state_dir / "s1.json").exists())


if __name__ == "__main__":
    unittest.main()
