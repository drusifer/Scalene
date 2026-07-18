"""Integration tests for the `scg monitor` TUI (STORY-701/702), using
Textual's built-in headless test harness (`App.run_test()` / `Pilot`) rather
than a real terminal or hand-rolled mocking.

2026-07-17 (docs/ARCHITECTURE.md sec15): rewritten for trust/sensitivity
session tags and BlockEvent (replacing has_sensitive_data/has_untrusted_data
and MaskEvent). STORY-702's editable-command-input workflow is removed with
its tests -- clearing a destination now always takes two explicit steps
(a real scan, then a hand-authored rule), not one runnable command."""

import json
import tempfile
import unittest
from pathlib import Path

from textual.widgets import DataTable

from scalene.monitor_app import MonitorApp, _NO_SESSIONS_MESSAGE, _format_relative_time


def _write_state(state_dir: Path, session_id: str, trust: str = "high", sensitivity: str = "public") -> None:
    (state_dir / f"{session_id}.json").write_text(json.dumps({"session_id": session_id, "trust": trust, "sensitivity": sensitivity}))


def _append_block_event(audit_log: Path, session_id: str, tool_name: str = "Bash") -> None:
    with audit_log.open("a") as f:
        f.write(
            json.dumps(
                {
                    "event": "block",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "reason": "no validated, explicitly-allowed rule",
                }
            )
            + "\n"
        )


class TestFormatRelativeTime(unittest.TestCase):
    """Smith's Phase 5 gate finding: the absolute 'YYYY-MM-DD HH:MM:SS'
    format was too wide once a 3rd panel divided the same horizontal space
    2 panels used to have, truncating to an unreadable string in a real
    rendered screenshot at a common 120-column width. Relative format is
    both shorter and arguably more useful for a live monitoring view."""

    def test_seconds_ago(self):
        now = 1000.0
        self.assertEqual(_format_relative_time(now - 5, now=now), "5s ago")

    def test_minutes_ago(self):
        now = 1000.0
        self.assertEqual(_format_relative_time(now - 125, now=now), "2m ago")

    def test_hours_ago(self):
        now = 100000.0
        self.assertEqual(_format_relative_time(now - 7300, now=now), "2h ago")

    def test_days_ago(self):
        now = 1000000.0
        self.assertEqual(_format_relative_time(now - 172800, now=now), "2d ago")

    def test_clock_skew_does_not_produce_a_negative_time(self):
        # scanned_at slightly in the future (real-world clock skew between
        # a worker process and the monitor process reading it) must not
        # render as "-1s ago".
        now = 1000.0
        self.assertEqual(_format_relative_time(now + 5, now=now), "0s ago")

    def test_result_is_short_enough_to_fit_a_narrow_column(self):
        # The whole point of this fix -- must be comfortably shorter than
        # the old 19-char absolute timestamp that caused the truncation.
        now = 1000000.0
        for delta in (5, 125, 7300, 172800):
            self.assertLess(len(_format_relative_time(now - delta, now=now)), 10)


