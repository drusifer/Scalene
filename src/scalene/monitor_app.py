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

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.css.query import NoMatches
from textual.screen import Screen
from textual.widgets import Button, DataTable, Footer, Header, Input, RadioButton, RadioSet, Static

from .hook_adapter import DEFAULT_AUDIT_LOG, append_audit_log
from .monitor_data import (
    AuditTail,
    ReviewEntry,
    ReviewResolution,
    ToolCallEvent,
    build_review_entry,
    discover_scanner_activity,
    discover_sessions,
    format_scanner_status,
    target_status,
)
from .onboard import BLOCKED_LABELS, write_rule
from .policy_config import (
    VALID_RULE_MODES,
    VALID_SENSITIVITIES,
    PolicyConfig,
    PolicyConfigError,
    PolicyRule,
    swap_rule_order,
)
from .resource_verifier import is_validated_allow
from .scan_cache import DEFAULT_CACHE_PATH, ScanCache
from .scanner import Resource, ScannerMachineryError, escape_gitignore_literal
from .taint_state import DEFAULT_STATE_DIR

# docs/ARCHITECTURE.md sec 11.2: poll, don't filesystem-watch.
POLL_INTERVAL_SECONDS = 0.5

# Same duplicated-by-convention constant as cli.py/onboard.py (both define
# their own DEFAULT_POLICY_PATH rather than sharing one) -- matches existing
# precedent rather than introducing a new cross-module dependency for it.
DEFAULT_POLICY_PATH = Path("scalene_policy.yaml")

_NO_SESSIONS_MESSAGE = "No sessions found yet. Run an agent session with scalene-guard installed, then reopen the monitor."

# docs/ARCHITECTURE.md sec22.6: STORY-1701 retires the full allow/block
# tagged call-stream panel (STORY-1603, E16) entirely -- the queue only ever
# holds blocks, and only until resolved, so there is no more "every call,
# tagged" surface anywhere in this app. `_event_tag`/`_TAG_TEXT`/`_TAG_STYLE`
# (the machinery that rendered that panel's per-row tag) are removed as
# dead code along with it, not left behind unused.


