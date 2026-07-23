"""Tests for the `scg monitor` data layer (STORY-701/702).

2026-07-17 (docs/ARCHITECTURE.md sec15): rewritten for trust/sensitivity
tags (replacing has_sensitive_data/has_untrusted_data) and BlockEvent
(replacing MaskEvent -- "mask" events no longer exist). STORY-702's
apply_onboard_command is removed with its now-gone editable-command
workflow (clearing a destination always takes two explicit steps now, not
one runnable command)."""

import json
import tempfile
import unittest
from pathlib import Path

from scalene.monitor_data import (
    AuditTail,
    ScannerActivity,
    ScanResultInfo,
    SessionInfo,
    ToolCallEvent,
    build_review_entry,
    discover_scan_results,
    discover_scanner_activity,
    discover_sessions,
    target_status,
)
from scalene.scan_cache import ScanCache
from scalene.scanner import SCANNERS, Resource, ScanResult


class TestDiscoverSessions(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_state_dir_returns_empty(self):
        missing = self.state_dir / "does-not-exist"
        self.assertEqual(discover_sessions(missing), [])

    def test_empty_state_dir_returns_empty(self):
        self.assertEqual(discover_sessions(self.state_dir), [])

    def test_reads_trust_and_sensitivity_from_state_file(self):
        (self.state_dir / "abc.json").write_text(json.dumps({"session_id": "abc", "trust": "low", "sensitivity": "internal"}))
        sessions = discover_sessions(self.state_dir)
        self.assertEqual(len(sessions), 1)
        self.assertEqual(
            sessions[0],
            SessionInfo(session_id="abc", trust="low", sensitivity="internal", updated_at=sessions[0].updated_at),
        )

    def test_missing_fields_default_to_clean(self):
        (self.state_dir / "abc.json").write_text(json.dumps({"session_id": "abc"}))
        sessions = discover_sessions(self.state_dir)
        self.assertEqual(sessions[0].trust, "high")
        self.assertEqual(sessions[0].sensitivity, "public")

    def test_multiple_sessions_sorted_most_recent_first(self):
        import os
        import time

        older = self.state_dir / "older.json"
        newer = self.state_dir / "newer.json"
        older.write_text(json.dumps({"session_id": "older"}))
        # Force a distinct, ordered mtime rather than relying on real-clock timing granularity.
        old_time = time.time() - 100
        os.utime(older, (old_time, old_time))
        newer.write_text(json.dumps({"session_id": "newer"}))

        sessions = discover_sessions(self.state_dir)
        self.assertEqual([s.session_id for s in sessions], ["newer", "older"])

    def test_malformed_state_file_is_skipped_not_raised(self):
        (self.state_dir / "broken.json").write_text("{not valid json")
        (self.state_dir / "good.json").write_text(json.dumps({"session_id": "good"}))
        sessions = discover_sessions(self.state_dir)
        self.assertEqual([s.session_id for s in sessions], ["good"])


class TestDiscoverScanResults(unittest.TestCase):
    """STORY-1005: scg monitor's resource panel reads .scalene/scan_cache.json
    directly (via ScanCache.all_entries()), not a parallel summary that
    could drift from the real store."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_cache_file_returns_empty(self):
        self.assertEqual(discover_scan_results(self.cache_path), [])

    def test_completed_scans_are_listed(self):
        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity="/abs/a.md", scanner_name="secrets"), ScanResult(label="public"))
        cache.put(
            Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
            ScanResult(label="trusted"),
        )

        results = discover_scan_results(self.cache_path)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(isinstance(r, ScanResultInfo) for r in results))
        identities = {r.identity for r in results}
        self.assertEqual(identities, {"/abs/a.md", "internal.example.com"})

    def test_results_are_newest_first(self):
        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity="/abs/older.md", scanner_name="secrets"), ScanResult(label="public"))
        import time

        time.sleep(0.01)
        cache.put(Resource(kind="file", identity="/abs/newer.md", scanner_name="secrets"), ScanResult(label="public"))

        results = discover_scan_results(self.cache_path)
        self.assertEqual([r.identity for r in results], ["/abs/newer.md", "/abs/older.md"])

    def test_in_flight_reservations_without_a_completed_scan_are_excluded(self):
        # A resource with only a pending_since reservation (no scan finished
        # yet) isn't a real result -- must not show up as if it were one.
        cache = ScanCache(self.cache_path)
        resource = Resource(kind="url", identity="never-finished.example.com", scanner_name="reputation")
        cache.try_reserve(resource)

        results = discover_scan_results(self.cache_path)
        self.assertEqual(results, [])

    def test_corrupted_cache_returns_empty_not_raised(self):
        # A live TUI must not crash on a broken cache store -- this is a
        # read-only monitoring view, not the fatal-exit hook path.
        self.cache_path.write_text("{not valid json")
        self.assertEqual(discover_scan_results(self.cache_path), [])

    def test_result_includes_reason_and_scanner_name(self):
        cache = ScanCache(self.cache_path)
        cache.put(
            Resource(kind="url", identity="203.0.113.42", scanner_name="reputation"),
            ScanResult(label="untrusted", reason="IP-literal targets are untrusted by default"),
        )
        results = discover_scan_results(self.cache_path)
        self.assertEqual(results[0].scanner_name, "reputation")
        self.assertIn("IP-literal", results[0].reason)


class TestDiscoverScannerActivity(unittest.TestCase):
    """docs/ARCHITECTURE.md sec20.2 (STORY-1602): one row per *configured*
    scanner (not just scanners with cache entries), busy = a real unexpired
    `pending_since` reservation for that scanner -- not simulated."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_scanner_with_no_cache_entries_at_all_is_idle_not_an_error(self):
        activity = discover_scanner_activity(self.cache_path, {"secrets": object(), "reputation": object()})
        self.assertEqual({a.name: a.busy for a in activity}, {"secrets": False, "reputation": False})

    def test_in_flight_reservation_makes_its_scanner_busy(self):
        cache = ScanCache(self.cache_path)
        cache.try_reserve(Resource(kind="url", identity="never-finished.example.com", scanner_name="reputation"))

        activity = discover_scanner_activity(self.cache_path, {"secrets": object(), "reputation": object()})
        by_name = {a.name: a.busy for a in activity}
        self.assertTrue(by_name["reputation"])
        self.assertFalse(by_name["secrets"])

    def test_completed_scan_with_no_pending_reservation_is_idle(self):
        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity="/abs/a.md", scanner_name="secrets"), ScanResult(label="public"))

        activity = discover_scanner_activity(self.cache_path, {"secrets": object()})
        self.assertFalse(activity[0].busy)

    def test_corrupted_cache_returns_all_idle_not_raised(self):
        self.cache_path.write_text("{not valid json")
        activity = discover_scanner_activity(self.cache_path, {"secrets": object()})
        self.assertEqual(activity, [ScannerActivity(name="secrets", busy=False)])


