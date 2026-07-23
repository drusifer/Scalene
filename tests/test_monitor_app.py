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

from textual.widgets import DataTable, Input, Static

from scalene.monitor_app import MonitorApp, _NO_SESSIONS_MESSAGE, _event_tag, _format_relative_time
from scalene.monitor_data import ToolCallEvent


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


class TestEventTag(unittest.TestCase):
    """docs/ARCHITECTURE.md sec20.3 (STORY-1603): every row's tag must carry
    its meaning in plain text -- color is a secondary cue, checked
    separately by TestMonitorApp's real-rendered/color-stripped test below,
    not the only signal here."""

    def test_allow_event_is_tagged_allow(self):
        tag = _event_tag(ToolCallEvent(session_id="s1", tool_name="Bash", reason="", event="allow", block_kind=None))
        self.assertEqual(str(tag), "[ALLOW]")

    def test_confirmed_bad_block_is_tagged_deny(self):
        tag = _event_tag(
            ToolCallEvent(session_id="s1", tool_name="Bash", reason="x", event="block", block_kind="confirmed_bad")
        )
        self.assertEqual(str(tag), "[DENY]")

    def test_uncleared_block_is_tagged_wait(self):
        tag = _event_tag(
            ToolCallEvent(session_id="s1", tool_name="Bash", reason="x", event="block", block_kind="uncleared")
        )
        self.assertEqual(str(tag), "[WAIT]")

    def test_old_format_block_with_no_block_kind_gets_a_generic_tag_not_a_crash(self):
        tag = _event_tag(ToolCallEvent(session_id="s1", tool_name="Bash", reason="x", event="block", block_kind=None))
        self.assertEqual(str(tag), "[BLOCK]")

    def test_allow_and_deny_and_wait_tags_are_all_textually_distinct(self):
        # The whole point of a text/symbol tag: distinguishable without
        # relying on the (separately-applied) color at all.
        tags = {
            str(_event_tag(ToolCallEvent(session_id="s1", tool_name="Bash", reason="", event="allow", block_kind=None))),
            str(
                _event_tag(
                    ToolCallEvent(session_id="s1", tool_name="Bash", reason="x", event="block", block_kind="confirmed_bad")
                )
            ),
            str(
                _event_tag(
                    ToolCallEvent(session_id="s1", tool_name="Bash", reason="x", event="block", block_kind="uncleared")
                )
            ),
        }
        self.assertEqual(len(tags), 3)


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
            self.assertEqual(row[0], "s1")
            self.assertEqual(row[1], "Bash")
            self.assertEqual(row[3], "no validated, explicitly-allowed rule")

    async def test_event_tags_are_legible_in_a_real_render_with_color_stripped(self):
        # docs/ARCHITECTURE.md sec20.3 (STORY-1603), mandatory Smith gate
        # per task.md Phase 2: a real rendered screenshot, not a stored-
        # cell-value check -- Oracle's 2026-07-15 lesson ("a row-content
        # check is not a rendering check") applies here exactly as it did
        # to the Last-Scanned truncation bug. `<text>` node innerText in the
        # exported SVG carries no color/fill information at all, so
        # confirming the tag strings appear in that extracted text *is* the
        # color-stripped check -- if a tag depended on color alone to convey
        # meaning, its distinguishing content wouldn't show up here.
        import re

        _write_state(self.state_dir, "s1", trust="low")
        _append_allow_event(self.audit_log, "s1", tool_name="Read")
        _append_block_event(self.audit_log, "s1", tool_name="WebFetch", block_kind="confirmed_bad")
        _append_block_event(self.audit_log, "s1", tool_name="Bash", block_kind="uncleared")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test(size=(120, 30)) as pilot:
            app.poll_data()
            await pilot.pause()
            svg = app.export_screenshot()
            rendered_text = " ".join(re.findall(r"<text[^>]*>([^<]*)</text>", svg))
            rendered_text = rendered_text.replace("&#160;", " ")

            self.assertIn("[ALLOW]", rendered_text)
            self.assertIn("[DENY]", rendered_text)
            self.assertIn("[WAIT]", rendered_text)

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


