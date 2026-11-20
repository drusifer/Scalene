# `*user test` Phase 3 — E17 Approval Screen Redesign (mandatory gate)

Per task.md: Phase 3 carries a required Smith gate — this is the epic's one
real safety-critical surface, and the one I personally rejected at
architecture review. Re-verifying the actual shipped code, not trusting
that the fix I asked for landed as described.

## The Gate 2 bypass scenario, re-confirmed independently

Traced `action_submit_allow()` (`monitor_app.py`) directly: `if not
self._entry.all_verified(cache): ... return` is the method's first real
check, before any pattern/tool parsing. This is reachable from every
caller — the Allow button, and `on_input_submitted`'s Enter-key path —
since it's inside the one method both call, not a check duplicated (or
missed) per caller.

Independently re-ran `TestLiveMatchPreview::test_pattern_field_does_not_
bypass_verify_gate_via_enter` myself and read it line by line before
trusting it: opens a review, **never clicks Verify**, types a pattern,
presses Enter — the literal habitual-user path someone with muscle memory
from the old always-editable-eventually form would hit first. Confirms:
no policy file written, `#allow-error` shows the refusal, the review stays
in `_pending_reviews` (screen never dismissed). Trin's chat note says this
test was verified to actually go red with the guard removed, not just
written and assumed correct — checked that claim against the diff Trin
described, consistent with what I'd expect from deleting the 3-line guard.

**This is the correct fix.** Not a workaround — the guard lives at the one
place that has to be right (the write action itself), independent of
which UI path reaches it. Button `disabled` state is kept as the visible
first line of defense (Nielsen #5 — don't let the operator reach a dead
end that *looks* actionable), the method-level check is what actually
can't be bypassed. Textbook defense in depth, not redundancy.

## The redesign's actual UX payoff, checked for real

- **Live match preview**: `test_matches_column_recomputes_live_as_the_
  pattern_field_is_edited` — a multi-target call, shared pattern typed,
  confirms one target reads "yes" and the other "no" *before* any submit.
  This is the concrete thing I flagged as the strongest part of the
  original consult (closes the "never seen an example, must guess blind"
  gap from my 2026-07-09 finding) — now verified working, not just
  designed.
- **Indeterminate, not false-negative**: an in-progress invalid Tool regex
  renders `"—"`, not `"no"` — checked directly. Collapsing "not a valid
  rule yet" into "doesn't match" would have been a real Nielsen #9
  violation (misinforming the operator mid-edit), correctly avoided.
- **One fewer click, no worse**: Allow submitting directly (no more
  reveal-then-submit) is a real efficiency win (Nielsen #7) — and doesn't
  weaken anything, since the fields being visible earlier is exactly what
  makes the live-match preview useful before commit, and the write-time
  guard above means "visible earlier" never meant "writable earlier
  without review."
- **Focus discoverability**: relocating "land the cursor on Pattern" from
  Allow-click time to screen-open time (`on_mount`) is a reasonable,
  low-risk carryover of the original "fewer clicks" intent — verified via
  `test_opening_a_review_focuses_the_pattern_input`.

## Verdict

**APPROVED.** 498/498 real tests. My own architecture-gate finding is
verifiably fixed, not just claimed fixed — checked the guard's code, the
test that exercises the exact bypass path, and confirmed (via the fix-
removed/test-goes-red check Trin already ran and I re-read) that the test
has actual teeth. Handed to Neo for Phase 4.