def _format_kinds(targets: list[Resource]) -> str:
    """docs/ARCHITECTURE.md sec22.2 (STORY-1701): the queue's Kind column --
    a call can identify more than one resource kind at once (e.g. a Bash
    command touching both a file path and a URL), so this joins the
    distinct kinds actually present rather than assuming one."""
    return ", ".join(sorted({t.kind for t in targets}))


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
        children" -- still true regardless of where it sits in the layout,
        which is why this stays even after sec22.4 (E17) moved #allow-form
        *before* #targets. Original trigger (E16): a 2-row #targets table
        shrank allow-form's 1fr share, silently compressing its content
        until #allow-error overlapped the (now-removed) #submit-btn's row,
        swallowing clicks with no error. */
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
        # docs/ARCHITECTURE.md sec22.4 (STORY-1704, direct user request): the
        # match-expression fields sit at the top, always visible/editable --
        # not revealed only after clicking Allow (the old 2-step reveal-
        # then-submit). Allow itself is now the direct write action; there
        # is no longer a separate "Submit rule" button.
        with Vertical(id="allow-form"):
            # `tool` is call-level (one value for the whole entry, every
            # target in one call shares the same tool_name) so it's always
            # editable; `pattern` is inherently per-target, so it's only
            # meaningfully editable when there's exactly one target (see
            # _refresh_allow_form_defaults) -- multi-target calls keep
            # today's automatic per-target derivation, shown disabled
            # rather than silently ignored.
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
        yield Static("", id="tool-input")
        yield DataTable(id="targets")
        with Horizontal():
            yield Button("Verify", id="verify-btn", compact=True)
            yield Button("Deny", id="deny-btn", compact=True)
            # docs/ARCHITECTURE.md sec20.4: Allow is disabled/unreachable
            # until every target's Verify has completed -- Textual's own
            # `disabled` state, not just a visual hint the user could
            # click past. sec22.4 (Smith's Gate 2 finding): this button
            # state is the *visible* first line of defense, not the only
            # one -- action_submit_allow() below re-checks all_verified()
            # itself, since the Enter-key path reaches it independent of
            # this button's state.
            yield Button("Allow", id="allow-btn", disabled=True, compact=True)
        yield Static("", id="allow-error")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#targets", DataTable)
        table.add_columns("Target", "Kind", "Status", "Verified", "Matches?")
        self.refresh_header()
        self.refresh_targets()
        # Fewer clicks/steps (direct user request, carried from the old
        # reveal-on-Allow-click behavior sec22.4 retires): land the cursor
        # on the field the operator is most likely to edit as soon as the
        # screen opens, since there's no longer a separate reveal step to
        # do it at.
        self.query_one("#rule-pattern-input", Input).focus()

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

    def _build_rule(self, pattern: str) -> PolicyRule:
        """docs/ARCHITECTURE.md sec22.4 (STORY-1704): the one place a
        `PolicyRule` is constructed from the live form values -- both the
        real write path (`action_submit_allow`) and the read-only live
        preview (`_preview_matches`) call this, so there is no second,
        divergent construction to drift out of sync with the one that
        actually gets written. May raise `PolicyConfigError` (e.g. an
        in-progress edit to the Tool field that isn't valid regex yet) --
        callers decide how to handle that themselves."""
        tool = self.query_one("#rule-tool-input", Input).value.strip() or self._entry.event.tool_name
        sensitivity = self._selected_radio_value("sensitivity-radio", VALID_SENSITIVITIES, "public")
        mode = self._selected_radio_value("mode-radio", VALID_RULE_MODES, "allow")
        return PolicyRule(tool=tool, pattern=pattern, sensitivity=sensitivity, mode=mode)

    def _preview_matches(self, target: Resource) -> str:
        """docs/ARCHITECTURE.md sec22.4 (STORY-1704): does the *current*
        (possibly unsaved) pattern field value match this target? Reuses
        the exact same scanner dispatch (`Scanner.match()` -- FileScanner's
        gitignore override vs. the base regex default) the real write path
        already relies on, not a second matcher. `"—"` (indeterminate, not
        "no") for an in-progress edit that isn't a valid rule yet -- that's
        a different claim than "this valid rule doesn't match," and
        collapsing the two would misinform the operator."""
        edited_pattern = self.query_one("#rule-pattern-input", Input).value.strip()
        pattern = edited_pattern or self._default_pattern_for(target)
        try:
            rule = self._build_rule(pattern)
        except PolicyConfigError:
            return "—"
        scanner = self._scanners.get(target.scanner_name)
        if scanner is None:
            return "—"
        return "yes" if scanner.match(rule, target) else "no"

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
        # don't carry over a previous entry's defaults or error text.
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
            table.add_row(t.identity, t.kind, status, verified, self._preview_matches(t))
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
            # docs/ARCHITECTURE.md sec22.4 (STORY-1704): Allow is the direct
            # write action now -- the match-expr fields are already visible
            # and editable above, there's no form left to reveal.
            self.action_submit_allow()
        elif event.button.id == "prev-btn":
            self.action_prev_review()
        elif event.button.id == "next-btn":
            self.action_next_review()

    def on_input_changed(self, event: Input.Changed) -> None:
        # docs/ARCHITECTURE.md sec22.4 (STORY-1704): live "Matches?" preview
        # -- recomputed on every keystroke in the Pattern field. Not wired
        # on the Tool field: `Scanner.match()` only ever reads `rule.
        # pattern`, never `rule.tool` (confirmed: `Scanner.match`/
        # `FileScanner.match`), so a tool-field edit can't change any row's
        # match result -- wiring it would be a no-op call, not a
        # correctness gap.
        if event.input.id == "rule-pattern-input":
            self.refresh_targets()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        # Fewer clicks/steps: Enter in either text field submits the rule
        # directly, same as clicking Allow -- no mouse required.
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
        # docs/ARCHITECTURE.md sec22.4 (Smith's Gate 2 finding): the match-
        # expr fields are always visible/focusable now, before Verify has
        # necessarily run -- Enter in either text input (on_input_submitted)
        # reaches this method directly, independent of the Allow button's
        # own disabled=all_verified() state. That button state is the
        # visible first line of defense (Nielsen #5); this check is the one
        # that actually can't be bypassed, since it's enforced at the write
        # action itself, not at a widget that isn't the only path here.
        cache = ScanCache(self._cache_path)
        if not self._entry.all_verified(cache):
            self.query_one("#allow-error", Static).update("Verify every target before allowing.")
            return

        # docs/ARCHITECTURE.md sec20.5 (STORY-1605): default pattern escapes
        # the identity as a literal, exact match -- onboard.py's own
        # existing default, reused verbatim, not a new derivation. Same
        # BLOCKED_LABELS guard onboard._onboard_resource applies, checked
        # against the result Verify already cached -- no re-scan here.
        # 2026-07-30 (Scanner.match()): escaping syntax must match whichever
        # scanner will interpret the pattern -- FileScanner ("secrets")
        # reads gitignore syntax, everything else still reads plain regex.
        edited_pattern = self.query_one("#rule-pattern-input", Input).value.strip()
        mode = self._selected_radio_value("mode-radio", VALID_RULE_MODES, "allow")

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
                rule = self._build_rule(edited_pattern)
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
                rule = self._build_rule(pattern)
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


