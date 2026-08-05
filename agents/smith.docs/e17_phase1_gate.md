# `*user test` Phase 1 — E17 Queue-First Home Screen (mandatory gate)

Per task.md: Phase 1 carries a required Smith gate (primary-surface
replacement). Reviewed the real shipped code and the real Pilot-driven
tests exercising it (Textual's own documented headless harness — genuine
execution against the real `MonitorApp`, not a mock, same standard this
project has used since Sprint 2).

## Checked against my own carried notes (Gate 1)

Both non-blocking notes from `e17_gate1_review.md` (Reason column / session
line truncation risk) are resolved with a real screenshot check, not
eyeballed: `test_session_line_and_reason_column_are_not_truncated_at_a_
common_terminal_width` renders the actual app at 120 columns and asserts
the full session id and full reason string both appear in the exported
SVG's text nodes — the same technique that caught the real Sprint 4 Phase 5
truncation bug, applied proactively this time instead of after the fact.

## Core interaction, driven for real

- `test_selecting_a_non_first_queue_row_opens_that_review_not_the_oldest`:
  moves the cursor to row 1 and presses Enter — confirms the *second*
  queued review opens, not always the oldest. This is STORY-1701's actual
  point (the old `'r'` binding could only ever reach index 0) and it's
  verified through the real queue table + a real keypress, not by calling
  `push_screen` with an explicit index directly.
- `test_queue_spans_every_session_not_just_the_latest_one`: a block from an
  older session still appears in the queue even though the session line
  only ever names the latest one — confirms dropping session selection
  didn't quietly narrow what the queue shows, matching what the consult's
  code-grounding claimed.
- Empty states are explicit and distinguishable: `#no-sessions` (no
  sessions at all — reused verbatim copy) vs. `#no-queue` ("No pending
  reviews.") are two different messages for two different absences, not
  one generic "nothing here" — Nielsen #1 and #9, don't make two different
  situations look identical.

## Real bug caught at Morpheus's review, independently re-confirmed here

`_on_review_resolved` not calling `refresh_queue()` would have shipped a
real, first-use regression: Deny a review, and the just-resolved entry
stays visibly in the queue table for up to 500ms (or indefinitely for an
auto-resolved second entry, until the next unrelated poll tick happened to
redraw it) — exactly the kind of "did my action actually work?" doubt
Nielsen #1 exists to prevent. Re-ran `test_denying_a_review_removes_it_
from_the_queue_table_immediately` myself; genuinely passes against the
fixed code.

## Not blocking, carried forward (already flagged, not new)

- The full tagged allow/block call-stream (STORY-1603) and the Resource-
  cache panel (STORY-1005) are both permanently retired by this epic, not
  gapped temporarily — real capability loss, already named explicitly in
  the epic's Origin note and my own consult, not silently dropped here.
  Nothing new to add.
- Scanner-activity visibility is gone until Phase 2's status strip lands
  later this same sprint — expected, matches the phase plan I already
  approved at Gate 2.

## Verdict

**APPROVED.** 488/488 tests, all real (Pilot-driven, not mocked). Both my
carried notes are closed with evidence, not assumption. Handed to Neo for
Phase 2.
