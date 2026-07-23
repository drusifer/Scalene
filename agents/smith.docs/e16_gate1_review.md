# `*user review` Gate 1 — E16 (2026-07-22)

Reviewing STORY-1601 through 1606 (`docs/USER_STORIES.md`) against HCI
principles and testability. Checked `agents/oracle.docs/lessons.md` first
per Artifacts-First habit — the 2026-07-15 lesson "A Row-Content Check Is
Not a Rendering Check" (`monitor_app.py`'s Last-Scanned truncation bug,
found only by a real rendered screenshot) applies directly to this epic's
new TUI surfaces (STORY-1603's tagged log, STORY-1604's dashboard) and is
carried into this review as a Gate 2/UAT requirement, not just a note.

## Verdict: Approved with notes

All 6 stories are testable and correctly scoped — this is a faithful,
grounded formalization of the consult I already vetted
(`agents/smith.docs/e16_onboarding_tui_consult.md`), not new invention.
Confirmed both of my own hard consult concerns are resolved by construction
here: STORY-1601 never touches `pre_tool_use`'s contract (explicit AC line),
and STORY-1602/1604 correctly cite `ScanCache.is_fresh()` as already
existing rather than inventing new vocabulary.

## Non-blocking notes

1. **STORY-1604 needs an explicit "needs your attention" signal, not just a
   dashboard that exists if you happen to be looking.** The user's own
   framing goal is allow-list impact being "plainly obvious" — a dashboard
   that silently appears in a TUI the operator isn't currently looking at
   fails Nielsen #1 exactly the way a silent state change always does in
   this project's history (the focus-loss bug, the cursor-desync bug — both
   real bugs I found by testing the *actual* interaction, not the data
   model). Recommend Morpheus/Mouse fold in a lightweight attention cue
   (terminal bell, title-bar change, or equivalent) as part of STORY-1604's
   scope, not a separate story — it's cheap and this project has been
   burned by "the data is right, the user just couldn't tell" before.
2. **Multiple simultaneous block events aren't addressed.** STORY-1604
   doesn't say what happens if two calls block before the operator resolves
   the first (multiple sessions, or a batch call). Not blocking Gate 1 —
   architecture-shaped, not product-shaped — but Morpheus should decide
   queue-vs-list explicitly rather than it falling out of implementation
   incidentally.
3. **Carrying the rendering-check standard forward explicitly**: whoever
   UATs STORY-1603 (tagged log) and STORY-1604 (dashboard) must verify via
   a real rendered screenshot at a realistic terminal width, the same
   standard `phase5_bug_last_scanned_truncation.md` established — a
   DataTable content/row-count check would not have caught that bug and
   won't catch an equivalent one here (e.g. tag markers or dashboard fields
   getting squeezed out at narrower widths than assumed).

None of these block Gate 1 — they're carried to Gate 2 (architecture) and
UAT respectively, same pattern as every prior sprint's non-blocking notes.

## Approved

@Morpheus for architecture. My hard-requirement watch-items for Gate 2:
STORY-1606's concrete read-only-boundary mechanism (open question #1) and
whichever attention-signal design Morpheus picks for note #1 above.
