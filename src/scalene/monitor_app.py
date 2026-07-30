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
from textual.widgets import Button, DataTable, Footer, Header, Input, RadioButton, RadioSet, Static
from textual.widgets.data_table import RowDoesNotExist

from .hook_adapter import DEFAULT_AUDIT_LOG, append_audit_log
from .monitor_data import (
    AuditTail,
    ReviewEntry,
    ReviewResolution,
    ToolCallEvent,
    build_review_entry,
    discover_scan_results,
    discover_scanner_activity,
    discover_sessions,
    target_status,
)
from .onboard import BLOCKED_LABELS, write_rule
from .policy_config import VALID_RULE_MODES, VALID_SENSITIVITIES, PolicyConfig, PolicyConfigError, PolicyRule
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache
from .scanner import Resource, ScannerMachineryError, escape_gitignore_literal
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

    BINDINGS = [
        ("escape", "dismiss_review", "Close (stays queued)"),
        ("n", "next_review", "Next review"),
        ("p", "prev_review", "Previous review"),
    ]

    # Compact layout fix: the tool-input JSON and the targets table were
    # both unbounded-height, so a multi-key tool call or several targets
    # could push "Submit rule" below the visible screen with no obvious way
    # to reach it. Both are capped and independently scrollable now, so the
    # rest of the screen (nav row, action buttons, allow-form) always fits.
    CSS = """
    ReviewScreen #nav-row {
        height: auto;
    }
    ReviewScreen #review-position {
        /* Static's default width is 1fr (fill remaining space) -- left
        unset here, an empty-text Static expanded to the full screen width
        on its own, pushing #next-btn's x past the right edge entirely
        (a real bug this exact compactness fix hit: OutOfBounds trying to
        click a button that had been shoved off an 80-col screen). */
        width: auto;
        content-align: center middle;
        padding: 0 2;
    }
    ReviewScreen #tool-input {
        height: auto;
        max-height: 4;
        overflow-y: auto;
        border: round $primary;
    }
    ReviewScreen #targets {
        height: auto;
        max-height: 5;
    }
    ReviewScreen #allow-form {
        /* Same 1fr-default bug as #review-position/#sensitivity-input
        above, but for height instead of width: an unconstrained Vertical
        defaults to a *share* of remaining screen space (1fr), not "fit my
        children". With a 2-row #targets table (vs. 1 for a single target)
        taking 1 more row, allow-form's 1fr share shrank by that same row,
        silently compressing its rendered content -- #allow-error (the next
        sibling) then started 1 row too early and overlapped #submit-btn's
        row entirely, silently swallowing every click on it (no error, no
        exception -- the click just landed on the wrong widget). Real bug,
        caught by test_typed_pattern_writes_one_shared_rule_for_a_multi_target_call,
        not the single-target tests, which happened not to hit the
        off-by-one. */
        height: auto;
    }
    ReviewScreen .field-row {
        height: auto;
    }
    ReviewScreen .field-label {
        width: 12;
        content-align: right middle;
        padding-right: 1;
    }
    ReviewScreen #rule-tool-input, ReviewScreen #rule-pattern-input,
    ReviewScreen #sensitivity-radio, ReviewScreen #mode-radio {
        /* Same class of bug as #review-position above: an unconstrained
        child's default width (1fr) means the first one alone fills the
        whole row, shoving the next one off the right edge of the screen
        entirely. Split the row evenly instead. */
        width: 1fr;
        height: auto;
    }
    """

    def __init__(self, pending: list[ReviewEntry], index: int, cache_path: Path, scanners: dict, policy_path: Path) -> None:
        super().__init__()
        # `pending` is the same list object as MonitorApp._pending_reviews
        # (not a copy) -- Next/Prev browse it in place. The list's length
        # doesn't change while this screen is open (an item is only removed
        # on resolve, which closes the screen), so an index into it stays
        # valid across navigation within one open of this screen.
        self._pending = pending
        self._index = index
        self._entry = pending[index]
        self._cache_path = cache_path
        self._scanners = scanners
        self._policy_path = policy_path

    def compose(self) -> ComposeResult:
        yield Header()
        # Nav row merged onto one line (was: a Static line, then a separate
        # buttons row) -- part of the same compactness fix as the CSS
        # height caps above.
        # `compact=True` throughout this screen (Buttons/Inputs/RadioButtons
        # all support it -- the documented, supported way to get a denser
        # render, not a CSS height override fighting the widget's own
        # default box model): with 2 new editable-field rows added for the
        # Tool/Pattern/Sensitivity/Mode feature, the default 3-row-per-
        # widget box no longer fits "Submit rule" on a standard 80x24
        # screen at all (a real regression caught by
        # test_allow_form_fields_all_stay_within_a_standard_80x24_screen,
        # not just eyeballed).
        with Horizontal(id="nav-row"):
            yield Button("< Prev", id="prev-btn", compact=True)
            yield Static("", id="review-position")
            yield Button("Next >", id="next-btn", compact=True)
        yield Static("", id="review-header")
        yield Static("", id="tool-input")
        yield DataTable(id="targets")
        with Horizontal():
            yield Button("Verify", id="verify-btn", compact=True)
            yield Button("Deny", id="deny-btn", compact=True)
            # docs/ARCHITECTURE.md sec20.4: Allow is disabled/unreachable
            # until every target's Verify has completed -- Textual's own
            # `disabled` state, not just a visual hint the user could
            # click past.
            yield Button("Allow", id="allow-btn", disabled=True, compact=True)
        with Vertical(id="allow-form"):
            # Direct user request: editable tool/pattern, defaulting to the
            # exact tool name and an exact-match pattern -- widen either
            # before submitting instead of only being able to accept the
            # narrow auto-derived rule. `tool` is call-level (one value for
            # the whole entry, every target in one call shares the same
            # tool_name) so it's always editable; `pattern` is inherently
            # per-target, so it's only meaningfully editable when there's
            # exactly one target (see _refresh_allow_form_defaults) --
            # multi-target calls keep today's automatic per-target
            # derivation, shown disabled rather than silently ignored.
            with Horizontal(classes="field-row"):
                yield Static("Tool:", classes="field-label")
                yield Input(value="", id="rule-tool-input", compact=True)
                yield Static("Pattern:", classes="field-label")
                yield Input(value="", id="rule-pattern-input", compact=True)
            # Direct user request: a fixed valid-value grid instead of
            # free-text -- can't type an invalid sensitivity/mode. RadioSet
            # (single-select) is the correct widget, not a checkbox group
            # (independent booleans) -- sensitivity/mode are each exactly
            # one value, never several at once. `compact=True` keeps each
            # option to roughly one row instead of a bordered box, in
            # keeping with this whole screen's compactness fix.
            with Horizontal(classes="field-row"):
                yield Static("Sensitivity:", classes="field-label")
                with RadioSet(id="sensitivity-radio"):
                    for value in VALID_SENSITIVITIES:
                        yield RadioButton(value, value=(value == "public"), compact=True, id=f"sensitivity-{value}")
                yield Static("Mode:", classes="field-label")
                with RadioSet(id="mode-radio"):
                    for value in VALID_RULE_MODES:
                        yield RadioButton(value, value=(value == "allow"), compact=True, id=f"mode-{value}")
            yield Button("Submit rule", id="submit-btn", compact=True)
        yield Static("", id="allow-error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#targets", DataTable)
        table.add_columns("Target", "Kind", "Status", "Verified")
        self.query_one("#allow-form", Vertical).display = False
        self.refresh_header()
        self.refresh_targets()

    def _default_pattern_for(self, target: Resource) -> str:
        return escape_gitignore_literal(target.identity) if target.scanner_name == "secrets" else re.escape(target.identity)

    def _refresh_allow_form_defaults(self) -> None:
        # `tool` is call-level (every target in one call shares the same
        # tool_name), so it's always editable, defaulting to the exact
        # name. `pattern` is always editable too (2026-07-30, direct user
        # follow-up -- it was wrongly disabled for a multi-target call):
        # a single target prefills the real exact-match default, ready to
        # widen in place; a multi-target call leaves it blank -- typing one
        # pattern there writes ONE shared rule covering every target in the
        # call (action_submit_allow), instead of today's automatic
        # per-target derivation, which still applies when left blank.
        self.query_one("#rule-tool-input", Input).value = self._entry.event.tool_name
        pattern_input = self.query_one("#rule-pattern-input", Input)
        targets = self._entry.targets
        if len(targets) == 1:
            pattern_input.value = self._default_pattern_for(targets[0])
            pattern_input.placeholder = ""
        else:
            pattern_input.value = ""
            pattern_input.placeholder = "(blank = auto per target; or type one pattern for all)"
        # A different entry shouldn't inherit whatever sensitivity/mode was
        # last selected -- reset both RadioSets back to their default
        # option (public/allow). Setting a RadioButton's own `.value`
        # (not RadioSet's, which has no public setter) is what
        # (de)selects it; RadioSet enforces the single-select exclusivity.
        self._select_radio_default("sensitivity-radio", VALID_SENSITIVITIES, "public")
        self._select_radio_default("mode-radio", VALID_RULE_MODES, "allow")

    def _select_radio_default(self, radio_set_id: str, values: tuple[str, ...], default: str) -> None:
        radio_set = self.query_one(f"#{radio_set_id}", RadioSet)
        buttons = list(radio_set.children)
        buttons[values.index(default)].value = True

    def _selected_radio_value(self, radio_set_id: str, values: tuple[str, ...], default: str) -> str:
        radio_set = self.query_one(f"#{radio_set_id}", RadioSet)
        index = radio_set.pressed_index
        return values[index] if index >= 0 else default

    def refresh_header(self) -> None:
        # "X of Y" (STORY request: know how many rules/reviews remain) plus
        # re-pointing the tool/session/tool-input display and Prev/Next's
        # disabled state at whichever entry Next/Prev has navigated to.
        total = len(self._pending)
        self.query_one("#review-position", Static).update(f"Review {self._index + 1} of {total}")
        self.query_one("#review-header", Static).update(
            f"Tool: {self._entry.event.tool_name}  |  Session: {self._entry.event.session_id}"
        )
        self.query_one("#tool-input", Static).update(json.dumps(self._entry.event.tool_input, indent=2))
        # A different entry has its own independent allow-form state --
        # don't carry over a previous entry's open form, defaults, or error
        # text.
        self.query_one("#allow-form", Vertical).display = False
        self.query_one("#allow-error", Static).update("")
        self._refresh_allow_form_defaults()
        self.query_one("#prev-btn", Button).disabled = self._index == 0
        self.query_one("#next-btn", Button).disabled = self._index >= total - 1

    def refresh_targets(self) -> None:
        table = self.query_one("#targets", DataTable)
        table.clear()
        cache = ScanCache(self._cache_path)
        for t in self._entry.targets:
            status = target_status(t, cache)
            verified = "yes" if self._entry.is_verified(t, cache) else "no"
            table.add_row(t.identity, t.kind, status, verified)
        self.query_one("#allow-btn", Button).disabled = not self._entry.all_verified(cache)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "verify-btn":
            self.action_verify()
        elif event.button.id == "deny-btn":
            # Report *which* entry was resolved -- not necessarily the one
            # this screen was originally opened with, since Next/Prev may
            # have navigated elsewhere in the pending queue before Deny was
            # pressed. MonitorApp dequeues by this value, not by the
            # original open-time entry.
            self.dismiss(self._entry)
        elif event.button.id == "allow-btn":
            self.query_one("#allow-form", Vertical).display = True
            # Fewer clicks/steps (direct user request): land the cursor on
            # the field the operator is most likely to edit, rather than
            # requiring an extra click just to start typing.
            self.query_one("#rule-pattern-input", Input).focus()
        elif event.button.id == "submit-btn":
            self.action_submit_allow()
        elif event.button.id == "prev-btn":
            self.action_prev_review()
        elif event.button.id == "next-btn":
            self.action_next_review()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Fewer clicks/steps: Enter in either text field submits the rule
        # directly, same as clicking "Submit rule" -- no mouse required.
        # Sensitivity/Mode are RadioSets now (their own Enter toggles the
        # highlighted option, not this), not Inputs.
        if event.input.id in ("rule-tool-input", "rule-pattern-input"):
            self.action_submit_allow()

    def action_next_review(self) -> None:
        if self._index < len(self._pending) - 1:
            self._index += 1
            self._entry = self._pending[self._index]
            self.refresh_header()
            self.refresh_targets()

    def action_prev_review(self) -> None:
        if self._index > 0:
            self._index -= 1
            self._entry = self._pending[self._index]
            self.refresh_header()
            self.refresh_targets()

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
            # No separate "verified" bookkeeping needed -- cache.put()
            # alone makes is_verified()/all_verified() true immediately
            # (they read this same ScanCache), and unlike the old ephemeral
            # dict, this is real, persisted state that survives a monitor
            # restart.
            cache.put(t, result)
        self.refresh_targets()

    def action_submit_allow(self) -> None:
        # docs/ARCHITECTURE.md sec20.5 (STORY-1605): default pattern escapes
        # the identity as a literal, exact match -- onboard.py's own
        # existing default, reused verbatim, not a new derivation. Same
        # BLOCKED_LABELS guard onboard._onboard_resource applies, checked
        # against the result Verify already cached -- no re-scan here.
        # 2026-07-30 (Scanner.match()): escaping syntax must match whichever
        # scanner will interpret the pattern -- FileScanner ("secrets")
        # reads gitignore syntax, everything else still reads plain regex.
        #
        # `tool` is now editable (direct user request), defaulting to the
        # exact tool name rather than the old hardcoded ".*" -- kept plain
        # regex (unlike `pattern`, tool names aren't path-shaped, so glob's
        # directory-recursion semantics wouldn't add anything; regex
        # alternation already covers "any of these tools").
        tool = self.query_one("#rule-tool-input", Input).value.strip() or self._entry.event.tool_name
        edited_pattern = self.query_one("#rule-pattern-input", Input).value.strip()
        sensitivity = self._selected_radio_value("sensitivity-radio", VALID_SENSITIVITIES, "public")
        mode = self._selected_radio_value("mode-radio", VALID_RULE_MODES, "allow")
        cache = ScanCache(self._cache_path)

        if edited_pattern:
            # 2026-07-30 (direct user follow-up): a typed pattern writes
            # ONE shared rule covering every target in this call -- for a
            # single-target call this is identical to the per-target path
            # below (the prefilled default IS this target's pattern), but
            # for a multi-target call it means one intentional rule instead
            # of N duplicate-pattern rules. Still checks every target's
            # real cached result first, same safety guard as below, just
            # aggregated across all of them since one rule now covers all.
            errors = []
            for t in self._entry.targets:
                entry = cache.get(t)
                if entry is not None and entry.label in BLOCKED_LABELS and mode != "block":
                    errors.append(f"{t.identity}: {entry.reason or 'scan found a real issue'} (use mode=block to override)")
            if errors:
                self.query_one("#allow-error", Static).update("; ".join(errors))
                return
            try:
                rule = PolicyRule(tool=tool, pattern=edited_pattern, sensitivity=sensitivity, mode=mode)
            except PolicyConfigError as exc:
                self.query_one("#allow-error", Static).update(str(exc))
                return
            write_rule(self._policy_path, rule)
            self.dismiss(self._entry)
            return

        # Blank pattern: automatic per-target derivation, one rule per
        # target -- unchanged original behavior.
        errors = []
        written = []
        for t in self._entry.targets:
            entry = cache.get(t)
            if entry is not None and entry.label in BLOCKED_LABELS and mode != "block":
                errors.append(f"{t.identity}: {entry.reason or 'scan found a real issue'} (use mode=block to override)")
                continue
            pattern = self._default_pattern_for(t)
            try:
                rule = PolicyRule(tool=tool, pattern=pattern, sensitivity=sensitivity, mode=mode)
            except PolicyConfigError as exc:
                errors.append(f"{t.identity}: {exc}")
                continue
            write_rule(self._policy_path, rule)
            written.append(t.identity)

        if errors and not written:
            self.query_one("#allow-error", Static).update("; ".join(errors))
            return
        self.dismiss(self._entry)

    def action_dismiss_review(self) -> None:
        self.dismiss(None)


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
        # 2026-07-30 (direct user report: "monitor decisions not persisting
        # across sessions"): all 4 paths default to cwd-relative (same as
        # scalene-guard's own hook-adapter defaults) -- correct for a hook
        # Claude Code invokes from a fixed project root, but `scg monitor`
        # is launched by hand in a separate terminal, where a different cwd
        # between runs silently points it at a different .scalene/ and
        # scalene_policy.yaml entirely, indistinguishable from "it forgot".
        # Resolving to absolute here (not changing the *default values*,
        # just making whichever cwd was active at launch explicit) and
        # showing it in sub_title turns a silent mismatch into a visible
        # one -- see monitor.py's new --policy-path/--cache-path/etc. flags
        # for how an operator pins this explicitly instead.
        state_dir = Path(state_dir).resolve()
        audit_log_path = Path(audit_log_path).resolve()
        cache_path = Path(cache_path).resolve()
        policy_path = Path(policy_path).resolve()
        self._state_dir = state_dir
        self._audit_log_path = audit_log_path
        self._tail = AuditTail(audit_log_path)
        self._cache_path = cache_path
        self._policy_path = policy_path
        self.sub_title = f"policy: {policy_path}  |  state: {state_dir}"
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
            new_items = self._tail.poll()
            if new_items:
                new_events = [i for i in new_items if isinstance(i, ToolCallEvent)]
                self._events.extend(new_events)
                self.refresh_events()
                new_reviews = False
                # 2026-07-30 (direct user report: "review status is not
                # persisted -- always resets to N pending reviews on
                # restart"): processed in file order, same as a live
                # in-session Deny/Allow already worked -- a `block` tentatively
                # queues a review, a later `review_resolved` for that exact
                # event (by log_offset, its stable identity) dequeues it
                # again. A fresh restart's first poll() re-reads the whole
                # log from byte 0, so this now correctly nets out anything
                # already resolved in a previous session, not just this one.
                for item in new_items:
                    if isinstance(item, ToolCallEvent):
                        if item.event == "block":
                            self._pending_reviews.append(build_review_entry(item, self._scanners))
                            new_reviews = True
                    elif isinstance(item, ReviewResolution):
                        self._pending_reviews = [
                            r for r in self._pending_reviews if r.event.log_offset != item.resolved_offset
                        ]
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
        # docstring). Next/Prev inside the screen then lets the operator
        # browse the rest of the queue (and see "Review X of Y") without
        # closing and reopening.
        if self._pending_reviews:
            self.push_screen(
                ReviewScreen(self._pending_reviews, 0, self._cache_path, self._scanners, self._policy_path),
                callback=self._on_review_resolved,
            )

    def _on_review_resolved(self, resolved_entry: ReviewEntry | None) -> None:
        # ReviewScreen reports back the entry that was actually
        # Denied/Allowed -- not necessarily the one this screen was opened
        # with, since Next/Prev may have moved elsewhere in the queue first.
        # `None` (plain Escape) leaves it queued -- same "ignoring it just
        # leaves it queued" model as the rest of this design.
        if resolved_entry is not None and resolved_entry in self._pending_reviews:
            self._pending_reviews.remove(resolved_entry)
            # 2026-07-30 (direct user report: "review status is not
            # persisted -- always resets to N pending reviews on restart"):
            # record that this exact block event (identified by its own
            # stable log_offset) was actually dealt with, to the same real
            # audit.log a restart re-reads from byte 0 -- poll_data() nets
            # this back out against the original `block` event, so it
            # doesn't silently reappear next time.
            append_audit_log(
                {"event": "review_resolved", "resolved_offset": resolved_entry.event.log_offset},
                self._audit_log_path,
            )
        self._refresh_review_title()

    def _refresh_review_title(self) -> None:
        count = len(self._pending_reviews)
        self.title = f"scg monitor — {count} pending review{'s' if count != 1 else ''}" if count else "scg monitor"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        if event.data_table.id == "sessions":
            self.selected_session_id = str(event.row_key.value)
            self.refresh_events()
