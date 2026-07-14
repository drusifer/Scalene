"""Integration tests for the `scg monitor` TUI (STORY-701/702), using
Textual's built-in headless test harness (`App.run_test()` / `Pilot`) rather
than a real terminal or hand-rolled mocking."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from textual.widgets import DataTable, Input

from scalene.monitor_app import MonitorApp, _NO_SESSIONS_MESSAGE


def _write_state(state_dir: Path, session_id: str, sensitive: bool, untrusted: bool) -> None:
    (state_dir / f"{session_id}.json").write_text(
        json.dumps({"session_id": session_id, "has_sensitive_data": sensitive, "has_untrusted_data": untrusted})
    )


def _append_mask_event(audit_log: Path, session_id: str, tool_name: str = "Bash") -> None:
    with audit_log.open("a") as f:
        f.write(
            json.dumps(
                {
                    "event": "mask",
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "payload_field": "command",
                    "suggested_onboard_command": "scg onboard ...",
                }
            )
            + "\n"
        )


class TestMonitorApp(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.state_dir = Path(self._tmp.name) / "state"
        self.state_dir.mkdir()
        self.audit_log = Path(self._tmp.name) / "audit.log"

    def tearDown(self):
        self._tmp.cleanup()

    async def test_shows_no_sessions_message_when_none_exist(self):
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test():
            widget = app.query_one("#no-sessions")
            self.assertIn("visible", widget.classes)
            self.assertEqual(widget.content, _NO_SESSIONS_MESSAGE)

    async def test_discovers_sessions_and_hides_empty_message(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=False)
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test():
            widget = app.query_one("#no-sessions")
            self.assertNotIn("visible", widget.classes)
            table = app.query_one("#sessions", DataTable)
            self.assertEqual(table.row_count, 1)

    async def test_default_selection_is_first_session_and_filters_events(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")
        _append_mask_event(self.audit_log, "other-session", tool_name="Write")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            self.assertEqual(app.selected_session_id, "s1")
            events_table = app.query_one("#events", DataTable)
            # Only s1's event should be visible by default (not other-session's).
            self.assertEqual(events_table.row_count, 1)

    async def test_events_are_shown_newest_first(self):
        # STORY-701 AC: "newest first, as they're appended."
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")
        _append_mask_event(self.audit_log, "s1", tool_name="Write")
        _append_mask_event(self.audit_log, "s1", tool_name="Edit")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            tool_column = [events_table.get_row_at(i)[1] for i in range(events_table.row_count)]
            self.assertEqual(tool_column, ["Edit", "Write", "Bash"])

    async def test_toggle_all_sessions_shows_every_session_event(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1")
        _append_mask_event(self.audit_log, "other-session")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            self.assertEqual(events_table.row_count, 1)

            await pilot.press("a")
            self.assertEqual(events_table.row_count, 2)

    async def test_cursor_stays_on_selected_session_across_a_poll_refresh(self):
        # Regression for a real bug (Smith's *user test, 2026-07-10): selecting
        # a non-default session, then any poll tick (e.g. a new mask event for
        # a *different* session) must not visually reset the highlighted row
        # to the top while the actual filter silently stays on the real
        # selection — the highlighted row and the filtered session must never
        # diverge (Nielsen #1: visibility of system status).
        _write_state(self.state_dir, "s1", sensitive=False, untrusted=False)
        _write_state(self.state_dir, "s2", sensitive=False, untrusted=False)
        _write_state(self.state_dir, "s3", sensitive=False, untrusted=False)

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            table = app.query_one("#sessions", DataTable)
            table.move_cursor(row=2)
            await pilot.press("enter")
            await pilot.pause()
            selected_after_click = app.selected_session_id
            row_after_click = table.cursor_row

            _append_mask_event(self.audit_log, "some-other-session")
            app.poll_data()
            await pilot.pause()

            self.assertEqual(app.selected_session_id, selected_after_click)
            self.assertEqual(table.cursor_row, row_after_click)

    async def test_never_shows_an_event_for_a_non_mask_audit_entry(self):
        # Regression guard for STORY-701's core AC: onboard.py writes
        # {"event": "onboard", ...} to the same audit.log — must never render
        # as a mask event.
        _write_state(self.state_dir, "s1", sensitive=False, untrusted=False)
        with self.audit_log.open("a") as f:
            f.write(json.dumps({"event": "onboard", "rule": {}}) + "\n")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            await pilot.press("a")  # show all sessions too, still should be empty
            events_table = app.query_one("#events", DataTable)
            self.assertEqual(events_table.row_count, 0)

    async def test_selecting_an_event_populates_the_editable_command_input(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            events_table.focus()
            events_table.move_cursor(row=0)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            command_input = app.query_one("#command-input", Input)
            self.assertEqual(command_input.value, "scg onboard ...")
            self.assertFalse(command_input.disabled)

    async def test_apply_runs_the_edited_command_and_reports_success(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        with patch("scalene.monitor_app.apply_onboard_command", return_value=(True, "Rule added: {...}")) as mock_apply:
            async with app.run_test() as pilot:
                app.poll_data()
                await pilot.pause()

                events_table = app.query_one("#events", DataTable)
                events_table.focus()
                events_table.move_cursor(row=0)
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                command_input = app.query_one("#command-input", Input)
                command_input.value = "scg onboard --target https://example.com --tool Bash"
                await pilot.press("enter")
                await pilot.pause()

                mock_apply.assert_called_once_with("scg onboard --target https://example.com --tool Bash")
                status = app.query_one("#apply-status")
                self.assertIn("Rule added", str(status.render()))

    async def test_apply_reports_failure_without_crashing(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        with patch("scalene.monitor_app.apply_onboard_command", return_value=(False, "Onboarding blocked: secrets check failed")):
            async with app.run_test() as pilot:
                app.poll_data()
                await pilot.pause()

                events_table = app.query_one("#events", DataTable)
                events_table.focus()
                events_table.move_cursor(row=0)
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                status = app.query_one("#apply-status")
                self.assertIn("Onboarding blocked", str(status.render()))

    async def test_dismiss_clears_input_with_no_side_effect(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        with patch("scalene.monitor_app.apply_onboard_command") as mock_apply:
            async with app.run_test() as pilot:
                app.poll_data()
                await pilot.pause()

                events_table = app.query_one("#events", DataTable)
                events_table.focus()
                events_table.move_cursor(row=0)
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                command_input = app.query_one("#command-input", Input)
                self.assertFalse(command_input.disabled)

                await pilot.press("escape")
                await pilot.pause()

                mock_apply.assert_not_called()
                self.assertTrue(command_input.disabled)
                self.assertEqual(command_input.value, "")

    async def test_dismiss_returns_focus_so_the_user_can_select_another_event(self):
        # Regression for a real bug (Smith's *user test, 2026-07-10): disabling
        # a focused Input causes Textual to blur it (Widget.watch_disabled's
        # own documented behavior) — leaving app.focused as None strands the
        # user with no way to press Enter on anything until they manually
        # click/Tab elsewhere. Dismissing must hand focus back somewhere usable.
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test() as pilot:
            app.poll_data()
            await pilot.pause()

            events_table = app.query_one("#events", DataTable)
            events_table.focus()
            events_table.move_cursor(row=0)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()

            self.assertIsNotNone(app.focused)
            self.assertIs(app.focused, events_table)

    async def test_poll_data_after_teardown_does_not_raise(self):
        # Regression for a real, if rare, flake observed in this suite: the
        # 500ms poll timer can fire after `run_test()`'s screen has already
        # torn down (`query_one("#sessions")` -> NoMatches), crashing the
        # whole test run. Reproduce deterministically (no real-time race
        # needed) by calling poll_data() after the app context has exited.
        _write_state(self.state_dir, "s1", sensitive=False, untrusted=False)
        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        async with app.run_test():
            pass
        app.poll_data()  # must not raise NoMatches after teardown

    async def test_apply_returns_focus_so_the_user_can_select_another_event(self):
        _write_state(self.state_dir, "s1", sensitive=True, untrusted=True)
        _append_mask_event(self.audit_log, "s1", tool_name="Bash")

        app = MonitorApp(state_dir=self.state_dir, audit_log_path=self.audit_log)
        with patch("scalene.monitor_app.apply_onboard_command", return_value=(True, "ok")):
            async with app.run_test() as pilot:
                app.poll_data()
                await pilot.pause()

                events_table = app.query_one("#events", DataTable)
                events_table.focus()
                events_table.move_cursor(row=0)
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()
                await pilot.press("enter")
                await pilot.pause()

                self.assertIsNotNone(app.focused)
                self.assertIs(app.focused, events_table)


if __name__ == "__main__":
    unittest.main()
