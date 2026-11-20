# `*user consult` — Queue-First Monitor Redesign (2026-07-30)

## Request (direct user, verbatim intent)

Redesign `scg monitor`'s UX to revolve around the approval queue:
1. Remove session selection — always track the latest session, since that's
   what's relevant to what the developer is currently doing.
2. Screen 1: a summary of the top items in the queue (tool name, # matching
   resources, etc.) — arrow-key navigation, selecting an item opens the
   approval screen.
3. Approval screen: put the match expression at the top; the resource list
   should indicate whether each resource currently matches the (possibly
   edited) expression.
4. Screen 2: the rule list, with reordering controls.

## Grounding — what actually exists today (checked against real code)

- **The queue is already session-agnostic.** `poll_data()`
  (`monitor_app.py:625-668`) appends every `block` event to
  `_pending_reviews` regardless of `session_id` — it's never filtered by
  `selected_session_id`. Removing session selection costs nothing on the
  queue itself; no review becomes hidden or lost. What actually goes away is
  the **events-log panel's** session filter (`refresh_events`, `'a'`
  toggle-all-sessions binding) and the **Sessions table** (`compose()`
  lines 556-559, `refresh_sessions()`).
- **"Latest session" is buildable but today's code is sticky, not live.**
  `selected_session_id` is set once (`if self.selected_session_id is None
  and sessions:`, line 611) and never re-points at a newer session
  afterward. `discover_sessions()` (`monitor_data.py:135`) already returns
  recent-first by `updated_at`, so "latest" is `discover_sessions()[0]` —
  the fix is dropping the `is None` guard, not new data plumbing.
- **The queue already has everything needed for a summary row.**
  `ReviewEntry` (`monitor_data.py:80`) holds `event.tool_name` and
  `targets: list[Resource]` — `len(entry.targets)` is the "# matching
  resources" the request asks for, no new field needed.
- **Arrow-nav-to-select is already the exact mechanism `action_open_review`
  hardcodes to index 0.** `DataTable` with `cursor_type = "row"` (used
  identically for `sessions`/`events`/`scan-results` today) plus
  `on_data_table_row_selected` is the established pattern in this same file
  — a queue table just needs the same wiring, selecting by row index into
  `_pending_reviews` instead of always opening index 0.
- **The pattern field is currently gated behind clicking Allow.**
  `ReviewScreen.compose()` builds `#allow-form` (containing
  `#rule-pattern-input`) as a `Vertical` with `display = False`
  (`monitor_app.py:265`), only shown via `on_button_pressed`'s `allow-btn`
  branch (line 348-353). "Put the match expr on top" means promoting this
  out from behind that gate, not just a visual reposition.
- **Matching is already a single, reusable call, not something to
  reimplement.** `Scanner.match(rule, resource)` (`scanner.py:151,236`) is
  the one place gitignore-vs-regex dispatch lives (FileScanner reads
  gitignore syntax, everything else plain regex — `escape_gitignore_literal`
  docstrings, `policy_config.py:71-78`). `action_submit_allow` already
  builds a transient `PolicyRule` from the live form values before writing
  it (lines 450-451) — a live-preview column reuses that exact
  rule-construction + `Scanner.match()` call, just without the `write_rule`
  step, so there is no second matcher to drift out of sync with the real one
  (this project has hit that failure class before: `ReviewEntry`'s removed
  parallel-verified-flag bug, this same file's own docstring at
  `monitor_data.py:87-100`).
- **Rule order is not cosmetic — it's precedence.** Both
  `write_default_project_policy`'s docstring (`policy_config.py:265-269`)
  and `onboard.py::write_rule`'s insert-before-not-append behavior exist
  specifically because `_find_matching_rule()` returns the **first**
  declaration-order match. A rule-reorder screen is a real access-control
  control surface, not a display feature — reordering must rewrite
  `scalene_policy.yaml`'s `rules:` list in the new order, through a real,
  tested function, the same class of thing `write_rule` already is.
- **No existing screen shows the rule list at all today.** `PolicyConfig`
  is loaded once at `MonitorApp.__init__` (line 543) and only consulted for
  `self._scanners` — the rules themselves (`config.rules`) are read by
  `resource_verifier.py` at hook-decision time, never displayed anywhere in
  the monitor. This is a genuinely new screen, not a rewire of an existing
  one.

## Proposed design

### Screen 1 — Queue (replaces the Sessions/Events/Scanners 3-panel dashboard)

```
scg monitor — 3 pending reviews          session: a1b2c3 (trust=low, sensitivity=internal)
┌─────────────────────────────────────────────────────────────────────────┐
│ Tool        Resources   Kind         Reason                       Age   │
│ WebFetch    1           url          untrusted destination        2m    │
│ Read        3           file         possible AWS key              12s  │
│ Bash        1           file         uncleared                     41s  │
└─────────────────────────────────────────────────────────────────────────┘
↑↓ navigate · Enter approve · R rules · a all sessions (if events kept)
```

- One `DataTable`, `cursor_type="row"`, columns **Tool | Resources | Kind |
  Reason | Age** — all derivable from `ReviewEntry`/`ToolCallEvent` today,
  no new data collection.