class RulesScreen(Screen):
    """docs/ARCHITECTURE.md sec22.5 (STORY-1705): lists every `PolicyRule`
    in real file order (rule order is genuine access-control precedence --
    `resource_verifier._find_matching_rule()` returns the first match, not
    the best one) with move-up/move-down controls that actually rewrite
    `scalene_policy.yaml` via `policy_config.swap_rule_order`, not a
    display-only sort.

    `k`/`j` (not the arrow keys, which `DataTable`'s own cursor already
    owns) move the rule under the cursor. Re-reads the real file after
    every write and shows a synchronous confirmation before accepting the
    next key -- reordering has immediate, real access-control consequences
    (a broad rule moved ahead of a specific one can make the specific one
    permanently unreachable, the exact failure `write_default_project_
    policy`'s own docstring warns about for appends), so the write must
    never be silent."""

    BINDINGS = [
        ("escape", "back_to_queue", "Back to queue"),
        ("k", "move_up", "Move rule up"),
        ("j", "move_down", "Move rule down"),
    ]

    CSS = """
    RulesScreen #no-rules { padding: 1 2; color: $text-muted; display: none; }
    RulesScreen #no-rules.visible { display: block; }
    """

    def __init__(self, policy_path: Path) -> None:
        super().__init__()
        self._policy_path = policy_path

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static("No rules configured.", id="no-rules")
        yield DataTable(id="rules")
        yield Static("", id="rule-confirm")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one("#rules", DataTable)
        table.add_columns("#", "Tool", "Pattern", "Sensitivity", "Mode", "Trust")
        table.cursor_type = "row"
        self.refresh_rules()

    def _load_rules(self) -> tuple[PolicyRule, ...]:
        try:
            return PolicyConfig.from_yaml(self._policy_path).rules if self._policy_path.exists() else ()
        except PolicyConfigError:
            # Fail-safe, not fail-crash: this is a live TUI (same standard
            # as ReviewScreen.action_verify) -- an invalid policy file
            # shows an empty rules list rather than taking the screen down.
            return ()

    def refresh_rules(self) -> None:
        table = self.query_one("#rules", DataTable)
        table.clear()
        rules = self._load_rules()
        # Nielsen #1: an empty table with no explanation reads as "broken,"
        # same disposition as #no-queue (sec22.2) -- explicit, not silent.
        self.query_one("#no-rules", Static).set_class(not rules, "visible")
        for i, rule in enumerate(rules):
            table.add_row(str(i + 1), rule.tool, rule.pattern, rule.sensitivity, rule.mode, rule.trust)

    def _move(self, direction: int) -> None:
        table = self.query_one("#rules", DataTable)
        index = table.cursor_row
        total = table.row_count
        other = index + direction
        if index < 0 or other < 0 or other >= total:
            return  # at the boundary -- no-op, same as ReviewScreen's disabled-button precedent
        try:
            swap_rule_order(self._policy_path, index, direction)
        except PolicyConfigError as exc:
            self.query_one("#rule-confirm", Static).update(str(exc))
            return
        self.refresh_rules()
        table.move_cursor(row=other)
        # Synchronous confirmation, same handler that performed the write --
        # no frame where the operator could act again before seeing what
        # happened (STORY-1705's hard AC).
        self.query_one("#rule-confirm", Static).update(f"Moved rule #{index + 1} → #{other + 1} — saved.")

    def action_move_up(self) -> None:
        self._move(-1)

    def action_move_down(self) -> None:
        self._move(1)

    def action_back_to_queue(self) -> None:
        self.dismiss()