class TestBuildReviewEntry(unittest.TestCase):
    """docs/ARCHITECTURE.md sec20.4 (STORY-1604): reconstructs targets via
    the real `identify_targets()`, the same function `scg onboard` uses --
    no second identification mechanism."""

    def test_identifies_real_targets_from_the_real_tool_input(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="WebFetch",
            reason="blocked",
            event="block",
            block_kind="uncleared",
            tool_input={"url": "https://example.com/x"},
        )
        entry = build_review_entry(event, SCANNERS)
        self.assertEqual(len(entry.targets), 1)
        self.assertEqual(entry.targets[0].identity, "https://example.com/x")

    def test_no_targets_identified_yields_an_empty_list_not_an_error(self):
        event = ToolCallEvent(
            session_id="s1", tool_name="Bash", reason="blocked", event="block", tool_input={"command": "echo hi"}
        )
        entry = build_review_entry(event, SCANNERS)
        self.assertEqual(entry.targets, [])

    def test_all_verified_is_false_until_every_target_is_marked_verified(self):
        event = ToolCallEvent(
            session_id="s1",
            tool_name="WebFetch",
            reason="blocked",
            event="block",
            tool_input={"url": "https://example.com/x"},
        )
        entry = build_review_entry(event, SCANNERS)
        self.assertFalse(entry.all_verified)
        entry.verified[entry.targets[0].identity] = True
        self.assertTrue(entry.all_verified)

    def test_all_verified_is_false_with_zero_targets(self):
        # Nothing to verify shouldn't silently read as "verification done".
        event = ToolCallEvent(session_id="s1", tool_name="Bash", reason="blocked", event="block", tool_input={})
        entry = build_review_entry(event, SCANNERS)
        self.assertFalse(entry.all_verified)


