"""Textual TUI for `scalene monitor` (STORY-701/702). Thin composition over
`monitor_data.py` — this module is the only place that imports `textual`, so
the optional `[monitor]` extra never touches the hot-path hook adapter
(docs/ARCHITECTURE.md sec 11.1).
"""

from __future__ import annotations

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.widgets import DataTable, Footer, Header, Input, Static
from textual.widgets.data_table import RowDoesNotExist

from .hook_adapter import DEFAULT_AUDIT_LOG
from .monitor_data import AuditTail, MaskEvent, apply_onboard_command, discover_sessions
from .taint_state import DEFAULT_STATE_DIR

# docs/ARCHITECTURE.md sec 11.2: poll, don't filesystem-watch.
POLL_INTERVAL_SECONDS = 0.5

_NO_SESSIONS_MESSAGE = "No sessions found yet. Run an agent session with scalene-guard installed, then reopen the monitor."


class MonitorApp(App):
    """Live view of session taint status and mask events (STORY-701), with an
    editable-and-applyable suggested onboard command per mask event (STORY-702)."""

    CSS = """
    #no-sessions { padding: 1 2; color: $text-muted; display: none; }
    #no-sessions.visible { display: block; }
    """
    BINDINGS = [
        ("a", "toggle_all_sessions", "Toggle all-sessions feed"),
        ("escape", "dismiss_edit", "Dismiss"),
    ]

    def __init__(
        self,
        state_dir: Path = DEFAULT_STATE_DIR,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
    ) -> None:
        super().__init__()
        self._state_dir = state_dir
        self._tail = AuditTail(audit_log_path)
        self._events: list[MaskEvent] = []
        self._visible_events: list[MaskEvent] = []
        self.selected_session_id: str | None = None
        self.show_all_sessions = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(_NO_SESSIONS_MESSAGE, id="no-sessions")
        with Horizontal():
            with Vertical():
                yield Static("Sessions")
                yield DataTable(id="sessions")
            with Vertical():
                yield Static("Mask events (press 'a' to toggle all-sessions, Enter to edit+apply, Escape to dismiss)")
                yield DataTable(id="events")
        yield Input(placeholder="Select a mask event to edit its onboard command...", id="command-input", disabled=True)
        yield Static("", id="apply-status")
        yield Footer()

    def on_mount(self) -> None:
        sessions_table = self.query_one("#sessions", DataTable)
        sessions_table.add_columns("Session", "Sensitive", "Untrusted")
        sessions_table.cursor_type = "row"

        events_table = self.query_one("#events", DataTable)
        events_table.add_columns("Session", "Tool", "Field")
        events_table.cursor_type = "row"

        self.refresh_sessions()
        self.set_interval(POLL_INTERVAL_SECONDS, self.poll_data)

    def refresh_sessions(self) -> None:
        sessions = discover_sessions(self._state_dir)
        table = self.query_one("#sessions", DataTable)
        table.clear()

        no_sessions_widget = self.query_one("#no-sessions", Static)
        no_sessions_widget.set_class(not sessions, "visible")

        for s in sessions:
            table.add_row(s.session_id, str(s.has_sensitive_data), str(s.has_untrusted_data), key=s.session_id)

        if self.selected_session_id is None and sessions:
            self.selected_session_id = sessions[0].session_id

        # DataTable.clear() unconditionally resets the cursor to row 0 — restore
        # it to whichever row the actually-selected session landed on, so the
        # highlighted row never silently diverges from the real selection.
        if self.selected_session_id is not None:
            try:
                row_index = table.get_row_index(self.selected_session_id)
            except RowDoesNotExist:
                pass
            else:
                table.move_cursor(row=row_index)

    def poll_data(self) -> None:
        # The periodic poll timer can fire after the app has already started
        # tearing down (e.g. the user quit mid-tick) — the table widgets are
        # gone by then, and there's nothing meaningful left to refresh.
        try:
            new_events = self._tail.poll()
            if new_events:
                self._events.extend(new_events)
                self.refresh_events()
            self.refresh_sessions()
        except NoMatches:
            pass

    def refresh_events(self) -> None:
        table = self.query_one("#events", DataTable)
        table.clear()
        visible = (
            self._events
            if self.show_all_sessions
            else [e for e in self._events if e.session_id == self.selected_session_id]
        )
        self._visible_events = list(reversed(visible))  # newest first — same order as the rows below
        for e in self._visible_events:
            table.add_row(e.session_id, e.tool_name, e.payload_field)

    def action_toggle_all_sessions(self) -> None:
        self.show_all_sessions = not self.show_all_sessions
        self.refresh_events()

    def action_dismiss_edit(self) -> None:
        """STORY-702: dismissing has no side effect — just clears the editor."""
        command_input = self.query_one("#command-input", Input)
        command_input.value = ""
        command_input.disabled = True
        self._return_focus_to_events_table()

    def _return_focus_to_events_table(self) -> None:
        """Disabling a focused Input blurs it (Widget.watch_disabled's own
        documented behavior) without focusing anything else — leaving the
        user stranded with no focused widget at all. Hand focus back to the
        events table so Enter immediately works on the next event."""
        self.query_one("#events", DataTable).focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "sessions":
            self.selected_session_id = str(event.row_key.value)
            self.refresh_events()
        elif event.data_table.id == "events":
            mask_event = self._visible_events[event.cursor_row]
            command_input = self.query_one("#command-input", Input)
            command_input.disabled = False
            command_input.value = mask_event.suggested_onboard_command
            command_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "command-input":
            return
        # STORY-702: a real subprocess call to the actual `scalene` CLI — never
        # a reimplementation, so this can't bypass onboard.py's safety gates.
        ok, output = apply_onboard_command(event.value)
        status = self.query_one("#apply-status", Static)
        status.update(("Applied: " if ok else "Failed: ") + output)
        event.input.value = ""
        event.input.disabled = True
        self._return_focus_to_events_table()