class MonitorApp(App):
    """docs/ARCHITECTURE.md sec22 (E17, STORY-1701/1702): queue-first home
    screen -- a table of pending reviews (oldest first) plus a single line
    naming whichever session is currently most active, not a multi-session
    dashboard with a picker. sec15 (2026-07-17): STORY-702's editable-and-
    applyable onboard-command workflow is retired -- clearing a destination
    always takes two explicit steps (a real scan, then a hand-authored
    rule), not one runnable command."""

    CSS = """
    #no-sessions { padding: 1 2; color: $text-muted; display: none; }
    #no-sessions.visible { display: block; }
    #session-line { padding: 0 1; color: $text-muted; }
    #no-queue { padding: 1 2; color: $text-muted; display: none; }
    #no-queue.visible { display: block; }
    /* docs/ARCHITECTURE.md sec22.3 (STORY-1703): real-rendered-geometry
    check (Phase 2 Trin/Morpheus finding) caught this differently than the
    architecture doc assumed -- two `dock: bottom` widgets don't stack
    outward from the edge, they fully overlap at the same region. Fix:
    #queue expands to fill remaining vertical space (1fr) and #status-strip
    is left in normal flow (not docked) -- it's simply the next line after
    the now-flexible queue table, landing exactly above Footer's own
    self-docked bar with no overlap, no explicit dock needed on the strip.
    */
    #queue { height: 1fr; }
    #status-strip { height: 1; padding: 0 1; color: $text-muted; }
    """
    BINDINGS = [("r", "open_rules", "Rules")]

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
        # docs/ARCHITECTURE.md sec22.2 (STORY-1701/1702): the queue is the
        # whole home screen now -- no Sessions/Events/Scanners/Resource-
        # cache panels (STORY-1701's own AC removes them; the scanner-
        # activity signal returns in sec22.3's status strip, everything
        # else is dropped outright, not replaced).
        yield Header()
        yield Static(_NO_SESSIONS_MESSAGE, id="no-sessions")
        yield Static("", id="session-line")
        yield Static("No pending reviews.", id="no-queue")
        yield DataTable(id="queue")
        yield Static("", id="status-strip")
        yield Footer()

    def on_mount(self) -> None:
        queue_table = self.query_one("#queue", DataTable)
        queue_table.add_columns("Tool", "Resources", "Kind", "Reason", "Age")
        queue_table.cursor_type = "row"

        self.refresh_session_line()
        self.refresh_queue()
        self.refresh_status_strip()
        self._refresh_review_title()
        self.set_interval(POLL_INTERVAL_SECONDS, self.poll_data)

    def refresh_status_strip(self) -> None:
        # docs/ARCHITECTURE.md sec22.3 (STORY-1703): reuses discover_
        # scanner_activity() verbatim (STORY-1602's own data source) --
        # only the rendering (a strip line, not a table) is new.
        activity = discover_scanner_activity(self._cache_path, self._scanners)
        self.query_one("#status-strip", Static).update(format_scanner_status(activity))

    def refresh_session_line(self) -> None:
        # docs/ARCHITECTURE.md sec22.2 (STORY-1702): recomputed fresh from
        # `discover_sessions()[0]` on every call -- no stickiness. A prior
        # `selected_session_id` field used to be set once (`is None` guard)
        # and never re-point at a newer session; there is no equivalent
        # state here to go stale, by construction.
        sessions = discover_sessions(self._state_dir)
        no_sessions_widget = self.query_one("#no-sessions", Static)
        no_sessions_widget.set_class(not sessions, "visible")

        line = self.query_one("#session-line", Static)
        if sessions:
            latest = sessions[0]
            line.update(f"Session: {latest.session_id}  (trust={latest.trust}, sensitivity={latest.sensitivity})")
        else:
            line.update("")

    def poll_data(self) -> None:
        # The periodic poll timer can fire after the app has already started
        # tearing down (e.g. the user quit mid-tick) — the table widgets are
        # gone by then, and there's nothing meaningful left to refresh.
        try:
            new_items = self._tail.poll()
            if new_items:
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
                self.refresh_queue()
            self.refresh_session_line()
            self.refresh_status_strip()
        except NoMatches:
            pass

    def refresh_queue(self) -> None:
        # docs/ARCHITECTURE.md sec22.2 (STORY-1701): oldest-first, same FIFO
        # order `_pending_reviews.append()` already produces -- displayed
        # now instead of only ever consumed by the old 'r'-opens-oldest
        # binding.
        table = self.query_one("#queue", DataTable)
        table.clear()
        no_queue_widget = self.query_one("#no-queue", Static)
        no_queue_widget.set_class(not self._pending_reviews, "visible")
        for entry in self._pending_reviews:
            table.add_row(
                entry.event.tool_name,
                str(len(entry.targets)),
                _format_kinds(entry.targets),
                entry.event.reason,
                _format_relative_time(entry.event.timestamp),
            )

    def _on_review_resolved(self, resolved_entry: ReviewEntry | None) -> None:
        # ReviewScreen reports back the entry that was actually
        # Denied/Allowed -- not necessarily the one this screen was opened
        # with, since Next/Prev may have moved elsewhere in the queue first.
        # `None` (plain Escape) leaves it queued -- same "ignoring it just
        # leaves it queued" model as the rest of this design.
        if resolved_entry is not None and resolved_entry in self._pending_reviews:
            self._pending_reviews.remove(resolved_entry)
            self._append_review_resolved(resolved_entry)
            # 2026-07-30 (direct user request): a just-submitted Allow rule
            # (e.g. widened to cover a whole project folder) may now also
            # validate other still-queued reviews' targets -- a rule
            # declares intent, but per sec15.2 it's the cache confirming
            # clean that actually counts, so this only fires for targets
            # already scanned (e.g. E10's automatic first-sight background
            # refresh, or an earlier manual Verify), not a blanket "any
            # pattern match resolves it" shortcut.
            self._auto_resolve_now_covered_reviews()
        self._refresh_review_title()
        # docs/ARCHITECTURE.md sec22.2 (Morpheus's Phase 1 review): `#queue`
        # is a visible widget now (it wasn't when this method was written,
        # E16) -- without this, a Deny/Allow (or an auto-resolved second
        # entry) would sit stale on screen until the next 0.5s poll tick
        # happened to call refresh_queue() on its own.
        self.refresh_queue()

    def _append_review_resolved(self, entry: ReviewEntry) -> None:
        # 2026-07-30 (direct user report: "review status is not
        # persisted -- always resets to N pending reviews on restart"):
        # record that this exact block event (identified by its own
        # stable log_offset) was actually dealt with, to the same real
        # audit.log a restart re-reads from byte 0 -- poll_data() nets
        # this back out against the original `block` event, so it
        # doesn't silently reappear next time.
        append_audit_log({"event": "review_resolved", "resolved_offset": entry.event.log_offset}, self._audit_log_path)

    def _auto_resolve_now_covered_reviews(self) -> None:
        try:
            config = PolicyConfig.from_yaml(self._policy_path) if self._policy_path.exists() else PolicyConfig()
        except PolicyConfigError:
            return
        cache = ScanCache(self._cache_path)
        still_pending = []
        for entry in self._pending_reviews:
            if entry.targets and all(
                is_validated_allow(entry.event.tool_name, t, config, cache) for t in entry.targets
            ):
                self._append_review_resolved(entry)
            else:
                still_pending.append(entry)
        self._pending_reviews[:] = still_pending

    def _refresh_review_title(self) -> None:
        count = len(self._pending_reviews)
        self.title = f"scg monitor — {count} pending review{'s' if count != 1 else ''}" if count else "scg monitor"

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        # docs/ARCHITECTURE.md sec22.2 (STORY-1701): opens the review at
        # whichever row is under the cursor -- supersedes the old 'r'-opens-
        # oldest binding (index 0 was the only reachable one before, and
        # 'r' is freed for the Rules screen, sec22.1).
        if event.data_table.id == "queue" and event.cursor_row < len(self._pending_reviews):
            self.push_screen(
                ReviewScreen(self._pending_reviews, event.cursor_row, self._cache_path, self._scanners, self._policy_path),
                callback=self._on_review_resolved,
            )

    def action_open_rules(self) -> None:
        # docs/ARCHITECTURE.md sec22.5 (STORY-1705): sibling screen to
        # ReviewScreen, pushed from the queue directly (never pushed from
        # inside a review).
        self.push_screen(RulesScreen(self._policy_path))