- Sort oldest-first (same FIFO the existing `'r'` binding already uses) —
  keeps "top of queue" meaning "longest-waiting," a real, stable ordering
  rather than something that reshuffles under the cursor as new blocks
  arrive.
- `Enter` on a row opens `ReviewScreen` at that row's index — literally
  today's `action_open_review`, just parameterized by cursor position
  instead of hardcoded `0`.
- Session line replaces the Sessions table: one line, tracks
  `discover_sessions()[0]` live every poll (the sticky-selection fix
  above), `_NO_SESSIONS_MESSAGE` unchanged for the zero-sessions case.
- Empty state: `"No pending reviews."` — Nielsen #1, don't show a blank
  table with no explanation.

**Flagged, not decided by me:** the request only describes two screens
(queue, rules) plus the approval drill-down — nothing preserves the
Scanners panel or Resource-cache panel. I'm proposing to drop both from the
default view rather than guess you want them kept. Real tradeoff to name
explicitly: the Scanners panel is the only place "is a scan actually
running" is visible today, and I flagged that exact signal as a Gate 1 hard
requirement last sprint (dashboard attention/status visibility, E16 Gate 1).
Dropping it isn't wrong, but it's a real regression unless something
replaces it — cheapest fix, if you want it back, is a one-line status
strip ("2 scans in progress") rather than the full panel, not a blocking
concern either way. Say the word and I'll fold it back in.

Also worth naming, not re-litigating: I flagged concurrent-multi-session
use as real and worth explicit support back at Sprint 2 Gate 1 (devs
running more than one agent session at once). This redesign doesn't lose
any *review* — the queue was never session-scoped — it only removes the
ability to browse a specific *older* session's allow/block event history
from this screen. If that history view still matters to you, it's a
"press a key to open a scrollback for session X" feature, not something
this design silently forecloses.

### Approval screen — match expression promoted to the top

```
Review 1 of 3                                              < Prev  Next >
Tool: [ WebFetch                    ]  Pattern: [ https://api\.example\.com/.* ]
Sensitivity: (•)public ( )internal ( )restricted   Mode: (•)allow ( )mask ( )block

Target                          Kind   Status              Verified  Matches?
https://api.example.com/v2/x    url    not yet scanned      no        yes
https://api.example.com/v1/y    url    not yet scanned      no        yes
https://evil.example.net/z      url    not yet scanned      no        no

[ Verify ]  [ Deny ]  [ Allow (disabled until all Verified) ]
```

- Tool/Pattern/Sensitivity/Mode move up to sit directly under the nav row,
  always visible and editable — not revealed only after clicking Allow.
  Verify/Deny/Allow stay where they are, gated exactly as today
  (`all_verified()` still the only thing that unlocks Allow — this doesn't
  loosen that Nielsen #5 guard, only when the pattern becomes visible).
- New **Matches?** column, recomputed on every keystroke in the Pattern
  field (`on_input_changed`, same event Textual already fires) via
  `Scanner.match()` against a transient `PolicyRule` built from the live
  form values — identical construction to what `action_submit_allow`
  already does at submit time, just called earlier and read-only.
- Multi-target payoff this specifically unlocks: today, widening a pattern
  for a multi-target call is a guess — you type, submit, and only find out
  which targets it covered after the fact. Live-preview means you see
  "covers targets 1-2, not 3" before committing.

### Screen 2 — Rules (new)

```
scg monitor — rules (scalene_policy.yaml)
┌─────────────────────────────────────────────────────────────────────────┐
│ #  Tool   Pattern                          Sensitivity  Mode   Trust     │
│ 1  .*     /home/you/project /home/you/…    internal     allow  high      │
│ 2  Bash   /etc/**                          restricted   block  high      │
│ 3  .*     https://api\.example\.com/.*     public       allow  high      │
└─────────────────────────────────────────────────────────────────────────┘
↑↓ select · K move up · J move down · Esc back to queue
```

- One `DataTable` row per `PolicyRule`, in file order (order = column #1,
  shown explicitly so "first match wins" is visible, not implicit).
- `K`/`J` (or equivalent) swap the selected row with its neighbor and
  rewrite `rules:` in the new order — a real, tested function alongside
  `write_rule`, not a display-only sort. The other 6 `PolicyRule` fields
  round-trip unchanged.

**One real concern, not cosmetic:** reordering has live access-control
consequences the instant it's written (a rule moved below a broader one can
make it permanently unreachable — literally the exact failure
`write_default_project_policy`'s docstring warns about for appends). I'd
want at minimum a visible confirmation of what changed before the write
lands (e.g. an inline "swapped #2 ↔ #3 — saved" toast), not a silent
same-tick rewrite with no feedback trail — Nielsen #1 and #5 both apply
here: this is the one part of this whole redesign that can silently make an
existing allow rule stop working.

## Status

Design discussion only — no code changed, no stories written. This is
multi-screen (new queue-first main screen, new rules screen, a real
behavior change to the review screen's layout and gating surface, a new
rule-reorder write path) — sprint-scale, same shape as the E16 consult that
became a 6-story epic, not a single-file tweak. My one open flag (drop vs.
keep Scanners/Resource-cache panels) is the only piece I'd want confirmed
before this becomes stories; everything else here is groundable directly
against the code that exists today.
