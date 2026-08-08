"""Integration tests for the `scg monitor` TUI (STORY-701/702), using
Textual's built-in headless test harness (`App.run_test()` / `Pilot`) rather
than a real terminal or hand-rolled mocking.

2026-07-17 (docs/ARCHITECTURE.md sec15): rewritten for trust/sensitivity
session tags and BlockEvent (replacing has_sensitive_data/has_untrusted_data
and MaskEvent). STORY-702's editable-command-input workflow is removed with
its tests -- clearing a destination now always takes two explicit steps
(a real scan, then a hand-authored rule), not one runnable command."""

import json
import re
import tempfile
import unittest
from pathlib import Path

from textual.widgets import DataTable, Input, RadioButton, Static

from scalene.monitor_app import MonitorApp, RulesScreen, _NO_SESSIONS_MESSAGE, _format_relative_time
from scalene.monitor_data import ToolCallEvent
from scalene.scanner import Resource, escape_gitignore_literal

from _fast_async import FastIsolatedAsyncioTestCase


def _write_state(state_dir: Path, session_id: str, trust: str = "high", sensitivity: str = "public") -> None:
    (state_dir / f"{session_id}.json").write_text(json.dumps({"session_id": session_id, "trust": trust, "sensitivity": sensitivity}))


def _append_block_event(
    audit_log: Path, session_id: str, tool_name: str = "Bash", block_kind: str | None = "uncleared"
) -> None:
    with audit_log.open("a") as f:
        f.write(
            json.dumps(
                {
                    "event": "block",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "reason": "no validated, explicitly-allowed rule",
                    "block_kind": block_kind,
                }
            )
            + "\n"
        )


def _append_allow_event(audit_log: Path, session_id: str, tool_name: str = "Bash") -> None:
    with audit_log.open("a") as f:
        f.write(
            json.dumps(
                {
                    "event": "allow",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "tool_input": {},
                    "reason": "",
                    "block_kind": None,
                }
            )
            + "\n"
        )


async def _open_review(pilot, app, row: int = 0) -> None:
    """docs/ARCHITECTURE.md sec22.1/22.2 (STORY-1701): supersedes the old
    'r'-opens-oldest-pending binding -- opening a review is now moving the
    `#queue` table's cursor to the target row and pressing Enter, same as a
    real user would. Row 0 is still "oldest" (the queue's own FIFO order),
    so this is a drop-in replacement everywhere the old shortcut opened the
    single oldest review."""
    table = app.query_one("#queue", DataTable)
    table.move_cursor(row=row)
    await pilot.press("enter")
    await pilot.pause()



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


