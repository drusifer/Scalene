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


class TestTaintStatePendingTrust(unittest.TestCase):
    """docs/ARCHITECTURE.md sec15.2 (direct user request, 2026-08-07):
    tracks resources optimistically trusted on a matching rule before
    their background scan finished, so the next call in the same session
    can reconcile against the real, since-completed verdict."""

    def test_add_pending_trust_tracks_the_key(self):
        state = TaintState(session_id="s1")
        state.add_pending_trust("secrets:/tmp/new.txt")
        self.assertEqual(state.pending_trust, ["secrets:/tmp/new.txt"])

    def test_add_pending_trust_does_not_duplicate(self):
        state = TaintState(session_id="s1")
        state.add_pending_trust("secrets:/tmp/new.txt")
        state.add_pending_trust("secrets:/tmp/new.txt")
        self.assertEqual(state.pending_trust, ["secrets:/tmp/new.txt"])

    def test_resolve_pending_trust_removes_the_key(self):
        state = TaintState(session_id="s1")
        state.add_pending_trust("secrets:/tmp/new.txt")
        state.resolve_pending_trust("secrets:/tmp/new.txt")
        self.assertEqual(state.pending_trust, [])

    def test_resolve_pending_trust_on_an_untracked_key_is_a_safe_no_op(self):
        state = TaintState(session_id="s1")
        state.resolve_pending_trust("secrets:/tmp/never-tracked.txt")
        self.assertEqual(state.pending_trust, [])

    def test_reset_clears_pending_trust_too(self):
        state = TaintState(session_id="s1")
        state.add_pending_trust("secrets:/tmp/new.txt")
        state.reset()
        self.assertEqual(state.pending_trust, [])

    def test_pending_trust_round_trips_through_save_and_load(self):
        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            state.add_pending_trust("secrets:/tmp/new.txt")
            state.add_pending_trust("reputation:https://pending.example.com/x")
            state.save()

            reloaded = TaintState.load("s1", state_dir=state_dir)
            self.assertEqual(
                reloaded.pending_trust, ["secrets:/tmp/new.txt", "reputation:https://pending.example.com/x"]
            )

    def test_load_missing_session_has_empty_pending_trust(self):
        with TemporaryDirectory() as tmp:
            state = TaintState.load("nonexistent", state_dir=Path(tmp))
            self.assertEqual(state.pending_trust, [])


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

    def test_a_held_lock_fails_fast_instead_of_hanging_forever(self):
        # Direct user request (2026-08-08): `FileLock`'s own default
        # (timeout=-1) blocks forever on contention -- a stuck/stale lock
        # on this session's state file would hang the hook indefinitely.
        # Proves the real bound against the exact lock path `save()` uses.
        import time

        from filelock import FileLock

        with TemporaryDirectory() as tmp:
            state_dir = Path(tmp)
            state = TaintState(session_id="s1", state_dir=state_dir)
            lock_path = str(state._path()) + ".lock"
            with FileLock(lock_path):  # held by this test process
                t0 = time.monotonic()
                with self.assertRaises(TimeoutError):
                    state.save()
                elapsed = time.monotonic() - t0
            self.assertLess(elapsed, 10, "lock contention should fail fast, not hang")

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