class TestReviewQueueAndDashboard(unittest.IsolatedAsyncioTestCase):
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

            await pilot.press("r")
            await pilot.pause()
            await pilot.click(app.screen.query_one("#deny-btn"))
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(app.title, "scg monitor")

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

    async def test_review_screen_shows_the_real_tool_call_and_target_status(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

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
            await pilot.press("r")
            await pilot.pause()

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

    async def test_allow_button_is_disabled_until_verify_completes(self):
        _write_state(self.state_dir, "s1", trust="low")
        self._append_block_with_url("WebFetch", "https://evil.example.com/x")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            await pilot.press("r")
            await pilot.pause()

            allow_button = app.screen.query_one("#allow-btn")
            self.assertTrue(allow_button.disabled)

            verify_button = app.screen.query_one("#verify-btn")
            await pilot.click(verify_button)
            await pilot.pause()

            self.assertFalse(allow_button.disabled)

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

            await pilot.press("r")
            await pilot.pause()
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
            await pilot.press("r")
            await pilot.pause()
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
            await pilot.press("r")
            await pilot.pause()

            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            await pilot.click(app.screen.query_one("#allow-btn"))
            # Revealing #allow-form (display = True) needs a layout/
            # compositor refresh before the newly-visible #submit-btn is at
            # a real, clickable screen region -- one pause settles the
            # reveal itself, a second is needed before clicking into it.
            await pilot.pause()
            await pilot.pause()
            await pilot.click(app.screen.query_one("#submit-btn"))
            # Screen.dismiss()'s result callback is scheduled via
            # requester.call_next(), not invoked synchronously (Textual's
            # own screen.py: ResultCallback.__call__) -- one more pause is
            # needed for it to actually run, not just for the click's own
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
            await pilot.press("r")
            await pilot.pause()

            # Verify will run the real URLScanner/reputation check against a
            # made-up hostname -- not guaranteed bad, so seed a real bad
            # cache entry directly the way a genuine scan finding would.
            from scalene.scan_cache import ScanCache
            from scalene.scanner import Resource, ScanResult

            ScanCache(self.cache_path).put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="known bad reputation"),
            )
            app.screen._entry.verified["https://evil.example.com/x"] = True
            app.screen.refresh_targets()

            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()
            await pilot.click(app.screen.query_one("#submit-btn"))  # mode defaults to "allow"
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
            await pilot.press("r")
            await pilot.pause()

            from scalene.scan_cache import ScanCache
            from scalene.scanner import Resource, ScanResult

            ScanCache(self.cache_path).put(
                Resource(kind="url", identity="https://evil.example.com/x", scanner_name="reputation"),
                ScanResult(label="untrusted", reason="known bad reputation"),
            )
            app.screen._entry.verified["https://evil.example.com/x"] = True
            app.screen.refresh_targets()

            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()
            mode_input = app.screen.query_one("#mode-input", Input)
            mode_input.value = "block"
            await pilot.click(app.screen.query_one("#submit-btn"))
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

            await pilot.press("r")
            await pilot.pause()
            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()
            await pilot.click(app.screen.query_one("#submit-btn"))
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


