"""Textual TUI for `scg monitor` (STORY-701/702). Thin composition over
`monitor_data.py` — this module is the only place that imports `textual`, so
the optional `[monitor]` extra never touches the hot-path hook adapter
(docs/ARCHITECTURE.md sec 11.1).
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, Static
from textual.widgets.data_table import RowDoesNotExist

from .hook_adapter import DEFAULT_AUDIT_LOG
from .monitor_data import (
    AuditTail,
    ReviewEntry,
    ToolCallEvent,
    build_review_entry,
    discover_scan_results,
    discover_scanner_activity,
    discover_sessions,
    target_status,
)
from .onboard import BLOCKED_LABELS, write_rule
from .policy_config import PolicyConfig, PolicyConfigError, PolicyRule
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache
from .scanner import ScannerMachineryError
from .taint_state import DEFAULT_STATE_DIR

# docs/ARCHITECTURE.md sec 11.2: poll, don't filesystem-watch.
POLL_INTERVAL_SECONDS = 0.5

# Same duplicated-by-convention constant as cli.py/onboard.py (both define
# their own DEFAULT_POLICY_PATH rather than sharing one) -- matches existing
# precedent rather than introducing a new cross-module dependency for it.
DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")

# docs/ARCHITECTURE.md sec20.3 (STORY-1603): text/symbol tags, color layered
# on top as a secondary cue only (Smith's Gate 1 accessibility note) -- the
# tag string alone must carry every bit of information color would.
_TAG_TEXT = {
    "allow": "[ALLOW]",
    "confirmed_bad": "[DENY]",
    "uncleared": "[WAIT]",
}
_TAG_STYLE = {
    "allow": "green",
    "confirmed_bad": "bold red",
    "uncleared": "yellow",
}
_UNKNOWN_BLOCK_TAG = "[BLOCK]"  # a pre-sec20 audit-log line: block, no block_kind


def _event_tag(event: ToolCallEvent) -> Text:
    """docs/ARCHITECTURE.md sec20.3: one text tag per row, identifying
    outcome/block_kind without relying on color. `event.event` is "allow" or
    "block"; for a block, `block_kind` ("confirmed_bad"/"uncleared") picks
    the specific tag -- an old-format block entry with no `block_kind` at
    all falls back to a generic tag rather than crashing or misreporting."""
    if event.event == "allow":
        return Text(_TAG_TEXT["allow"], style=_TAG_STYLE["allow"])
    if event.block_kind in _TAG_TEXT:
        return Text(_TAG_TEXT[event.block_kind], style=_TAG_STYLE[event.block_kind])
    return Text(_UNKNOWN_BLOCK_TAG, style="red")


_NO_SESSIONS_MESSAGE = "No sessions found yet. Run an agent session with scalene-guard installed, then reopen the monitor."


def _format_relative_time(scanned_at: float, now: float | None = None) -> str:
    """Short 'X ago' formatting for the resource-cache panel's Last Scanned
    column (Smith's Phase 5 gate finding: an absolute 'YYYY-MM-DD HH:MM:SS'
    timestamp -- 19 characters -- truncated to an unreadable string once a
    3rd panel divided the same horizontal space 2 panels used to have, at a
    real, common 120-column terminal width). Clamped at 0 so real-world
    clock skew between a worker process and the monitor process reading its
    result never renders as a confusing negative duration."""
    delta = max(0.0, (now if now is not None else time.time()) - scanned_at)
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta // 60)}m ago"
    if delta < 86400:
        return f"{int(delta // 3600)}h ago"
    return f"{int(delta // 86400)}d ago"


class ReviewScreen(Screen):
    """docs/ARCHITECTURE.md sec20.4/20.5 (STORY-1604/1605): the Verify/
    Allow/Deny dashboard for one queued review. Not a live gate:
    `pre_tool_use` already resolved (denied) this call synchronously before
    this screen ever exists (sec20.1) -- Verify/Allow populate the scan
    cache and policy file for real, they don't change whether the original
    call was allowed; only a subsequent retry of the identical call can now
    succeed (STORY-1601's retry guidance is what tells the agent to retry).

    Dismisses with `True` when the review was actually resolved (Deny, or
    a successful Allow submit) so `MonitorApp` dequeues it -- dismisses
    with `False` on a plain Escape ("close for now, still queued"), the
    same "ignoring it just leaves it queued" model as the rest of this
    review-queue design."""

    BINDINGS = [("escape", "dismiss_review", "Close (stays queued)")]

    def __init__(self, entry: ReviewEntry, cache_path: Path, scanners: dict, policy_path: Path) -> None:
        super().__init__()
        self._entry = entry
        self._cache_path = cache_path
        self._scanners = scanners
        self._policy_path = policy_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(f"Tool: {self._entry.event.tool_name}  |  Session: {self._entry.event.session_id}")
        yield Static(json.dumps(self._entry.event.tool_input, indent=2), id="tool-input")
        yield DataTable(id="targets")
        with Horizontal():
            yield Button("Verify", id="verify-btn")
            yield Button("Deny", id="deny-btn")
            # docs/ARCHITECTURE.md sec20.4: Allow is disabled/unreachable
            # until every target's Verify has completed -- Textual's own
            # `disabled` state, not just a visual hint the user could
            # click past.
            yield Button("Allow", id="allow-btn", disabled=True)
        with Vertical(id="allow-form"):
            yield Static("Sensitivity (public/internal/restricted):")
            yield Input(value="public", id="sensitivity-input")
            yield Static("Mode (allow/block):")
            yield Input(value="allow", id="mode-input")
            yield Button("Submit rule", id="submit-btn")
        yield Static("", id="allow-error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#targets", DataTable)
        table.add_columns("Target", "Kind", "Status", "Verified")
        self.query_one("#allow-form", Vertical).display = False
        self.refresh_targets()

    def refresh_targets(self) -> None:
        table = self.query_one("#targets", DataTable)
        table.clear()
        cache = ScanCache(self._cache_path)
        for t in self._entry.targets:
            status = target_status(t, cache)
            verified = "yes" if self._entry.verified.get(t.identity) else "no"
            table.add_row(t.identity, t.kind, status, verified)
        self.query_one("#allow-btn", Button).disabled = not self._entry.all_verified

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "verify-btn":
            self.action_verify()
        elif event.button.id == "deny-btn":
            self.dismiss(True)
        elif event.button.id == "allow-btn":
            self.query_one("#allow-form", Vertical).display = True
        elif event.button.id == "submit-btn":
            self.action_submit_allow()

    def action_verify(self) -> None:
        # docs/ARCHITECTURE.md sec20.4: the same two calls onboard._onboard_resource
        # already makes for a real scan (scanner.scan() + cache.put()) --
        # invoked directly here since Verify must not write a rule yet
        # (that's Allow's job, sec20.5). try_reserve()/put() around the scan
        # means Phase 3's Scanners panel shows real busy/idle activity for a
        # manual Verify too, not just background first-sighting scans.
        cache = ScanCache(self._cache_path)
        for t in self._entry.targets:
            scanner = self._scanners.get(t.scanner_name)
            if scanner is None:
                continue
            cache.try_reserve(t)
            try:
                result = scanner.scan(t)
            except ScannerMachineryError:
                # Fail-safe, not fail-crash: this is a live TUI, not the
                # fatal-exit hook path (sec13's distinction) -- leave this
                # target unverified so the operator can see it and retry,
                # rather than taking down the whole review screen.
                continue
            cache.put(t, result)
            self._entry.verified[t.identity] = True
        self.refresh_targets()

    def action_submit_allow(self) -> None:
        # docs/ARCHITECTURE.md sec20.5 (STORY-1605): default pattern is
        # re.escape(identity) -- onboard.py's own existing default, reused
        # verbatim, not a new derivation. Same BLOCKED_LABELS guard
        # onboard._onboard_resource applies, checked against the result
        # Verify already cached -- no re-scan here.
        sensitivity = self.query_one("#sensitivity-input", Input).value.strip() or "public"
        mode = self.query_one("#mode-input", Input).value.strip() or "allow"
        cache = ScanCache(self._cache_path)
        errors = []
        written = []
        for t in self._entry.targets:
            entry = cache.get(t)
            if entry is not None and entry.label in BLOCKED_LABELS and mode != "block":
                errors.append(f"{t.identity}: {entry.reason or 'scan found a real issue'} (use mode=block to override)")
                continue
            try:
                rule = PolicyRule(tool=".*", pattern=re.escape(t.identity), sensitivity=sensitivity, mode=mode)
            except PolicyConfigError as exc:
                errors.append(f"{t.identity}: {exc}")
                continue
            write_rule(self._policy_path, rule)
            written.append(t.identity)

        if errors and not written:
            self.query_one("#allow-error", Static).update("; ".join(errors))
            return
        self.dismiss(True)

    def action_dismiss_review(self) -> None:
        self.dismiss(False)


class MonitorApp(App):
    """Live view of session trust/sensitivity tags and block events
    (STORY-701). docs/ARCHITECTURE.md sec15 (2026-07-17): STORY-702's
    editable-and-applyable onboard-command workflow is retired -- clearing
    a destination now always takes two explicit steps (a real scan, then a
    hand-authored rule), not one runnable command."""

    CSS = """
    #no-sessions { padding: 1 2; color: $text-muted; display: none; }
    #no-sessions.visible { display: block; }
    #top-row { height: 60%; }
    #scan-results-panel { height: 40%; }
    #scanners-panel { width: 24; }
    """
    BINDINGS = [
        ("a", "toggle_all_sessions", "Toggle all-sessions feed"),
        ("r", "open_review", "Review oldest pending block"),
    ]

    def __init__(
        self,
        state_dir: Path = DEFAULT_STATE_DIR,
        audit_log_path: Path = DEFAULT_AUDIT_LOG,
        cache_path: Path = DEFAULT_CACHE_PATH,
        policy_path: Path = DEFAULT_POLICY_PATH,
    ) -> None:
        super().__init__()
        self._state_dir = state_dir
        self._tail = AuditTail(audit_log_path)
        self._cache_path = cache_path
        self._policy_path = policy_path
        self._events: list[ToolCallEvent] = []
        self._visible_events: list[ToolCallEvent] = []
        self.selected_session_id: str | None = None
        self.show_all_sessions = False
        # docs/ARCHITECTURE.md sec20.2 (STORY-1602): same load pattern as
        # cli.py/onboard.py's main() -- a missing or invalid policy file
        # falls back to the 2 builtin scanners, never crashes the monitor.
        try:
            config = PolicyConfig.from_yaml(policy_path) if Path(policy_path).exists() else PolicyConfig()
        except PolicyConfigError:
            config = PolicyConfig()
        self._scanners = config.scanners
        # docs/ARCHITECTURE.md sec20.4 (STORY-1604): a to-do queue, not a
        # live gate -- the hook already resolved this call synchronously
        # before the TUI ever saw it, so an unreviewed entry just stays
        # queued (no timeout).
        self._pending_reviews: list[ReviewEntry] = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(_NO_SESSIONS_MESSAGE, id="no-sessions")
        with Horizontal(id="top-row"):
            with Vertical():
                yield Static("Sessions")
                yield DataTable(id="sessions")
            with Vertical():
                yield Static("Block events (press 'a' to toggle all-sessions)")
                yield DataTable(id="events")
            with Vertical(id="scanners-panel"):
                yield Static("Scanners")
                yield DataTable(id="scanners")
        # STORY-1005 / Smith's Phase 5 gate finding: a resource identity can be
        # a long file path or hostname -- squeezed into a 3rd side-by-side
        # column (alongside Sessions/Block-events) it doesn't have enough
        # combined width to stay readable at a common terminal size (real
        # screenshot confirmed truncation even after shortening the
        # timestamp format). Full-width row below instead, so it gets the
        # entire terminal width rather than a third of it.
        with Vertical(id="scan-results-panel"):
            yield Static("Resource cache (recently scanned files/hosts)")
            yield DataTable(id="scan-results")
        yield Footer()

    def on_mount(self) -> None:
        sessions_table = self.query_one("#sessions", DataTable)
        sessions_table.add_columns("Session", "Trust", "Sensitivity")
        sessions_table.cursor_type = "row"

        events_table = self.query_one("#events", DataTable)
        events_table.add_columns("Session", "Tool", "Tag", "Reason")
        events_table.cursor_type = "row"

        scan_results_table = self.query_one("#scan-results", DataTable)
        scan_results_table.add_columns("Resource", "Label", "Last Scanned")
        scan_results_table.cursor_type = "row"

        scanners_table = self.query_one("#scanners", DataTable)
        scanners_table.add_columns("Scanner", "Status")

        self.refresh_sessions()
        self.refresh_scan_results()
        self.refresh_scanner_activity()
        self._refresh_review_title()
        self.set_interval(POLL_INTERVAL_SECONDS, self.poll_data)

    def refresh_sessions(self) -> None:
        sessions = discover_sessions(self._state_dir)
        table = self.query_one("#sessions", DataTable)
        table.clear()

        no_sessions_widget = self.query_one("#no-sessions", Static)
        no_sessions_widget.set_class(not sessions, "visible")

        for s in sessions:
            table.add_row(s.session_id, s.trust, s.sensitivity, key=s.session_id)

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
                new_reviews = False
                for e in new_events:
                    if e.event == "block":
                        self._pending_reviews.append(build_review_entry(e, self._scanners))
                        new_reviews = True
                if new_reviews:
                    # docs/ARCHITECTURE.md sec20.4 (STORY-1604), Smith's Gate 1
                    # hard-requirement watch-item: a queued review must be
                    # noticeable, not just present if the operator happens to
                    # be looking. bell() + a pending-count in the title are
                    # both plain Textual App members on the installed version
                    # (verified against the real installed package, not
                    # assumed from the architecture doc).
                    self.bell()
                    self._refresh_review_title()
            self.refresh_sessions()
            self.refresh_scan_results()
            self.refresh_scanner_activity()
        except NoMatches:
            pass

    def refresh_scan_results(self) -> None:
        # STORY-1005: reads .scalene/scan_cache.json directly (via
        # discover_scan_results -> ScanCache.all_entries()) on every poll --
        # no separate bookkeeping of its own to drift from the real store.
        results = discover_scan_results(self._cache_path)
        table = self.query_one("#scan-results", DataTable)
        table.clear()
        for r in results:
            table.add_row(r.identity, r.label, _format_relative_time(r.scanned_at))

    def refresh_scanner_activity(self) -> None:
        # docs/ARCHITECTURE.md sec20.2: one row per *configured* scanner
        # (self._scanners, loaded once at startup from the real policy
        # file) -- a config-declared scanner (E15/STORY-1501) shows up here
        # with no monitor code change needed.
        activity = discover_scanner_activity(self._cache_path, self._scanners)
        table = self.query_one("#scanners", DataTable)
        table.clear()
        for a in activity:
            table.add_row(a.name, "busy" if a.busy else "idle")

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
            table.add_row(e.session_id, e.tool_name, _event_tag(e), e.reason)

    def action_toggle_all_sessions(self) -> None:
        self.show_all_sessions = not self.show_all_sessions
        self.refresh_events()

    def action_open_review(self) -> None:
        # docs/ARCHITECTURE.md sec20.4: oldest unresolved entry first, FIFO
        # -- resolves Smith's Gate 1 note on multiple simultaneous block
        # events without needing timeout/expiry logic (see ReviewScreen's
        # docstring).
        if self._pending_reviews:
            entry = self._pending_reviews[0]
            self.push_screen(
                ReviewScreen(entry, self._cache_path, self._scanners, self._policy_path),
                callback=lambda resolved: self._on_review_resolved(entry, resolved),
            )

    def _on_review_resolved(self, entry: ReviewEntry, resolved: bool) -> None:
        # `resolved=False` (plain Escape) leaves it queued -- same "ignoring
        # it just leaves it queued" model as the rest of this design.
        if resolved and entry in self._pending_reviews:
            self._pending_reviews.remove(entry)
        self._refresh_review_title()

    def _refresh_review_title(self) -> None:
        count = len(self._pending_reviews)
        self.title = f"scg monitor — {count} pending review{'s' if count != 1 else ''}" if count else "scg monitor"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "sessions":
            self.selected_session_id = str(event.row_key.value)
            self.refresh_events()
