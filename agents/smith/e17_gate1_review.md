# `*user review` Gate 1 — E17 (Queue-First Monitor Redesign)

Reviewing Cypher's 5 stories (STORY-1701–1705, `docs/USER_STORIES.md`) against
my own `*user consult` (`e17_monitor_queue_first_consult.md`) that originated
this epic — checking they formalize what was actually grounded, not just
restate the request.

## Concerns from the consult — checked against the real ACs

- **Panel-drop question (my one open flag)**: resolved in the epic's Origin
  note by the user's own follow-up, not silently decided by Cypher — Scanners
  becomes STORY-1703's strip, Sessions/Resource-cache are dropped outright.
  Correctly recorded as resolved, not left as an open question for
  architecture.
- **Silent rule-reorder (my one real, not-a-flag concern)**: now a hard AC
  bullet on STORY-1705 — "followed by a visible, on-screen confirmation... **before
  the next input is accepted**." That's the actual protection (a queued
  keystroke can't race past the confirmation), not just "show a message
  eventually." Good.
- **Matcher duplication risk**: STORY-1704's AC explicitly requires reusing
  `Scanner.match()` + the same transient-`PolicyRule` construction
  `action_submit_allow` already does, "not reimplemented." Correct call —
  this project has a real history of two divergent stores/checks drifting
  apart (`ReviewEntry`'s removed parallel-verified-flag bug is the most
  recent).
- **Verify-gates-Allow must not loosen**: STORY-1704 says so explicitly.
  Good — moving the fields earlier in the layout is a real layout change and
  it would have been easy to accidentally imply the gate moved with it.

## Testability

All 5 stories have concrete, checkable ACs — specific columns, specific
copy strings (`"No pending reviews."`, `"Scanners: none configured"`), a
specific end-to-end verification for STORY-1705 (real 2-rule policy file,
reorder, re-run through the actual hook). No vague "should feel better"
criteria anywhere.

## Non-blocking notes (carried to Gate 2, not blocking here)

1. STORY-1701's **Reason** column reuses `ToolCallEvent.reason` verbatim —
   that string can be long (it's written for a human reading a block
   message, not a table cell). This project has already shipped one real
   truncation bug from an unbounded string in a bounded column (Sprint 4
   Phase 5, the "Last Scanned" panel). Not blocking — just don't assume it
   fits without checking a real render at a real terminal width, same
   standard as last time.
2. STORY-1702's session line concatenates id + trust + sensitivity on one
   line — a long session id combined with a narrow terminal has the same
   shape of risk as note 1. Same disposition: verify against a real
   screenshot before calling it done, don't eyeball it.

Neither is a hard requirement — both are "verify for real before Smith's
end-to-end pass," consistent with this project's own "screenshot-check UI
changes before approving" retro lesson (Sprint 4).

## Verdict

**APPROVED.** All ACs are testable and user-facing; every concern I raised
in the originating consult is either resolved by construction or carried
forward as an explicit AC, not dropped. No hard requirement blocking
architecture.