class TestMonitorApp(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec22.2 (STORY-1701/1702): the queue-first home
    screen. The Sessions table, per-session Events log, and 'a' toggle-all-
    sessions binding (E16/STORY-1603's tagged full-call-stream panel) are
    retired outright by this epic, not replaced -- their old tests (session
    selection/filtering, event tag legibility) are removed along with the
    surface they tested, not adapted."""

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

    async def test_session_line_shows_the_latest_sessions_id_trust_and_sensitivity(self):
        # docs/ARCHITECTURE.md sec22.2 (STORY-1702): one line, not a table --
        # `discover_sessions()` already sorts recent-first, so the most
        # recently-touched session's own state file (written last) is what
        # shows.
        _write_state(self.state_dir, "s1", trust="low", sensitivity="restricted")
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            widget = app.query_one("#no-sessions")
            self.assertNotIn("visible", widget.classes)
            content = str(app.query_one("#session-line", Static).content)
            self.assertIn("s1", content)
            self.assertIn("low", content)
            self.assertIn("restricted", content)

    async def test_session_line_tracks_the_latest_session_live_not_sticky(self):
        # STORY-1702's core AC: a prior sticky `is None`-guarded selection
        # never re-pointed at a newer session once set. This must. Forces a
        # distinct, ordered mtime (same technique as test_monitor_data.py's
        # test_multiple_sessions_sorted_most_recent_first) rather than
        # relying on real-clock timing granularity between two writes.
        import os
        import time as _time

        _write_state(self.state_dir, "s1")
        older_time = _time.time() - 100
        os.utime(self.state_dir / "s1.json", (older_time, older_time))

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIn("s1", str(app.query_one("#session-line", Static).content))

            _write_state(self.state_dir, "s2")  # real current mtime, newer than s1's forced one
            app.poll_data()
            await pilot.pause()
            self.assertIn("s2", str(app.query_one("#session-line", Static).content))

    async def test_never_queues_a_review_for_a_non_block_audit_entry(self):
        # Regression guard for STORY-701's core AC: onboard.py writes
        # {"event": "onboard", ...} to the same audit.log — must never
        # surface as a queued review.
        _write_state(self.state_dir, "s1")
        with self.audit_log.open("a") as f:
            f.write(json.dumps({"event": "onboard", "rule": {}}) + "\n")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(app.query_one("#queue", DataTable).row_count, 0)

    async def test_queue_shows_no_pending_reviews_message_when_empty(self):
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            widget = app.query_one("#no-queue")
            self.assertIn("visible", widget.classes)

    async def test_queue_row_shows_tool_resource_count_kind_reason_and_hides_empty_message(self):
        _write_state(self.state_dir, "s1", trust="low")
        _append_block_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            no_queue_widget = app.query_one("#no-queue")
            self.assertNotIn("visible", no_queue_widget.classes)

            table = app.query_one("#queue", DataTable)
            self.assertEqual(table.row_count, 1)
            row = table.get_row_at(0)
            # ID, Tool, Resource, Kind, Reason, Count, Last Seen (sec23.2/23.3)
            self.assertEqual(row[0], "1")
            self.assertEqual(row[1], "Bash")
            self.assertEqual(row[4], "no validated, explicitly-allowed rule")
            self.assertEqual(row[5], "1")

    async def test_poll_data_after_teardown_does_not_raise(self):
        # Regression for a real, if rare, flake observed in this suite: the
        # 500ms poll timer can fire after `run_test()`'s screen has already
        # torn down (`query_one("#queue")` -> NoMatches), crashing the whole
        # test run. Reproduce deterministically (no real-time race needed)
        # by calling poll_data() after the app context has exited.
        _write_state(self.state_dir, "s1")
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            pass
        app.poll_data()  # must not raise NoMatches after teardown

    async def test_session_line_and_reason_column_are_not_truncated_at_a_common_terminal_width(self):
        # Smith's E17 Gate 1 carried non-blocking note (agents/smith.docs/
        # e17_gate1_review.md): both are single lines built by string
        # concatenation, the exact shape that has already caused a real
        # truncation bug once (Sprint 4 Phase 5, the old "Last Scanned"
        # panel) once a real terminal width came into play -- Oracle's
        # 2026-07-15 lesson ("a row-content check is not a rendering
        # check") applies here too. Checks the actual rendered SVG text at
        # a common 120-column width, not the DataTable's stored data.
        import re

        _write_state(self.state_dir, "a1b2c3d4e5f6g7h8", trust="low", sensitivity="internal")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "a1b2c3d4e5f6g7h8",
                        "tool_name": "Read",
                        "reason": "no validated, explicitly-allowed rule -- wait for review, then retry.",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test(size=(120, 30)) as pilot:
            app.poll_data()
            await pilot.pause()
            svg = app.export_screenshot()
            rendered_text = " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))
            rendered_text = rendered_text.replace("&#160;", " ")

            self.assertIn("a1b2c3d4e5f6g7h8", rendered_text)
            self.assertIn("no validated, explicitly-allowed rule -- wait for review, then retry.", rendered_text)

    async def test_status_strip_shows_scanner_activity_and_renders_above_the_footer(self):
        # docs/ARCHITECTURE.md sec22.3 (STORY-1703): the strip's own CSS
        # comment flags the dock-order stacking as a claim to verify against
        # the real installed Textual, not assumed -- checks the real
        # rendered geometry (region.y), the same technique this project's
        # own standing rule prescribes for "does this widget render within
        # bounds" claims, not a stored-value check.
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test(size=(120, 30)) as pilot:
            await pilot.pause()
            strip = app.query_one("#status-strip", Static)
            footer = app.query_one("Footer")
            self.assertIn("Scanners:", str(strip.content))
            self.assertIn("secrets", str(strip.content))
            self.assertIn("reputation", str(strip.content))
            # Strip must be strictly above (not overlapping) the footer.
            self.assertLessEqual(strip.region.y + strip.region.height, footer.region.y)

    async def test_status_strip_updates_live_on_a_poll_tick_not_just_at_mount(self):
        # Trin's UAT (E17 Phase 2): same class of gap Morpheus's Phase 1
        # review caught for #queue -- a refresh wired only into on_mount
        # would show correct data once, then go stale forever. A real
        # ScanCache reservation appearing between polls must flip the
        # strip from idle to busy on the next poll_data(), not just at
        # startup.
        from scalene.scan_cache import ScanCache

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertIn("reputation idle", str(app.query_one("#status-strip", Static).content))

            ScanCache(self.cache_path).try_reserve(
                Resource(kind="url", identity="never-finished.example.com", scanner_name="reputation")
            )
            app.poll_data()
            await pilot.pause()
            self.assertIn("reputation busy", str(app.query_one("#status-strip", Static).content))


class TestReviewQueueAndDashboard(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec20.4 (STORY-1604): read-side of the review
    queue/dashboard -- Verify only, no Allow/Deny actions yet (Phase 5)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block_with_url(self, tool_name: str, url: str) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": tool_name,
                        "tool_input": {"url": url},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

    async def test_a_new_block_event_is_queued_for_review(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 1)
            self.assertEqual(app._pending_reviews[0].targets[0].identity, "https://evil.example.com/x")

    async def test_a_new_block_event_updates_the_title_with_the_pending_count(self):
        # docs/ARCHITECTURE.md sec20.4, Smith's Gate 1 hard-requirement
        # watch-item: a queued review must be noticeable (Nielsen #1), not
        # just present. Title is the part of the attention signal that's
        # actually assertable in a headless test (bell() has no observable
        # state here beyond "it didn't raise").
        _write_state(self.state_dir, "s1", trust="low")
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(app.title, "scg monitor")

            self._append_block_with_url("WebFetch", "https://evil.example.com/x")
            app.poll_data()
            await pilot.pause()
            self.assertIn("1 pending review", app.title)

            self._append_block_with_url("WebFetch", "https://also-evil.example.com/x")
            app.poll_data()
            await pilot.pause()
            self.assertIn("2 pending reviews", app.title)

    async def test_denying_a_review_drops_the_title_count_back_to_zero(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertIn("1 pending review", app.title)

            await _open_review(pilot, app)
            await pilot.click(app.screen.query_one("#deny-btn"))
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(app.title, "scg monitor")

    async def test_denying_a_review_removes_it_from_the_queue_table_immediately(self):
        # Morpheus's Phase 1 code review finding: `#queue` didn't exist when
        # `_on_review_resolved` was written (E16) -- without a
        # `refresh_queue()` call there, a resolved entry would sit stale on
        # screen until the next 0.5s poll tick happened to redraw it.
        # Checks the real table, not just `_pending_reviews`/title (both of
        # which already updated correctly before this fix).
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(app.query_one("#queue", DataTable).row_count, 1)

            await _open_review(pilot, app)
            await pilot.click(app.screen.query_one("#deny-btn"))
            await pilot.pause()

            self.assertEqual(app.query_one("#queue", DataTable).row_count, 0)
            self.assertIn("visible", app.query_one("#no-queue").classes)

    async def test_an_allow_event_is_not_queued_for_review(self):
        _write_state(self.state_dir, "s1")
        _append_allow_event(self.audit_log, "s1", tool_name="Read")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(app._pending_reviews, [])

    async def test_multiple_block_events_queue_oldest_first(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://first.example.com/x")
        self._append_block_with_url("WebFetch", "https://second.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 2)
            self.assertEqual(app._pending_reviews[0].targets[0].identity, "https://first.example.com/x")

    async def test_next_prev_navigates_between_queued_reviews_and_shows_position(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://first.example.com/x")
        self._append_block_with_url("WebFetch", "https://second.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            self.assertEqual(app.screen.query_one("#review-position", Static).content, "Review 1 of 2")
            self.assertTrue(app.screen.query_one("#prev-btn").disabled)
            self.assertFalse(app.screen.query_one("#next-btn").disabled)
            table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(table.get_row_at(0)[0], "https://first.example.com/x")

            await pilot.click(app.screen.query_one("#next-btn"))
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#review-position", Static).content, "Review 2 of 2")
            self.assertFalse(app.screen.query_one("#prev-btn").disabled)
            self.assertTrue(app.screen.query_one("#next-btn").disabled)
            table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(table.get_row_at(0)[0], "https://second.example.com/x")

            await pilot.click(app.screen.query_one("#prev-btn"))
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#review-position", Static).content, "Review 1 of 2")
            table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(table.get_row_at(0)[0], "https://first.example.com/x")

    async def test_denying_after_navigating_to_the_second_review_dequeues_that_one_not_the_first(self):
        # Regression test for the dismiss()-closure bug Next/Prev would
        # otherwise expose: the entry dequeued must be whichever one was
        # actually showing when Deny was pressed, not always the entry the
        # screen was originally opened with.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://first.example.com/x")
        self._append_block_with_url("WebFetch", "https://second.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            await pilot.click(app.screen.query_one("#next-btn"))
            await pilot.pause()

            await pilot.click(app.screen.query_one("#deny-btn"))
            await pilot.pause()

            self.assertEqual(len(app._pending_reviews), 1)
            self.assertEqual(app._pending_reviews[0].targets[0].identity, "https://first.example.com/x")

    async def test_review_screen_shows_the_real_tool_call_and_target_status(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            table = app.screen.query_one("#targets", DataTable)
            row = table.get_row_at(0)
            self.assertEqual(row[0], "https://evil.example.com/x")
            self.assertEqual(row[2], "not yet scanned")
            self.assertEqual(row[3], "no")

    async def test_verify_runs_a_real_scan_and_updates_status_and_verified_flag(self):
        _write_state(self.state_dir, "s1", trust="low")
        # A never-before-seen file: LocalHeuristicChecker/FileScanner will
        # actually run for real against this exact path.
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": str(target_path)},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            verify_button = app.screen.query_one("#verify-btn")
            await pilot.click(verify_button)
            await pilot.pause()

            table = app.screen.query_one("#targets", DataTable)
            row = table.get_row_at(0)
            self.assertEqual(row[3], "yes")
            self.assertIn("fresh", row[2])

            # Confirms this actually reached the real ScanCache, not just
            # updated in-memory review-entry state.
            from scalene.scan_cache import ScanCache
            from scalene.scanner import Resource

            entry = ScanCache(self.cache_path).get(Resource(kind="file", identity=str(target_path), scanner_name="secrets"))
            self.assertIsNotNone(entry)
            self.assertEqual(entry.label, "public")

    async def test_verified_status_survives_a_monitor_restart(self):
        # Direct user report: "restarted scg monitor and it lost the
        # verified status." Root cause: verification used to live in a
        # separate in-memory ReviewEntry.verified dict that build_review_entry()
        # always reconstructs empty -- including on every restart -- even
        # though the real ScanCache entry Verify wrote was still there and
        # still fresh. Verified is derived live from that same real cache
        # now, so a second MonitorApp instance pointed at the same
        # cache_path (simulating a restart) must already show the target
        # verified and Allow already enabled, with no second Verify click.
        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": str(target_path)},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        first_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            await _open_review(pilot, first_run)
            await pilot.click(first_run.screen.query_one("#verify-btn"))
            await pilot.pause()
            self.assertFalse(first_run.screen.query_one("#allow-btn").disabled)

        # A brand-new MonitorApp/ReviewScreen -- same as actually restarting
        # `scg monitor` -- pointed at the same real .scalene/ state.
        second_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            await _open_review(pilot, second_run)
            table = second_run.screen.query_one("#targets", DataTable)
            self.assertEqual(table.get_row_at(0)[3], "yes")
            self.assertFalse(second_run.screen.query_one("#allow-btn").disabled)

    async def test_denied_review_does_not_reappear_after_a_monitor_restart(self):
        # Direct user report: "review status is not persisted (always
        # resets to 6 pending reviews on restart)". Root cause: a fresh
        # AuditTail always starts at byte offset 0, so every restart
        # re-read the whole audit log and re-queued every historical block
        # event, including ones already Denied -- Deny wrote nothing
        # anywhere marking it dealt with. Denying now appends a
        # `review_resolved` marker (referencing the block event's own
        # log_offset) to the same real audit.log; a restart's first poll()
        # nets it back out instead of re-queuing it.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        first_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            self.assertEqual(len(first_run._pending_reviews), 1)
            await _open_review(pilot, first_run)
            await pilot.click(first_run.screen.query_one("#deny-btn"))
            await pilot.pause()
            self.assertEqual(first_run._pending_reviews, [])

        second_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(second_run._pending_reviews, [])
            self.assertNotIn("pending review", second_run.title)

    async def test_allowed_review_does_not_reappear_after_a_monitor_restart(self):
        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": str(target_path)},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

        first_run = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            await _open_review(pilot, first_run)
            await pilot.click(first_run.screen.query_one("#verify-btn"))
            await pilot.pause()
            await pilot.click(first_run.screen.query_one("#allow-btn"))
            await pilot.pause()
            self.assertEqual(first_run._pending_reviews, [])

        second_run = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(second_run._pending_reviews, [])

    async def test_still_pending_reviews_do_reappear_after_a_monitor_restart(self):
        # The other half of the same fix, guarding against overcorrecting:
        # sec20.4's own design is "an entry that never gets reviewed just
        # stays queued" -- a review nobody has acted on yet must still
        # reappear, not be silently dropped.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        first_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            self.assertEqual(len(first_run._pending_reviews), 1)

        second_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(len(second_run._pending_reviews), 1)

    async def test_allow_button_is_disabled_until_verify_completes(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            allow_button = app.screen.query_one("#allow-btn")
            self.assertTrue(allow_button.disabled)

            verify_button = app.screen.query_one("#verify-btn")
            await pilot.click(verify_button)
            await pilot.pause()

            self.assertFalse(allow_button.disabled)

    async def test_verify_unlocks_allow_for_a_write_targeting_a_file_that_does_not_exist_yet(self):
        # Direct user bug report (2026-08-07): pre_tool_use runs *before*
        # the tool itself executes, so a real Write's target is identified
        # and Verify-able while it still doesn't exist on disk yet -- there
        # is nothing to scan, which is not the same claim as "the scanning
        # machinery is broken." Before the fix, Verify silently swallowed a
        # ScannerMachineryError for this exact case and Allow stayed
        # disabled forever, with no way to ever allow creating a new file.
        _write_state(self.state_dir, "s1", trust="low")
        new_file_target = str(Path(self._tmp.name) / "brand-new-file-that-does-not-exist-yet.txt")
        self.assertFalse(Path(new_file_target).exists())
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Write",
                        "tool_input": {"file_path": new_file_target, "content": "hello"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            allow_button = app.screen.query_one("#allow-btn")
            self.assertTrue(allow_button.disabled)

            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()

            self.assertFalse(allow_button.disabled)
            targets_table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(targets_table.get_row_at(0)[3], "yes")  # Verified column

            await pilot.click(allow_button)
            await pilot.pause()
            await pilot.pause()

        self.assertTrue(policy_path.exists())
        self.assertIn("mode: allow", policy_path.read_text())

        # Trin's UAT: the actual point, proven end-to-end through the real
        # hook -- the agent's retried Write (still to a file that doesn't
        # exist -- Scalene never creates it, only the real tool does) now
        # genuinely succeeds, same standard as every other Allow-then-retry
        # test in this file.
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig

        self.assertFalse(Path(new_file_target).exists())
        retry = pre_tool_use(
            {"session_id": "s1", "tool_name": "Write", "tool_input": {"file_path": new_file_target, "content": "hello"}},
            PolicyConfig.from_yaml(policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(retry["hookSpecificOutput"]["permissionDecision"], "allow")

    async def test_deny_resolves_the_review_and_writes_no_rule(self):
        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": str(target_path)},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 1)

            await _open_review(pilot, app)
            deny_button = app.screen.query_one("#deny-btn")
            await pilot.click(deny_button)
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])  # dequeued
            self.assertFalse(policy_path.exists())  # no rule written

    async def test_escape_without_a_decision_keeps_the_review_queued(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            await pilot.press("escape")
            await pilot.pause()

            self.assertEqual(len(app._pending_reviews), 1)  # still queued

    async def test_allow_writes_a_real_rule_and_a_retry_of_the_same_call_is_then_allowed(self):
        # End-to-end per task.md Phase 5 exit criteria: block -> dashboard
        # -> Verify -> Allow -> retry the identical original call succeeds.
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig

        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        hook_input = {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": str(target_path)}}

        # Real original call, through the real hook -- confirms it's
        # genuinely blocked before any of this test's setup.
        first = pre_tool_use(
            hook_input,
            PolicyConfig(),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "deny")

        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        # Default 80x24 test size clips the Allow form (below the button
        # row, several widgets tall) out of the visible viewport once the
        # rest of the screen (Header/tool-input/DataTable/buttons) claims
        # its share -- a real click at an off-screen region is a no-op, not
        # an error, which is why this needs a taller terminal, not more waiting.
        async with app.run_test(size=(100, 50)) as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            await pilot.click(app.screen.query_one("#allow-btn"))
            # Screen.dismiss()'s result callback is scheduled via
            # requester.call_next(), not invoked synchronously (Textual's
            # own screen.py: ResultCallback.__call__) -- pauses are needed
            # for it to actually run, not just for the click's own
            # immediate effects.
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])

        # Retry the exact same original call through the real hook again --
        # a fresh PolicyConfig loaded from the real, just-written policy file.
        second = pre_tool_use(
            hook_input,
            PolicyConfig.from_yaml(policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "allow")

    async def test_bad_finding_blocks_allow_unless_mode_is_block(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        # See the sizing note in test_allow_writes_a_real_rule_... above --
        # the Allow form is clipped out of the default 80x24 viewport.
        async with app.run_test(size=(100, 50)) as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            # Verify will run the real URLScanner/reputation check against a
            # made-up hostname -- not guaranteed bad, so seed a real bad
            # cache entry directly the way a genuine scan finding would.
            from scalene.scan_cache import ScanCache
            from scalene.scanner import Resource, ScanResult

            ScanCache(self.cache_path).put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="known bad reputation"),
            )
            # Verified is derived live from this same real cache entry now
            # (2026-07-30) -- no separate flag to seed.
            app.screen.refresh_targets()

            await pilot.click(app.screen.query_one("#allow-btn"))  # mode defaults to "allow"
            await pilot.pause()
            await pilot.pause()

            self.assertFalse(policy_path.exists())
            self.assertIn("known bad reputation", app.screen.query_one("#allow-error", Static).content)

    async def test_mode_block_explicitly_overrides_a_bad_finding(self):
        # Trin UAT (2026-07-23): the previous test only proves the negative
        # (mode=allow correctly blocked) -- never actually exercised the
        # documented mode=block escape hatch onboard._onboard_resource has
        # always had. Real gap, not assumed to work by symmetry.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with app.run_test(size=(100, 50)) as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            from scalene.scan_cache import ScanCache
            from scalene.scanner import Resource, ScanResult

            ScanCache(self.cache_path).put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="known bad reputation"),
            )
            # Verified is derived live from this same real cache entry now
            # (2026-07-30) -- no separate flag to seed.
            app.screen.refresh_targets()

            # Mode must be selected before the single Allow click now (it
            # submits directly, not a two-step reveal-then-submit).
            await pilot.click(app.screen.query_one("#mode-block"))
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()

            self.assertTrue(policy_path.exists())
            written = policy_path.read_text()
            self.assertIn("mode: block", written)
            self.assertEqual(app._pending_reviews, [])

    async def test_allow_writes_one_rule_per_target_for_a_multi_target_call(self):
        # Trin UAT (2026-07-23): every prior Allow test used a single-target
        # call -- a real batch call (e.g. a command touching 2 URLs) needs
        # one rule written per target, not just the first.
        _write_state(self.state_dir, "s1", trust="low")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": "curl https://first.example.com/x https://second.example.com/y"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with app.run_test(size=(100, 50)) as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews[0].targets), 2)

            await _open_review(pilot, app)
            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()

            self.assertTrue(policy_path.exists())
            # re.escape() means the written pattern has literal backslashes
            # before each dot (e.g. "first\.example\.com") -- assert against
            # that real written form, not the plain hostname.
            written = policy_path.read_text()
            self.assertIn(r"first\.example\.com", written)
            self.assertIn(r"second\.example\.com", written)
            self.assertEqual(written.count("mode: allow"), 2)

    async def test_selecting_a_non_first_queue_row_opens_that_review_not_the_oldest(self):
        # Trin's UAT (E17 Phase 1): STORY-1701's actual point -- the old
        # 'r' binding could only ever reach index 0. Confirms clicking/
        # selecting row 1 directly opens the *second* queued review, not
        # always the oldest, driven through the real queue table (not by
        # calling push_screen with an explicit index directly).
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://first.example.com/x")
        self._append_block_with_url("WebFetch", "https://second.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app, row=1)
            table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(table.get_row_at(0)[0], "https://second.example.com/x")
            self.assertEqual(app.screen.query_one("#review-position", Static).content, "Review 2 of 2")

    async def test_queue_spans_every_session_not_just_the_latest_one(self):
        # Trin's UAT (E17 Phase 1): the queue was already session-agnostic
        # before this epic (Smith's consult grounding) -- confirms that
        # didn't regress now that the Sessions table/selection UI (the
        # thing that used to filter a *different* panel) is gone. A block
        # from an old session still shows up even though the session line
        # now only ever names the latest one.
        import os
        import time

        _write_state(self.state_dir, "old-session", trust="low")
        older_time = time.time() - 100
        os.utime(self.state_dir / "old-session.json", (older_time, older_time))
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://from-old-session.example.com/x")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "old-session",
                        "tool_name": "Read",
                        "tool_input": {},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            table = app.query_one("#queue", DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertIn("s1", str(app.query_one("#session-line", Static).content))


class TestReviewAggregation(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec23.1 (STORY-1801): repeated, byte-for-byte
    identical block events collapse into one ReviewEntry with a stable id,
    instead of one row per occurrence."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block_with_url(self, tool_name: str, url: str) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": tool_name,
                        "tool_input": {"url": url},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

    async def test_identical_repeated_calls_aggregate_into_one_entry(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 1)
            self.assertEqual(app._pending_reviews[0].count, 2)
            self.assertEqual(app._pending_reviews[0].id, 1)

    async def test_a_distinct_call_gets_its_own_id_not_merged(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        self._append_block_with_url("WebFetch", "https://also-evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 2)
            self.assertEqual([e.count for e in app._pending_reviews], [1, 1])
            self.assertEqual({e.id for e in app._pending_reviews}, {1, 2})

    async def test_a_later_occurrence_of_the_same_call_is_not_a_separate_target_identity(self):
        # Same tool+input identified via a *different* wrapping Bash call is
        # deliberately NOT aggregated -- exact tool_name+tool_input match
        # only (sec23.1's rejected alternative: same identified target).
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": "curl https://evil.example.com/x"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 2)

    async def test_resolving_one_occurrence_leaves_the_others_pending_after_a_restart(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        first_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            entry = first_run._pending_reviews[0]
            self.assertEqual(entry.count, 2)
            first_offset = entry.events[0].log_offset

        # Simulate a restart with only the first occurrence ever resolved --
        # a real, interleaved review_resolved line, not an in-memory-only
        # removal.
        with self.audit_log.open("a") as f:
            f.write(json.dumps({"event": "review_resolved", "resolved_offset": first_offset}) + "\n")

        second_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(len(second_run._pending_reviews), 1)
            self.assertEqual(second_run._pending_reviews[0].count, 1)

    async def test_resolving_every_occurrence_removes_the_entry_after_a_restart(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        first_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            offsets = [e.log_offset for e in first_run._pending_reviews[0].events]

        with self.audit_log.open("a") as f:
            for offset in offsets:
                f.write(json.dumps({"event": "review_resolved", "resolved_offset": offset}) + "\n")

        second_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(second_run._pending_reviews, [])

    async def test_allowing_an_aggregated_entry_resolves_every_occurrence_not_just_the_latest(self):
        # STORY-1801's 4th AC: resolving an aggregate must mark *every*
        # underlying occurrence resolved, or a restart's replay would
        # resurrect whichever ones didn't get a marker.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        first_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            await _open_review(pilot, first_run)
            await pilot.click(first_run.screen.query_one("#deny-btn"))
            await pilot.pause()
            self.assertEqual(first_run._pending_reviews, [])

        second_run = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(second_run._pending_reviews, [])


class TestQueueDisplaySortAndMultiTargetRows(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec23.2/23.3 (STORY-1802/1803): most-recent-
    first display order and one row per identified target on a multi-
    target call."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block(self, tool_name: str, tool_input: dict, ts: float = 0.0) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "reason": "blocked",
                        "block_kind": "uncleared",
                        "ts": ts,
                    }
                )
                + "\n"
            )

    async def test_multi_target_call_renders_as_one_row_per_target(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("Bash", {"command": "curl https://first.example.com/x https://second.example.com/y"})

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test(size=(100, 50)) as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews[0].targets), 2)

            table = app.query_one("#queue", DataTable)
            self.assertEqual(table.row_count, 2)
            row0, row1 = table.get_row_at(0), table.get_row_at(1)
            # Same entry (ID, Tool, Reason, Count) on both rows.
            self.assertEqual(row0[0], row1[0])
            self.assertEqual(row0[1], row1[1])
            self.assertIn("(1 of 2)", row0[2])
            self.assertIn("(2 of 2)", row1[2])
            self.assertEqual(self._queue_rows_len(app), 2)

            # Either row opens the same underlying review.
            table.move_cursor(row=1)
            await pilot.press("enter")
            await pilot.pause()
            self.assertEqual(len(app.screen.query_one("#targets", DataTable).rows), 2)

    def _queue_rows_len(self, app) -> int:
        return len(app._queue_rows)

    async def test_zero_target_call_renders_a_dash_not_a_crash(self):
        # Trin's UAT (2026-08-07): no existing test covered the queue row
        # for a block with no identified targets at all (e.g. a Bash
        # command with nothing scanner-identifiable) -- refresh_queue()'s
        # `n == 0` branch was previously exercised only in monitor_data.py's
        # ReviewEntry-level tests, never through the real rendered table.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("Bash", {"command": "echo hi"})

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            table = app.query_one("#queue", DataTable)
            self.assertEqual(table.row_count, 1)
            row = table.get_row_at(0)
            self.assertEqual(row[2], "—")
            self.assertEqual(row[3], "—")

    async def test_queue_displays_most_recent_first(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://older.example.com/x"}, ts=1000.0)

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            self._append_block("WebFetch", {"url": "https://newer.example.com/x"}, ts=2000.0)
            app.poll_data()
            await pilot.pause()

            table = app.query_one("#queue", DataTable)
            self.assertEqual(table.row_count, 2)
            # Newer entry (higher id, appended later) renders first.
            self.assertEqual(table.get_row_at(0)[0], "2")
            self.assertEqual(table.get_row_at(1)[0], "1")
            # Storage order is untouched -- still append/FIFO order.
            self.assertEqual([e.id for e in app._pending_reviews], [1, 2])

    async def test_a_poll_tick_mid_review_does_not_change_the_open_reviews_entry(self):
        # sec23.2: the display sort is recomputed fresh every refresh_queue()
        # call, including from poll_data()'s own 0.5s timer while a
        # ReviewScreen is open -- the open screen's entry/index must not
        # silently change out from under the operator.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://original.example.com/x"}, ts=1000.0)

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            review_screen = app.screen
            original_entry = review_screen._entry
            self.assertEqual(original_entry.targets[0].identity, "https://original.example.com/x")

            # A brand-new, more-recent block arrives while the review is
            # open -- sorts ahead of the original entry on display (higher
            # ts), confirming this isn't a coincidental pass.
            self._append_block("WebFetch", {"url": "https://newer.example.com/x"}, ts=2000.0)
            app.poll_data()
            await pilot.pause()

            self.assertIs(app.screen, review_screen)
            self.assertIs(review_screen._entry, original_entry)
            self.assertEqual(review_screen._entry.targets[0].identity, "https://original.example.com/x")


class TestSkipAndSkipAll(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec23.4 (STORY-1804): dequeue without writing a
    rule or touching the scan cache; skip-all requires 2 consecutive "S"
    presses, any other key in between cancels it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block(self, tool_name: str, tool_input: dict) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": tool_name,
                        "tool_input": tool_input,
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

    def _make_app(self) -> MonitorApp:
        return MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )

    async def test_skip_selected_dequeues_the_row_under_the_cursor(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})

        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            table = app.query_one("#queue", DataTable)
            table.move_cursor(row=0)
            await pilot.press("s")
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])
            self.assertEqual(table.row_count, 0)

    async def test_skip_writes_no_rule_and_touches_no_scan_cache(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})

        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            table = app.query_one("#queue", DataTable)
            table.move_cursor(row=0)
            await pilot.press("s")
            await pilot.pause()

            self.assertFalse(self.policy_path.exists())
            self.assertFalse(self.cache_path.exists())

    async def test_a_single_s_press_alone_does_not_skip_anything(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})

        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await pilot.press("S")
            await pilot.pause()

            self.assertEqual(len(app._pending_reviews), 1)
            self.assertIn("Press S again", str(app.query_one("#queue-status", Static).content))

    async def test_two_consecutive_s_presses_skip_everything(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://first.example.com/x"})
        self._append_block("WebFetch", {"url": "https://second.example.com/x"})

        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await pilot.press("S")
            await pilot.press("S")
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])
            self.assertIn("Skipped 2 reviews", str(app.query_one("#queue-status", Static).content))

    async def test_any_other_key_between_the_two_s_presses_cancels_it(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})

        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await pilot.press("S")
            await pilot.press("x")
            await pilot.press("S")
            await pilot.pause()

            # The 2nd "S" re-armed (cancel reset it) rather than executing --
            # still 1 pending, and the status shows the re-arm prompt again.
            self.assertEqual(len(app._pending_reviews), 1)
            self.assertIn("Press S again", str(app.query_one("#queue-status", Static).content))

    async def test_pressing_s_all_with_an_empty_queue_is_a_no_op(self):
        _write_state(self.state_dir, "s1")
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.pause()
            await pilot.press("S")
            await pilot.pause()
            self.assertEqual(str(app.query_one("#queue-status", Static).content), "")

    async def test_a_mouse_click_between_the_two_s_presses_cancels_it(self):
        # Trin's UAT finding: on_key alone can't see a mouse click -- opening
        # a review by clicking a row must cancel the arm too, the same as
        # any other keyboard interruption.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})

        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await pilot.press("S")
            await pilot.pause()
            self.assertTrue(app._skip_all_armed)

            # A bare click alone (no follow-up Enter keypress) already fires
            # RowSelected in Textual's DataTable -- isolates this from
            # on_key's own keyboard-based disarm path.
            await pilot.click("#queue", offset=(2, 1))
            await pilot.pause()

            self.assertFalse(app._skip_all_armed)
            self.assertEqual(str(app.query_one("#queue-status", Static).content), "")

    async def test_skipped_entry_does_not_reappear_after_a_restart(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})
        self._append_block("WebFetch", {"url": "https://evil.example.com/x"})

        first_run = self._make_app()
        async with first_run.run_test() as pilot:
            first_run.poll_data()
            await pilot.pause()
            self.assertEqual(first_run._pending_reviews[0].count, 2)
            first_run.query_one("#queue", DataTable).move_cursor(row=0)
            await pilot.press("s")
            await pilot.pause()
            self.assertEqual(first_run._pending_reviews, [])

        second_run = self._make_app()
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(second_run._pending_reviews, [])


class TestAllowFormEditableFieldsAndLayout(FastIsolatedAsyncioTestCase):
    """Direct user requests (2026-07-30): editable tool/pattern fields
    (defaulting to the exact tool name / exact-match pattern, widenable
    before submit), a fixed-value RadioSet grid for sensitivity/mode
    instead of free-text, and a compact layout where every allow-form
    field stays on-screen at a standard 80x24 terminal."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block_with_url(self, tool_name: str, url: str) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": tool_name,
                        "tool_input": {"url": url},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

    async def _open_allow_form(self, pilot, app):
        # docs/ARCHITECTURE.md sec22.4 (STORY-1704): the match-expr fields
        # are always visible now -- no reveal click needed, this just gets
        # to a verified review so #allow-btn is enabled for whichever test
        # wants to actually submit.
        app.poll_data()
        await pilot.pause()
        await _open_review(pilot, app)
        await pilot.click(app.screen.query_one("#verify-btn"))
        await pilot.pause()

    async def test_tool_field_defaults_to_the_exact_tool_name(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            self.assertEqual(app.screen.query_one("#rule-tool-input", Input).value, "WebFetch")

    async def test_pattern_field_defaults_to_exact_match_and_is_editable(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            self.assertFalse(pattern_input.disabled)
            self.assertEqual(pattern_input.value, r"https://evil\.example\.com/x")

            # Widen it (the actual point of making this editable) and
            # confirm the widened value, not the default, is what's written.
            pattern_input.value = r"https://evil\.example\.com/*"
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            written = self.policy_path.read_text()
            self.assertIn(r"https://evil\.example\.com/*", written)

    async def test_pattern_field_is_enabled_and_blank_by_default_for_a_multi_target_call(self):
        # 2026-07-30 (direct user follow-up): was disabled here originally
        # ("a single text field can't represent N distinct identities") --
        # corrected once it was clear a typed pattern should write one
        # shared rule for all targets instead, not attempt to represent
        # each target's own identity.
        _write_state(self.state_dir, "s1", trust="low")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": "curl https://a.example.com/x https://b.example.com/y"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            self.assertFalse(pattern_input.disabled)
            self.assertEqual(pattern_input.value, "")

    async def test_typed_pattern_writes_one_shared_rule_for_a_multi_target_call(self):
        # The actual point of no longer disabling pattern-input for a
        # multi-target call: typing a pattern writes ONE rule covering
        # every target, not the same pattern duplicated N times. Uses 2
        # real files under a shared directory (not URLs) so the real
        # scanner involved is FileScanner -- deterministic, no dependency
        # on a real network reputation lookup's outcome for a made-up host.
        _write_state(self.state_dir, "s1", trust="low")
        project_dir = Path(self._tmp.name) / "project"
        project_dir.mkdir()
        file_a = project_dir / "a.py"
        file_b = project_dir / "b.py"
        file_a.write_text("print('a')")
        file_b.write_text("print('b')")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": f"cat {file_a} {file_b}"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.value = f"{project_dir}\n{project_dir}/**"
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])
            self.assertTrue(self.policy_path.exists())
            written = self.policy_path.read_text()
            self.assertEqual(written.count("pattern:"), 1)
            self.assertIn(str(project_dir), written)

    async def test_allowing_one_review_auto_resolves_other_pending_reviews_it_now_covers(self):
        # Direct user request: a wildcard rule covering a whole project
        # folder should render other already-queued reviews for files
        # under that folder moot, not leave the operator to manually
        # Deny/dismiss each one individually. Per sec15.2, a rule only
        # counts once the cache confirms the resource clean -- both files
        # are pre-seeded with real, fresh cache entries here (standing in
        # for E10's automatic first-sight background scan) so this tests
        # "rule now matches + already validated", not a shortcut that
        # resolves anything a broad pattern merely touches.
        _write_state(self.state_dir, "s1", trust="low")
        project_dir = Path(self._tmp.name) / "project"
        project_dir.mkdir()
        file_a = project_dir / "a.py"
        file_b = project_dir / "b.py"
        file_a.write_text("print('a')")
        file_b.write_text("print('b')")

        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource, ScanResult

        cache = ScanCache(self.cache_path)
        cache.put(Resource(kind="file", identity=str(file_a), scanner_name="secrets"), ScanResult(label="public"))
        cache.put(Resource(kind="file", identity=str(file_b), scanner_name="secrets"), ScanResult(label="public"))

        with self.audit_log.open("a") as f:
            for target_file in (file_a, file_b):
                f.write(
                    json.dumps(
                        {
                            "event": "block",
                            "session_id": "s1",
                            "tool_name": "Read",
                            "tool_input": {"file_path": str(target_file)},
                            "reason": "blocked",
                            "block_kind": "uncleared",
                        }
                    )
                    + "\n"
                )

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            self.assertEqual(len(app._pending_reviews), 2)

            await _open_review(pilot, app)
            # Both targets already have fresh cache entries -- Allow is
            # already unlocked without needing an explicit Verify click.
            self.assertFalse(app.screen.query_one("#allow-btn").disabled)
            # Fields are always visible now (sec22.4) -- type the widened
            # pattern directly, no reveal click needed first.
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.value = f"{project_dir}\n{project_dir}/**"
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()

            # Not just the review actually Allowed -- the *other* file's
            # review, never explicitly touched, is gone too.
            self.assertEqual(app._pending_reviews, [])

        # And it stays gone across a restart (2026-07-30's persistence
        # fix) -- the auto-resolution wrote a real review_resolved marker,
        # not just an in-memory removal.
        second_run = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with second_run.run_test() as pilot:
            second_run.poll_data()
            await pilot.pause()
            self.assertEqual(second_run._pending_reviews, [])

    async def test_sensitivity_and_mode_default_to_public_and_allow(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            self.assertTrue(app.screen.query_one("#sensitivity-public", RadioButton).value)
            self.assertTrue(app.screen.query_one("#mode-allow", RadioButton).value)

    async def test_selecting_a_different_sensitivity_and_mode_is_what_gets_written(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            await pilot.click(app.screen.query_one("#sensitivity-restricted"))
            await pilot.click(app.screen.query_one("#mode-block"))
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            written = self.policy_path.read_text()
            self.assertIn("sensitivity: restricted", written)
            self.assertIn("mode: block", written)

    async def test_cannot_select_more_than_one_option_per_radio_set(self):
        # The whole reason RadioSet (not a checkbox group) is the right
        # widget: sensitivity/mode are each exactly one value.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            await pilot.click(app.screen.query_one("#sensitivity-restricted"))
            self.assertTrue(app.screen.query_one("#sensitivity-restricted", RadioButton).value)
            self.assertFalse(app.screen.query_one("#sensitivity-public", RadioButton).value)
            self.assertFalse(app.screen.query_one("#sensitivity-internal", RadioButton).value)

    async def test_enter_in_pattern_input_submits_without_clicking_submit(self):
        # Fewer clicks/steps (direct user request): Enter submits directly.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_allow_form(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            self.assertTrue(self.policy_path.exists())
            self.assertEqual(app._pending_reviews, [])

    async def test_opening_a_review_focuses_the_pattern_input(self):
        # docs/ARCHITECTURE.md sec22.4 (STORY-1704): with the match-expr
        # fields always visible now, there's no separate "reveal" click to
        # focus on -- the cursor lands on the field the operator is most
        # likely to edit as soon as the review screen opens instead.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            self.assertEqual(app.focused, app.screen.query_one("#rule-pattern-input"))

    async def test_allow_form_fields_all_stay_within_a_standard_80x24_screen(self):
        # Regression test for a real bug hit while building this feature:
        # an unconstrained empty Static/Input defaults to width 1fr (fill
        # remaining space), which silently pushed a sibling widget's x
        # coordinate past the right edge of the screen entirely --
        # Pilot.click() on it then raised OutOfBounds. This asserts every
        # allow-form widget's region stays inside the real screen size,
        # not just that clicking happens to still work today.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:  # default size: 80x24
            await self._open_allow_form(pilot, app)
            screen = app.screen
            for widget_id in (
                "prev-btn", "review-position", "next-btn",
                "rule-tool-input", "rule-pattern-input",
                "sensitivity-radio", "mode-radio",
                "allow-btn", "allow-error",
            ):
                region = screen.query_one(f"#{widget_id}").region
                self.assertLessEqual(
                    region.x + region.width, app.size.width, f"#{widget_id} extends past the right edge"
                )
                self.assertLessEqual(
                    region.y + region.height, app.size.height, f"#{widget_id} extends past the bottom edge"
                )

    async def test_allow_button_does_not_overlap_allow_error_with_multiple_targets(self):
        # Regression test for a real bug found while building this feature
        # (E16): #allow-form (a Vertical) had no explicit `height` and
        # silently defaulted to 1fr (a *share* of remaining screen space),
        # same class of bug as the width-1fr issue above -- a growing
        # #targets table shrank that share, silently compressing #allow-
        # form's content until #allow-error (the next sibling at the time)
        # overlapped the action button, swallowing clicks with no error.
        # sec22.4 (E17) moved #allow-form *before* #targets in compose(), so
        # the original trigger no longer applies the same way -- kept as a
        # defense-in-depth layout-health check, not because this exact
        # scenario is still reachable.
        _write_state(self.state_dir, "s1", trust="low")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": "curl https://a.example.com/x https://b.example.com/y"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:  # default size: 80x24
            await self._open_allow_form(pilot, app)
            allow_region = app.screen.query_one("#allow-btn").region
            error_region = app.screen.query_one("#allow-error").region
            overlaps = (
                allow_region.x < error_region.x + error_region.width
                and error_region.x < allow_region.x + allow_region.width
                and allow_region.y < error_region.y + error_region.height
                and error_region.y < allow_region.y + allow_region.height
            )
            self.assertFalse(
                overlaps, f"#allow-btn {allow_region} overlaps #allow-error {error_region} -- clicks would be swallowed"
            )

    async def test_sub_title_shows_the_resolved_policy_and_state_paths(self):
        # Direct user report: "monitor decisions not persisting across
        # sessions" traced to cwd-relative default paths -- showing the
        # resolved absolute paths makes a cwd mismatch between runs visible
        # instead of silently looking like state was forgotten.
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        self.assertIn(str(self.policy_path.resolve()), app.sub_title)
        self.assertIn(str(self.state_dir.resolve()), app.sub_title)


class TestPatternFieldUndoRedo(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec23.6 (STORY-1806): ctrl+z/ctrl+y undo/redo
    for the Tool/Pattern rule-editing fields -- confirmed Textual's own
    Input widget has no built-in undo."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block_with_url(self, tool_name: str, url: str) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": tool_name,
                        "tool_input": {"url": url},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

    async def _open_review_screen(self, pilot, app) -> None:
        app.poll_data()
        await pilot.pause()
        await _open_review(pilot, app)

    async def test_ctrl_z_with_no_input_focused_is_a_safe_no_op(self):
        # Trin's UAT: focus could be on a Button/RadioSet (neither is an
        # Input, neither is in _input_histories) -- must not crash.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            app.screen.query_one("#verify-btn").focus()
            await pilot.press("ctrl+z")
            await pilot.pause()
            # Nothing raised, and the untouched field's value is unaffected.
            self.assertEqual(app.screen.query_one("#rule-pattern-input", Input).value, r"https://evil\.example\.com/x")

    async def test_undo_restoring_the_pattern_field_recomputes_the_matches_column(self):
        # The Matches? column (STORY-1704) must stay live-consistent even
        # when the pattern field's value changes via undo, not just typing.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = "no-match-for-anything"
            await pilot.pause()
            targets_table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(targets_table.get_row_at(0)[4], "no")

            await pilot.press("ctrl+z")
            await pilot.pause()
            self.assertEqual(targets_table.get_row_at(0)[4], "yes")

    async def test_ctrl_z_undoes_the_last_edit_to_the_focused_field(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            default_value = pattern_input.value
            pattern_input.focus()

            pattern_input.value = "widened-once"
            await pilot.pause()
            pattern_input.value = "widened-twice"
            await pilot.pause()

            await pilot.press("ctrl+z")
            await pilot.pause()
            self.assertEqual(pattern_input.value, "widened-once")

            await pilot.press("ctrl+z")
            await pilot.pause()
            self.assertEqual(pattern_input.value, default_value)

            # At the floor -- one more undo is a no-op, not an error/crash.
            await pilot.press("ctrl+z")
            await pilot.pause()
            self.assertEqual(pattern_input.value, default_value)

    async def test_ctrl_y_redoes_after_an_undo(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()

            pattern_input.value = "widened"
            await pilot.pause()
            await pilot.press("ctrl+z")
            await pilot.pause()
            self.assertNotEqual(pattern_input.value, "widened")

            await pilot.press("ctrl+y")
            await pilot.pause()
            self.assertEqual(pattern_input.value, "widened")

    async def test_a_new_edit_after_undo_clears_the_redo_stack(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()

            pattern_input.value = "first-edit"
            await pilot.pause()
            await pilot.press("ctrl+z")
            await pilot.pause()

            pattern_input.value = "a-different-edit"
            await pilot.pause()
            await pilot.press("ctrl+y")
            await pilot.pause()
            # Nothing to redo into -- the new edit invalidated it, standard
            # undo/redo semantics.
            self.assertEqual(pattern_input.value, "a-different-edit")

    async def test_the_two_fields_have_independent_undo_history(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            tool_input = app.screen.query_one("#rule-tool-input", Input)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)

            pattern_input.value = "pattern-edit"
            await pilot.pause()
            tool_input.focus()
            tool_input.value = "ToolEdit"
            await pilot.pause()

            await pilot.press("ctrl+z")
            await pilot.pause()
            # Undo while the Tool field is focused only affects Tool --
            # the Pattern field's own edit is untouched.
            self.assertEqual(pattern_input.value, "pattern-edit")
            self.assertNotEqual(tool_input.value, "ToolEdit")

    async def test_switching_entries_resets_undo_history(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://first.example.com/x")
        self._append_block_with_url("WebFetch", "https://second.example.com/x")
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await self._open_review_screen(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = "edited-on-first-entry"
            await pilot.pause()

            await pilot.click(app.screen.query_one("#next-btn"))
            await pilot.pause()
            second_entry_default = app.screen.query_one("#rule-pattern-input", Input).value

            # Undo on the new entry must not reach back into the previous
            # entry's edit -- there is nothing to undo into but its own
            # freshly-seeded baseline.
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()
            await pilot.press("ctrl+z")
            await pilot.pause()
            self.assertEqual(pattern_input.value, second_entry_default)


class TestPatternWidenAndBreadcrumbs(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec23.x (direct user request, 2026-08-07):
    "hard to select text and type" a long path in the Pattern field --
    alt+w progressively widens it to a directory-level wildcard from the
    keyboard, and one clickable breadcrumb button per path segment does
    the same from the mouse, jumping straight to that level."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def _append_block_read(self, file_path: str) -> None:
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": file_path},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

    def _make_app(self) -> MonitorApp:
        return MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )

    async def test_breadcrumbs_render_one_button_per_path_segment(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/home/user/project/src/foo/bar.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            crumbs = app.screen.query_one("#pattern-breadcrumbs")
            labels = [str(b.label) for b in crumbs.query("Button")]
            # Path("/home/user/project/src/foo/bar.py").parts
            self.assertEqual(labels, ["/", "home", "user", "project", "src", "foo", "bar.py"])

    async def test_breadcrumbs_are_empty_for_a_multi_target_call(self):
        _write_state(self.state_dir, "s1", trust="low")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": "curl https://first.example.com/x https://second.example.com/x"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )
        app = self._make_app()
        async with app.run_test(size=(100, 50)) as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            crumbs = app.screen.query_one("#pattern-breadcrumbs")
            self.assertEqual(len(crumbs.query("Button")), 0)

    async def test_clicking_a_breadcrumb_widens_the_pattern_to_that_level(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/home/user/project/src/foo/bar.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            await pilot.click("#breadcrumb-4")  # "src" -- keep through src/, wildcard the rest
            await pilot.pause()

            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            self.assertEqual(pattern_input.value, escape_gitignore_literal("/home/user/project/src") + "/**")

    async def test_clicking_the_final_segment_resets_to_the_exact_literal_pattern(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/home/user/project/src/foo/bar.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            await pilot.click("#breadcrumb-4")
            await pilot.pause()
            await pilot.click("#breadcrumb-6")  # "bar.py" -- back to exact match
            await pilot.pause()

            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            self.assertEqual(pattern_input.value, escape_gitignore_literal("/home/user/project/src/foo/bar.py"))

    async def test_alt_w_progressively_widens_the_pattern(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/home/user/project/src/foo/bar.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            default_value = pattern_input.value

            await pilot.press("alt+w")
            await pilot.pause()
            self.assertEqual(pattern_input.value, escape_gitignore_literal("/home/user/project/src/foo") + "/**")
            self.assertNotEqual(pattern_input.value, default_value)

            await pilot.press("alt+w")
            await pilot.pause()
            self.assertEqual(pattern_input.value, escape_gitignore_literal("/home/user/project/src") + "/**")

    async def test_alt_w_stops_widening_at_the_root_boundary(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/a/b.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)

            for _ in range(10):  # far more presses than there are segments
                await pilot.press("alt+w")
                await pilot.pause()

            self.assertEqual(pattern_input.value, escape_gitignore_literal("/") + "/**")

    async def test_widened_pattern_still_matches_the_target_live(self):
        # The Matches? column (STORY-1704) must reflect the widened
        # pattern too -- proves the produced gitignore pattern is actually
        # a valid, matching rule, not just cosmetically plausible text.
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/home/user/project/src/foo/bar.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            await pilot.press("alt+w")
            await pilot.pause()

            targets_table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(targets_table.get_row_at(0)[4], "yes")

    async def test_breadcrumbs_reset_when_switching_entries(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_read("/home/user/first/a.py")
        self._append_block_read("/home/user/second/deep/path/b.py")
        app = self._make_app()
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            await pilot.click(app.screen.query_one("#next-btn"))
            await pilot.pause()

            crumbs = app.screen.query_one("#pattern-breadcrumbs")
            labels = [str(b.label) for b in crumbs.query("Button")]
            self.assertEqual(labels, ["/", "home", "user", "second", "deep", "path", "b.py"])
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            self.assertEqual(pattern_input.value, escape_gitignore_literal("/home/user/second/deep/path/b.py"))


class TestLiveMatchPreview(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec22.4 (STORY-1704): the "Matches?" column,
    recomputed live as the Pattern field is edited -- before any Allow
    submit, using the same `Scanner.match()` dispatch the real write path
    relies on."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_matches_column_recomputes_live_as_the_pattern_field_is_edited(self):
        _write_state(self.state_dir, "s1", trust="low")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Bash",
                        "tool_input": {"command": "curl https://covered.example.com/x https://other.example.net/y"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            table = app.screen.query_one("#targets", DataTable)
            # Blank pattern (auto per-target derivation): each target's own
            # exact-match default always matches itself.
            self.assertEqual(table.get_row_at(0)[4], "yes")
            self.assertEqual(table.get_row_at(1)[4], "yes")

            # A shared pattern covering only the .example.com host --
            # matches the first target, not the second (real payoff of
            # this feature: see coverage *before* submitting, not after).
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.value = r"https://.*\.example\.com/.*"
            await pilot.pause()
            self.assertEqual(table.get_row_at(0)[4], "yes")
            self.assertEqual(table.get_row_at(1)[4], "no")

    async def test_invalid_tool_regex_mid_edit_shows_indeterminate_not_no(self):
        # An in-progress edit that isn't a valid rule yet is a different
        # claim than "this valid rule doesn't match" -- collapsing them
        # would misinform the operator (sec22.4).
        _write_state(self.state_dir, "s1", trust="low")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": "/tmp/x.md"},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            self.assertEqual(app.screen.query_one("#targets", DataTable).get_row_at(0)[4], "yes")

            # Trigger via the Pattern field's on_input_changed, same as a
            # real edit would -- an unbalanced "(" is not a valid regex.
            tool_input = app.screen.query_one("#rule-tool-input", Input)
            tool_input.value = "("
            app.screen.query_one("#rule-pattern-input", Input).value += " "  # force refresh_targets to re-run
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#targets", DataTable).get_row_at(0)[4], "—")

    async def test_pattern_field_does_not_bypass_verify_gate_via_enter(self):
        # Smith's Gate 2 finding (docs/ARCHITECTURE.md sec22.4 correction):
        # promoting the Pattern field to always-visible/focusable removed
        # the thing that used to enforce "Allow requires Verify first" (the
        # old hidden-until-Allow-clicked form). Confirms the fix holds
        # against the real bypass path -- Enter in the field, never
        # clicking Verify at all.
        import re

        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "never_verified.md"
        target_path.write_text("could be anything")
        with self.audit_log.open("a") as f:
            f.write(
                json.dumps(
                    {
                        "event": "block",
                        "session_id": "s1",
                        "tool_name": "Read",
                        "tool_input": {"file_path": str(target_path)},
                        "reason": "blocked",
                        "block_kind": "uncleared",
                    }
                )
                + "\n"
            )

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await _open_review(pilot, app)

            # Never click #verify-btn. Type a pattern and press Enter --
            # the real path a habitual user would hit first, not a
            # contrived direct method call.
            self.assertTrue(app.screen.query_one("#allow-btn").disabled)
            pattern_input = app.screen.query_one("#rule-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = re.escape(str(target_path))
            await pilot.press("enter")
            await pilot.pause()

            self.assertFalse(self.policy_path.exists())
            self.assertIn("Verify", app.screen.query_one("#allow-error", Static).content)
            self.assertEqual(len(app._pending_reviews), 1)  # still queued, screen never dismissed


class TestRulesScreen(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec22.5 (STORY-1705): the Rules screen -- list
    + reorder, reachable from the queue via 'r' (freed from the old
    'r'-opens-oldest-review binding, sec22.1)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_rules(self, rules: list[dict]) -> None:
        import yaml

        self.policy_path.write_text(yaml.safe_dump({"rules": rules}, sort_keys=False, default_flow_style=False))

    async def test_no_rules_configured_shows_an_explicit_message(self):
        # Trin's UAT (E17 Phase 4): an empty table with no explanation reads
        # as "broken" -- same Nielsen #1 standard as #no-queue (Phase 1).
        # No policy file at all here, the common brand-new-project case.
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            self.assertIn("visible", app.screen.query_one("#no-rules").classes)
            self.assertEqual(app.screen.query_one("#rules", DataTable).row_count, 0)

            # Adversarial: pressing move keys against an empty table must
            # not crash (real edge case, not "shouldn't happen so skip it").
            await pilot.press("k")
            await pilot.press("j")
            await pilot.pause()

            # Smith's Gate (sec23.7): 'e'/'d' against an empty table must
            # not crash either, same standard as k/j above.
            await pilot.press("e")
            await pilot.press("d")
            await pilot.press("d")
            await pilot.pause()
            self.assertIsInstance(app.screen, RulesScreen)

    async def test_a_single_rule_cannot_move_up_or_down(self):
        # Adversarial boundary case: with exactly 1 rule, both directions
        # are simultaneously the top and bottom boundary.
        self._write_rules([{"tool": ".*", "pattern": "only", "sensitivity": "public", "mode": "allow"}])
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            table.move_cursor(row=0)
            await pilot.press("k")
            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(table.get_row_at(0)[2], "only")
            self.assertEqual(app.screen.query_one("#rule-confirm", Static).content, "")  # no write attempted

    async def test_r_opens_the_rules_screen_listing_real_rules_in_order(self):
        self._write_rules(
            [
                {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                {"tool": "Bash", "pattern": "b", "sensitivity": "restricted", "mode": "block"},
            ]
        )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            self.assertEqual(table.row_count, 2)
            self.assertEqual(table.get_row_at(0), ["1", ".*", "a", "public", "allow", "high"])
            self.assertEqual(table.get_row_at(1), ["2", "Bash", "b", "restricted", "block", "high"])

    async def test_escape_returns_to_the_queue_screen(self):
        self._write_rules([{"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"}])
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            self.assertEqual(len(app.screen.query("#rules")), 0)
            self.assertEqual(len(app.screen.query("#queue")), 1)

    async def test_j_moves_the_selected_rule_down_and_confirms_synchronously(self):
        self._write_rules(
            [
                {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
            ]
        )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            table.move_cursor(row=0)
            await pilot.press("j")
            await pilot.pause()

            self.assertEqual(table.get_row_at(0)[2], "b")
            self.assertEqual(table.get_row_at(1)[2], "a")
            self.assertIn("Moved rule #1", str(app.screen.query_one("#rule-confirm", Static).content))
            # Real file, not just the in-memory table.
            import yaml

            written = yaml.safe_load(self.policy_path.read_text())
            self.assertEqual([r["pattern"] for r in written["rules"]], ["b", "a"])

    async def test_k_moves_the_selected_rule_up(self):
        self._write_rules(
            [
                {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
            ]
        )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            table.move_cursor(row=1)
            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(table.get_row_at(0)[2], "b")
            self.assertEqual(table.get_row_at(1)[2], "a")

    async def test_cannot_move_the_first_rule_up_or_the_last_rule_down(self):
        # Boundary no-op -- same disposition as ReviewScreen's disabled
        # Prev/Next at the ends of the queue, just via a bound key instead
        # of a disabled button (this screen has no buttons).
        self._write_rules(
            [
                {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
            ]
        )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)

            table.move_cursor(row=0)
            await pilot.press("k")
            await pilot.pause()
            self.assertEqual(table.get_row_at(0)[2], "a")  # unchanged

            table.move_cursor(row=1)
            await pilot.press("j")
            await pilot.pause()
            self.assertEqual(table.get_row_at(1)[2], "b")  # unchanged

    async def test_reordering_via_the_real_screen_changes_which_rule_a_real_hook_call_resolves_with(self):
        # STORY-1705's hard end-to-end AC: reorder via this screen, then
        # confirm a real pre_tool_use call now resolves per the new order.
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig as PC

        target = str(Path(self._tmp.name) / "secret.env")
        Path(target).write_text("nothing")
        self._write_rules(
            [
                {"tool": ".*", "pattern": target, "sensitivity": "public", "mode": "allow"},
                {"tool": ".*", "pattern": target, "sensitivity": "restricted", "mode": "block"},
            ]
        )
        hook_input = {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": target}}

        before = pre_tool_use(
            hook_input, PC.from_yaml(self.policy_path), state_dir=self.state_dir, cache_path=self.cache_path, audit_log_path=self.audit_log
        )
        self.assertEqual(before["hookSpecificOutput"]["permissionDecision"], "allow")

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            table.move_cursor(row=0)
            await pilot.press("j")
            await pilot.pause()

        after = pre_tool_use(
            hook_input, PC.from_yaml(self.policy_path), state_dir=self.state_dir, cache_path=self.cache_path, audit_log_path=self.audit_log
        )
        self.assertEqual(after["hookSpecificOutput"]["permissionDecision"], "deny")


class TestRulesScreenEditAndDelete(FastIsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec23.7 (STORY-1807/1808): edit ('e') and
    delete ('d') actions on the Rules screen. `policy_config.update_rule`/
    `delete_rule` themselves are unit-tested directly in
    test_policy_config.py (test pyramid) -- these integration tests cover
    only what needs the real running screen: keybinding wiring, focus/
    typing interaction, and the armed/confirm delete flow."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    def _write_rules(self, rules: list[dict]) -> None:
        import yaml

        self.policy_path.write_text(yaml.safe_dump({"rules": rules}, sort_keys=False, default_flow_style=False))

    def _make_app(self) -> MonitorApp:
        return MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )

    async def test_e_opens_the_edit_form_prefilled_with_the_real_rule_values(self):
        self._write_rules(
            [{"tool": "Bash", "pattern": "a", "sensitivity": "restricted", "mode": "block", "trust": "low", "description": "real"}]
        )
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            self.assertIn("visible", app.screen.query_one("#edit-form").classes)
            self.assertEqual(app.screen.query_one("#edit-tool-input", Input).value, "Bash")
            self.assertEqual(app.screen.query_one("#edit-pattern-input", Input).value, "a")
            self.assertEqual(app.screen.query_one("#edit-description-input", Input).value, "real")

    async def test_editing_an_internal_sensitivity_rule_does_not_silently_downgrade_it_to_public(self):
        # Trin's UAT finding (2026-08-08): the Sensitivity/Trust RadioSets
        # were narrowed to 2 pickable values (_LABELING_SENSITIVITIES/
        # _LABELING_TRUST_LEVELS) as part of sec15.2b's UX follow-on, but a
        # real rule can still hold "internal"/"med" -- STORY-1504's own
        # project-folder default rule writes sensitivity="internal". Since
        # _set_radio_value() no-ops when the stored value isn't in the
        # shown tuple, opening this rule for edit leaves the Sensitivity
        # radio with *nothing* selected -- and saving without touching that
        # field then falls through to _get_radio_value()'s "public" default,
        # silently overwriting "internal" with "public" even though the
        # user only meant to change the pattern. Real, not hypothetical:
        # this is exactly STORY-1504's own rule shape.
        self._write_rules(
            [{"tool": ".*", "pattern": "/project/**", "sensitivity": "internal", "mode": "allow", "trust": "med"}]
        )
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            pattern_input = app.screen.query_one("#edit-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = "/project/**"  # touched, but unchanged -- same as a no-op edit
            await pilot.press("enter")
            await pilot.pause()

            import yaml

            saved = yaml.safe_load(self.policy_path.read_text())["rules"][0]
            self.assertEqual(saved["sensitivity"], "internal")
            self.assertEqual(saved["trust"], "med")

    async def test_saving_an_edit_writes_the_real_file_and_shows_confirmation(self):
        self._write_rules([{"tool": ".*", "pattern": "old", "sensitivity": "public", "mode": "allow"}])
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            pattern_input = app.screen.query_one("#edit-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = "new-pattern"
            await pilot.press("enter")
            await pilot.pause()

            self.assertNotIn("visible", app.screen.query_one("#edit-form").classes)
            self.assertIn("Saved rule #1", str(app.screen.query_one("#rule-confirm", Static).content))
            self.assertEqual(app.screen.query_one("#rules", DataTable).get_row_at(0)[2], "new-pattern")

            import yaml

            self.assertEqual(yaml.safe_load(self.policy_path.read_text())["rules"][0]["pattern"], "new-pattern")

    async def test_escape_while_editing_closes_the_form_without_writing(self):
        self._write_rules([{"tool": ".*", "pattern": "untouched", "sensitivity": "public", "mode": "allow"}])
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            pattern_input = app.screen.query_one("#edit-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = "would-have-changed"
            await pilot.press("escape")
            await pilot.pause()

            # First Escape closes the form, not the whole screen.
            self.assertNotIn("visible", app.screen.query_one("#edit-form").classes)
            self.assertIsInstance(app.screen, RulesScreen)
            import yaml

            self.assertEqual(yaml.safe_load(self.policy_path.read_text())["rules"][0]["pattern"], "untouched")

    async def test_an_invalid_edit_shows_an_error_and_does_not_write(self):
        self._write_rules([{"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"}])
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            tool_input = app.screen.query_one("#edit-tool-input", Input)
            tool_input.focus()
            tool_input.value = "["  # invalid regex
            await pilot.press("enter")
            await pilot.pause()

            self.assertNotEqual(str(app.screen.query_one("#edit-error", Static).content), "")
            self.assertIn("visible", app.screen.query_one("#edit-form").classes)  # still open
            import yaml

            self.assertEqual(yaml.safe_load(self.policy_path.read_text())["rules"][0]["tool"], ".*")

    async def test_typing_letters_that_are_also_binding_keys_types_them_instead_of_triggering_the_binding(self):
        # Real risk this screen didn't have before adding Input fields:
        # 'e'/'d'/'k'/'j' are all single-letter bindings here -- typing a
        # pattern containing them (e.g. "database") must type the letters,
        # not fire edit/delete/move while the field has focus.
        self._write_rules([{"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"}])
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            pattern_input = app.screen.query_one("#edit-pattern-input", Input)
            pattern_input.focus()
            pattern_input.value = ""
            await pilot.press("d", "a", "t", "a", "b", "a", "s", "e")
            await pilot.pause()

            self.assertEqual(pattern_input.value, "database")
            # Still just the one open form, no rule deleted/re-edited.
            self.assertIn("visible", app.screen.query_one("#edit-form").classes)
            self.assertEqual(app.screen.query_one("#rules", DataTable).row_count, 1)

    async def test_delete_requires_two_consecutive_d_presses_on_the_same_row(self):
        self._write_rules(
            [
                {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
            ]
        )
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            table.move_cursor(row=0)
            await pilot.press("d")
            await pilot.pause()
            self.assertEqual(table.row_count, 2)  # first press only arms
            self.assertIn("Press d again", str(app.screen.query_one("#rule-confirm", Static).content))

            await pilot.press("d")
            await pilot.pause()
            self.assertEqual(table.row_count, 1)
            self.assertEqual(table.get_row_at(0)[2], "b")
            self.assertIn("Deleted rule #1", str(app.screen.query_one("#rule-confirm", Static).content))

    async def test_navigating_between_the_two_d_presses_cancels_delete(self):
        self._write_rules(
            [
                {"tool": ".*", "pattern": "a", "sensitivity": "public", "mode": "allow"},
                {"tool": ".*", "pattern": "b", "sensitivity": "public", "mode": "allow"},
            ]
        )
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            table = app.screen.query_one("#rules", DataTable)
            table.move_cursor(row=0)
            await pilot.press("d")
            await pilot.pause()

            table.move_cursor(row=1)
            await pilot.pause()
            await pilot.press("d")
            await pilot.pause()

            # Cursor-move disarmed the first arm -- this "d" re-arms on row
            # 1 instead of deleting row 0.
            self.assertEqual(table.row_count, 2)
            self.assertIn("Press d again", str(app.screen.query_one("#rule-confirm", Static).content))

    async def test_sensitivity_and_trust_fields_hide_for_block_mode_and_show_for_allow(self):
        # 2026-08-07 (direct user request): Sensitivity/Trust are labeling-
        # rule fields, only relevant when Mode=allow -- decide_access()
        # skips tagging entirely for block/mask. This is real reactive UI
        # behavior (a RadioSet.Changed handler toggling another widget's
        # visibility) that only a running screen can verify -- not reachable
        # from a unit test the way policy_config.py's own validation is.
        self._write_rules([{"tool": ".*", "pattern": "a", "sensitivity": "restricted", "mode": "block", "trust": "low"}])
        app = self._make_app()
        async with app.run_test() as pilot:
            await pilot.press("r")
            await pilot.pause()
            app.screen.query_one("#rules", DataTable).move_cursor(row=0)
            await pilot.press("e")
            await pilot.pause()

            # Opened on a mode=block rule -- fields start hidden.
            self.assertIn("hidden", app.screen.query_one("#edit-sensitivity-field").classes)
            self.assertIn("hidden", app.screen.query_one("#edit-trust-field").classes)

            await pilot.click(app.screen.query_one("#edit-mode-allow"))
            await pilot.pause()

            self.assertNotIn("hidden", app.screen.query_one("#edit-sensitivity-field").classes)
            self.assertNotIn("hidden", app.screen.query_one("#edit-trust-field").classes)

            await pilot.click(app.screen.query_one("#edit-mode-block"))
            await pilot.pause()

            self.assertIn("hidden", app.screen.query_one("#edit-sensitivity-field").classes)
            self.assertIn("hidden", app.screen.query_one("#edit-trust-field").classes)


if __name__ == "__main__":
    unittest.main()