class TestTargetStatus(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_never_scanned_target(self):
        cache = ScanCache(self.cache_path)
        resource = Resource(kind="url", identity="never-seen.example.com", scanner_name="reputation")
        self.assertEqual(target_status(resource, cache), "not yet scanned")

    def test_scanned_and_fresh_target(self):
        cache = ScanCache(self.cache_path)
        resource = Resource(kind="url", identity="known.example.com", scanner_name="reputation")
        cache.put(resource, ScanResult(label="trusted"))
        self.assertEqual(target_status(resource, cache), "trusted (fresh)")

    def test_scanned_but_expired_target(self):
        cache = ScanCache(self.cache_path)
        resource = Resource(kind="url", identity="stale.example.com", scanner_name="reputation")
        cache.put(resource, ScanResult(label="trusted"))
        # Directly age the entry past FRESHNESS_SECONDS rather than sleeping
        # in a test -- same technique used elsewhere in this suite for
        # freshness-boundary tests.
        import json as _json

        from scalene.scan_cache import FRESHNESS_SECONDS

        data = _json.loads(self.cache_path.read_text())
        key = f"reputation:{resource.identity}"
        data[key]["scanned_at"] -= FRESHNESS_SECONDS + 1
        self.cache_path.write_text(_json.dumps(data))

        self.assertEqual(target_status(resource, cache), "trusted (expired)")


class TestAuditTail(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.audit_log = Path(self._tmp.name) / "audit.log"

    def tearDown(self):
        self._tmp.cleanup()

    def _append(self, entry: dict) -> None:
        with self.audit_log.open("a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_missing_file_returns_empty(self):
        tail = AuditTail(self.audit_log)
        self.assertEqual(tail.poll(), [])

    def test_reads_block_events_not_onboard_events(self):
        # onboard.py writes {"event": "onboard", ...} to this same file --
        # must not surface as if it were a block.
        self._append({"event": "onboard", "rule": {}})
        self._append({"event": "block", "session_id": "s1", "tool_name": "Bash", "reason": "no validated rule"})
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(events, [ToolCallEvent(session_id="s1", tool_name="Bash", reason="no validated rule")])

    def test_reads_allow_events_too_not_just_blocks(self):
        # docs/ARCHITECTURE.md sec20.3 (STORY-1603, corrected 2026-07-22):
        # the monitor's event panel is a genuine tool-call stream now, not
        # a block-only feed.
        self._append({"event": "onboard", "rule": {}})
        self._append(
            {
                "event": "allow",
                "session_id": "s1",
                "tool_name": "Bash",
                "tool_input": {"command": "echo hi"},
                "reason": "",
                "block_kind": None,
            }
        )
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, "allow")
        self.assertIsNone(events[0].block_kind)
        self.assertEqual(events[0].tool_input, {"command": "echo hi"})

    def test_old_format_block_only_entry_without_new_fields_still_parses(self):
        # Backward compatibility (sec20.3): a pre-sec20 audit-log line has
        # no block_kind/tool_input at all -- must not crash the reader.
        self._append({"event": "block", "session_id": "s1", "tool_name": "Bash", "reason": "old-format reason"})
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].event, "block")
        self.assertIsNone(events[0].block_kind)
        self.assertEqual(events[0].tool_input, {})

    def test_second_poll_only_returns_newly_appended_events(self):
        self._append({"event": "block", "session_id": "s1", "tool_name": "Bash", "reason": "x"})
        tail = AuditTail(self.audit_log)
        first = tail.poll()
        self.assertEqual(len(first), 1)

        second = tail.poll()
        self.assertEqual(second, [])

        self._append({"event": "block", "session_id": "s2", "tool_name": "Write", "reason": "y"})
        third = tail.poll()
        self.assertEqual(len(third), 1)
        self.assertEqual(third[0].session_id, "s2")

    def test_malformed_line_is_skipped_not_raised(self):
        with self.audit_log.open("a") as f:
            f.write("{not valid json\n")
        self._append({"event": "block", "session_id": "s1", "tool_name": "Bash", "reason": "x"})
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        self.assertEqual(len(events), 1)

    def test_can_filter_by_session_id(self):
        self._append({"event": "block", "session_id": "s1", "tool_name": "Bash", "reason": "x"})
        self._append({"event": "block", "session_id": "s2", "tool_name": "Write", "reason": "y"})
        tail = AuditTail(self.audit_log)
        events = tail.poll()
        s1_only = [e for e in events if e.session_id == "s1"]
        self.assertEqual(len(s1_only), 1)
        self.assertEqual(len(events), 2)


if __name__ == "__main__":
    unittest.main()