class TestMonitorApp(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_shows_no_sessions_message_when_none_exist(self):
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            widget = app.query_one("#no-sessions")
            self.assertIn("visible", widget.classes)
            self.assertEqual(widget.content, _NO_SESSIONS_MESSAGE)

    async def test_discovers_sessions_and_hides_empty_message(self):
        _write_state(self.state_dir, "s1", trust="low")
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            widget = app.query_one("#no-sessions")
            self.assertNotIn("visible", widget.classes)
            table = app.query_one("#sessions", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_session_row_shows_trust_and_sensitivity(self):
        _write_state(self.state_dir, "s1", trust="low", sensitivity="restricted")
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            table = app.query_one("#sessions", DataTable)
            row = table.get_row_at(0)
            self.assertEqual(row, ["s1", "low", "restricted"])

    async def test_default_selection_is_first_session_and_filters_events(self):
        _write_state(self.state_dir, "s1", trust="low")
        _append_block_event(self.audit_log, "s1", tool_name="Bash")
        _append_block_event(self.audit_log, "other-session", tool_name="Write")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            self.assertEqual(app.selected_session_id, "s1")
            events_table = app.query_one("#events", DataTable)
            # Only s1's event should be visible by default (not other-session's).
            self.assertEqual(events_table.row_count, 1)

    async def test_events_are_shown_newest_first(self):
        # STORY-701 AC: "newest first, as they're appended."
        _write_state(self.state_dir, "s1", trust="low")
        _append_block_event(self.audit_log, "s1", tool_name="Bash")
        _append_block_event(self.audit_log, "s1", tool_name="Write")
        _append_block_event(self.audit_log, "s1", tool_name="Edit")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            tool_column = [events_table.get_row_at(i)[1] for i in range(events_table.row_count)]
            self.assertEqual(tool_column, ["Edit", "Write", "Bash"])

    async def test_toggle_all_sessions_shows_every_session_event(self):
        _write_state(self.state_dir, "s1", trust="low")
        _append_block_event(self.audit_log, "s1")
        _append_block_event(self.audit_log, "other-session")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            self.assertEqual(events_table.row_count, 1)

            await pilot.press("a")
            self.assertEqual(events_table.row_count, 2)

    async def test_cursor_stays_on_selected_session_across_a_poll_refresh(self):
        # Regression for a real bug (Smith's *user test, 2026-07-10): selecting
        # a non-default session, then any poll tick (e.g. a new block event for
        # a *different* session) must not visually reset the highlighted row
        # to the top while the actual filter silently stays on the real
        # selection — the highlighted row and the filtered session must never
        # diverge (Nielsen #1: visibility of system status).
        _write_state(self.state_dir, "s1")
        _write_state(self.state_dir, "s2")
        _write_state(self.state_dir, "s3")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            table = app.query_one("#sessions", DataTable)
            table.move_cursor(row=2)
            await pilot.press("enter")
            await pilot.pause()
            selected_after_click = app.selected_session_id
            row_after_click = table.cursor_row

            _append_block_event(self.audit_log, "some-other-session")
            app.poll_data()
            await pilot.pause()

            self.assertEqual(app.selected_session_id, selected_after_click)
            self.assertEqual(table.cursor_row, row_after_click)

    async def test_never_shows_an_event_for_a_non_block_audit_entry(self):
        # Regression guard for STORY-701's core AC: onboard.py writes
        # {"event": "onboard", ...} to the same audit.log — must never render
        # as a block event.
        _write_state(self.state_dir, "s1")
        with self.audit_log.open("a") as f:
            f.write(json.dumps({"event": "onboard", "rule": {}}) + "\n")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            await pilot.press("a")  # show all sessions too, still should be empty
            events_table = app.query_one("#events", DataTable)
            self.assertEqual(events_table.row_count, 0)

    async def test_event_row_shows_the_block_reason(self):
        _write_state(self.state_dir, "s1", trust="low")
        _append_block_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            row = events_table.get_row_at(0)
            self.assertEqual(row, ["s1", "Bash", "no validated, explicitly-allowed rule"])

    async def test_poll_data_after_teardown_does_not_raise(self):
        # Regression for a real, if rare, flake observed in this suite: the
        # 500ms poll timer can fire after `run_test()`'s screen has already
        # torn down (`query_one("#sessions")` -> NoMatches), crashing the
        # whole test run. Reproduce deterministically (no real-time race
        # needed) by calling poll_data() after the app context has exited.
        _write_state(self.state_dir, "s1")
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            pass
        app.poll_data()  # must not raise NoMatches after teardown


class TestMonitorAppScanResultsPanel(unittest.IsolatedAsyncioTestCase):
    """STORY-1005: the resource cache panel reads .scalene/scan_cache.json
    directly, no separate/duplicated bookkeeping."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_empty_cache_shows_no_rows(self):
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            table = app.query_one("#scan-results", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_shows_real_cache_entries(self):
        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource, ScanResult

        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity="/abs/readme.md", scanner_name="secrets"), ScanResult(label="public"))
        cache.put(
            Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
            ScanResult(label="trusted"),
        )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            table = app.query_one("#scan-results", DataTable)
            self.assertEqual(table.row_count, 2)

    async def test_new_scan_appears_after_a_poll(self):
        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource, ScanResult

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            table = app.query_one("#scan-results", DataTable)
            self.assertEqual(table.row_count, 0)

            ScanCache(self.cache_path).put(
                Resource(kind="file", identity="/abs/new.md", scanner_name="secrets"), ScanResult(label="public")
            )
            app.poll_data()
            await pilot.pause()

            self.assertEqual(table.row_count, 1)

    async def test_row_content_shows_the_real_resource_and_label_not_just_a_count(self):
        # Trin's UAT addition: Neo's own tests only assert row *counts* for
        # this panel (same class of gap Trin found+closed for the mask-event
        # feed back in Sprint 2) -- verifying actual cell content here.
        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource, ScanResult

        ScanCache(self.cache_path).put(
            Resource(kind="url", identity="internal.example.com", scanner_name="reputation"),
            ScanResult(label="trusted"),
        )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            table = app.query_one("#scan-results", DataTable)
            row = table.get_row_at(0)
            self.assertEqual(row[0], "internal.example.com")
            self.assertEqual(row[1], "trusted")
            self.assertIn("ago", str(row[2]))  # relative format, not the old truncation-prone absolute timestamp

    async def test_in_flight_reservation_does_not_appear_as_a_result(self):
        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource

        ScanCache(self.cache_path).try_reserve(Resource(kind="url", identity="pending.example.com", scanner_name="reputation"))

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            table = app.query_one("#scan-results", DataTable)
            self.assertEqual(table.row_count, 0)

    async def test_last_scanned_column_is_not_truncated_at_a_common_terminal_width(self):
        # Regression test for Smith's Phase 5 gate finding: a real rendered
        # screenshot at a common 120-column width showed the "Last Scanned"
        # header truncated to " La" and values truncated to " 0s" when this
        # panel was a 3rd side-by-side column -- neither a row-count check
        # nor a stored-cell-value check would catch this, since the
        # underlying data was correct; only the *rendered* text was cut off.
        # Fixed by giving the panel its own full-width row. Checks the
        # actual rendered SVG text, not the DataTable's stored data.
        import re

        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource, ScanResult

        ScanCache(self.cache_path).put(
            Resource(kind="file", identity="/workspace/some/deeply/nested/path/README.md", scanner_name="secrets"),
            ScanResult(label="public"),
        )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            svg = app.export_screenshot()
            rendered_text = " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))
            rendered_text = rendered_text.replace("&#160;", " ")

            self.assertIn("Last Scanned", rendered_text)
            self.assertIn("0s ago", rendered_text)
            self.assertIn("/workspace/some/deeply/nested/path/README.md", rendered_text)


if __name__ == "__main__":
    unittest.main()