class TestMonitorAppScannerActivityPanel(unittest.IsolatedAsyncioTestCase):
    """docs/ARCHITECTURE.md sec20.2 (STORY-1602): one row per configured
    scanner, real ScanCache.pending_since reservations drive busy/idle."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_default_config_shows_the_two_builtin_scanners_idle(self):
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test():
            table = app.query_one("#scanners", DataTable)
            names = {table.get_row_at(i)[0] for i in range(table.row_count)}
            statuses = {table.get_row_at(i)[0]: table.get_row_at(i)[1] for i in range(table.row_count)}
            self.assertEqual(names, {"secrets", "reputation"})
            self.assertEqual(set(statuses.values()), {"idle"})

    async def test_a_config_declared_scanner_appears_with_no_monitor_code_change(self):
        # Same fixture as test_policy_config.py's config-driven-registry
        # coverage (E15/STORY-1501) -- proves the panel reflects whatever
        # PolicyConfig.scanners really is, not a hardcoded pair.
        import sys

        sys.path.insert(0, str(Path(__file__).parent))
        policy_path = Path(self._tmp.name) / "scalene_policy.yaml"
        policy_path.write_text(
            "scanners:\n  extra:\n    - name: dummy\n      import: \"fixtures_custom_scanner:DummyScanner\"\n"
        )
        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=policy_path
        )
        async with app.run_test():
            table = app.query_one("#scanners", DataTable)
            names = {table.get_row_at(i)[0] for i in range(table.row_count)}
            self.assertIn("dummy", names)

    async def test_a_real_pending_reservation_shows_the_scanner_as_busy(self):
        from scalene.scan_cache import ScanCache
        from scalene.scanner import Resource

        ScanCache(self.cache_path).try_reserve(
            Resource(kind="url", identity="never-finished.example.com", scanner_name="reputation")
        )
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()
            table = app.query_one("#scanners", DataTable)
            statuses = {table.get_row_at(i)[0]: table.get_row_at(i)[1] for i in range(table.row_count)}
            self.assertEqual(statuses["reputation"], "busy")
            self.assertEqual(statuses["secrets"], "idle")


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


class TestE16EndToEndUserJourney(unittest.IsolatedAsyncioTestCase):
    """Smith's sprint-close end-to-end test (`*user test E16`) — the full
    epic exercised as one continuous real scenario through the actual
    scg monitor TUI + the real pre_tool_use hook, not per-phase in
    isolation. Same standard as TestE14/E15EndToEndUserJourney: real
    binaries/functions throughout, nothing mocked."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"
        self.cache_path = Path(self._tmp.name) / "scan_cache.json"
        self.policy_path = Path(self._tmp.name) / "scalene_policy.yaml"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_full_journey_block_to_dashboard_to_allow_to_retry_succeeds(self):
        from scalene.hook_adapter import pre_tool_use
        from scalene.policy_config import PolicyConfig

        # A clean session's first unrecognized resource is allowed
        # (fail-safe, taints trust to low) -- a real block needs an
        # already-tainted session, same setup every other real-hook test
        # in this file uses.
        _write_state(self.state_dir, "s1", trust="low")
        target_path = Path(self._tmp.name) / "clean.md"
        target_path.write_text("nothing sensitive here")
        hook_input = {"session_id": "s1", "tool_name": "Read", "tool_input": {"file_path": str(target_path)}}

        # STORY-1601: a real blocked call carries differentiated retry
        # guidance in its systemMessage/reason, not just a bare denial.
        first = pre_tool_use(
            hook_input,
            PolicyConfig(),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(first["hookSpecificOutput"]["permissionDecision"], "deny")
        reason = first["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("wait", reason.lower())
        self.assertIn("retry", reason.lower())

        app = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app.run_test(size=(120, 50)) as pilot:
            app.poll_data()
            await pilot.pause()

            # STORY-1602: the real 2 builtin scanners show up, idle (no
            # scan in flight yet).
            scanners_table = app.query_one("#scanners", DataTable)
            scanner_names = {scanners_table.get_row_at(i)[0] for i in range(scanners_table.row_count)}
            self.assertEqual(scanner_names, {"secrets", "reputation"})

            # STORY-1603: the block is in the tagged event log, [WAIT] not
            # color alone.
            events_table = app.query_one("#events", DataTable)
            self.assertEqual(str(events_table.get_row_at(0)[2]), "[WAIT]")

            # Attention signal fired for the new review (title updated).
            self.assertIn("1 pending review", app.title)

            # STORY-1604: dashboard shows the real blocked call.
            await pilot.press("r")
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#tool-input", Static).content, json.dumps({"file_path": str(target_path)}, indent=2))
            targets_table = app.screen.query_one("#targets", DataTable)
            self.assertEqual(targets_table.get_row_at(0)[0], str(target_path))
            self.assertEqual(targets_table.get_row_at(0)[2], "not yet scanned")

            # Verify -> real scan -> Allow unlocked.
            await pilot.click(app.screen.query_one("#verify-btn"))
            await pilot.pause()
            self.assertFalse(app.screen.query_one("#allow-btn").disabled)

            # STORY-1605: Allow form pre-filled, submits a real rule.
            await pilot.click(app.screen.query_one("#allow-btn"))
            await pilot.pause()
            await pilot.pause()
            self.assertEqual(app.screen.query_one("#sensitivity-input", Input).value, "public")
            self.assertEqual(app.screen.query_one("#mode-input", Input).value, "allow")
            await pilot.click(app.screen.query_one("#submit-btn"))
            await pilot.pause()
            await pilot.pause()

            self.assertEqual(app._pending_reviews, [])
            self.assertIn("scg monitor", app.title)
            self.assertNotIn("pending review", app.title)

        self.assertTrue(self.policy_path.exists())
        written = self.policy_path.read_text()
        self.assertIn("mode: allow", written)

        # The retry: identical original call, real fresh config reload
        # from the just-written policy file, now genuinely allowed.
        second = pre_tool_use(
            hook_input,
            PolicyConfig.from_yaml(self.policy_path),
            state_dir=self.state_dir,
            cache_path=self.cache_path,
            audit_log_path=self.audit_log,
        )
        self.assertEqual(second["hookSpecificOutput"]["permissionDecision"], "allow")

        # And that allow is now itself visible in the monitor's tagged log
        # (STORY-1603's full-stream requirement) on the next poll.
        app2 = MonitorApp(
            state_dir=self.state_dir, audit_log_path=self.audit_log, cache_path=self.cache_path, policy_path=self.policy_path
        )
        async with app2.run_test() as pilot:
            app2.poll_data()
            await pilot.pause()
            events_table = app2.query_one("#events", DataTable)
            self.assertEqual(str(events_table.get_row_at(0)[2]), "[ALLOW]")


if __name__ == "__main__":
    unittest.main()
