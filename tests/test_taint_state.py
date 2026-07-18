"""Tests for TaintState (STORY-101; reworked 2026-07-17 per
docs/ARCHITECTURE.md sec15 -- trust/sensitivity tags replace the old
has_sensitive_data/has_untrusted_data booleans)."""

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from scalene.taint_state import TaintState


class TestTaintStateDefaults(unittest.TestCase):
    def test_starts_clean(self):
        state = TaintState(session_id="s1")
        self.assertEqual(state.trust, "high")
        self.assertEqual(state.sensitivity, "public")
        self.assertTrue(state.is_clean)

    def test_invalid_trust_raises(self):
        with self.assertRaises(ValueError):
            TaintState(session_id="s1", trust="nope")

    def test_invalid_sensitivity_raises(self):
        with self.assertRaises(ValueError):
            TaintState(session_id="s1", sensitivity="nope")


class TestTaintStateEscalation(unittest.TestCase):
    def test_escalate_trust_moves_toward_more_restrictive(self):
        state = TaintState(session_id="s1")
        state.escalate_trust("low")
        self.assertEqual(state.trust, "low")
        self.assertFalse(state.is_clean)

    def test_escalate_trust_never_relaxes(self):
        state = TaintState(session_id="s1", trust="low")
        state.escalate_trust("high")
        self.assertEqual(state.trust, "low")

    def test_escalate_trust_to_med_from_high(self):
        state = TaintState(session_id="s1")
        state.escalate_trust("med")
        self.assertEqual(state.trust, "med")

    def test_escalate_trust_low_wins_over_med(self):
        state = TaintState(session_id="s1")
        state.escalate_trust("med")
        state.escalate_trust("low")
        self.assertEqual(state.trust, "low")
        state.escalate_trust("med")  # attempting to relax back up must not work
        self.assertEqual(state.trust, "low")

    def test_escalate_sensitivity_moves_toward_more_restrictive(self):
        state = TaintState(session_id="s1")
        state.escalate_sensitivity("internal")
        self.assertEqual(state.sensitivity, "internal")
        state.escalate_sensitivity("restricted")
        self.assertEqual(state.sensitivity, "restricted")

    def test_escalate_sensitivity_never_relaxes(self):
        state = TaintState(session_id="s1", sensitivity="restricted")
        state.escalate_sensitivity("public")
        self.assertEqual(state.sensitivity, "restricted")
        state.escalate_sensitivity("internal")
        self.assertEqual(state.sensitivity, "restricted")

    def test_only_reset_reverts_escalated_tags(self):
        state = TaintState(session_id="s1")
        state.escalate_trust("low")
        state.escalate_sensitivity("restricted")
        state.reset()
        self.assertEqual(state.trust, "high")
        self.assertEqual(state.sensitivity, "public")
        self.assertTrue(state.is_clean)


class TestTaintStatePersistence(unittest.TestCase):
    def test_load_missing_session_returns_clean_defaults(self):
        with TemporaryDirectory() as tmp:
            state = TaintState.load("nonexistent", state_dir=Path(tmp))
            self.assertTrue(state.is_clean)

    def test_save_then_load_round_trips_tags(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.escalate_trust("low")
            state.escalate_sensitivity("internal")
            state.save()

            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertEqual(reloaded.trust, "low")
            self.assertEqual(reloaded.sensitivity, "internal")

    def test_queryable_without_replaying_prior_calls(self):
        # Loading state must not require replaying/re-scanning any tool-call
        # history — it's a flat O(1) file read of the persisted tags.
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.escalate_trust("low")
            state.escalate_sensitivity("restricted")
            state.save()

            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertEqual(reloaded.trust, "low")
            self.assertEqual(reloaded.sensitivity, "restricted")

    def test_reset_clears_persisted_state_file(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.escalate_trust("low")
            state.save()
            self.assertTrue((state_dir / "s1.json").exists())

            state.reset()
            self.assertFalse((state_dir / "s1.json").exists())


if __name__ == "__main__":
    unittest.main()
