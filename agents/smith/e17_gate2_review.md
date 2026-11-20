# `*user feedback` Gate 2 — E17 Architecture (docs/ARCHITECTURE.md §22)

## What's solid

- §22.2's `refresh_session_line()` fix (drop the `is None` guard) is exactly
  the one-line change my own consult identified — no scope creep.
- §22.3's `format_scanner_status` as a pure, `textual`-free function
  matches this module's own established testability boundary
  (`monitor_data.py`'s docstring: "stays testable without a terminal") —
  right call, not a new precedent.
- §22.4's live-match reuse of `Scanner.match()` via a shared helper (not a
  second matcher) is exactly what I flagged as the real risk in the
  original consult, and it's addressed by construction.
- §22.5's write-then-reread-then-confirm-before-next-input sequencing is
  precisely what closes my one real concern from the consult (a silent
  reorder). Correctly modeled as synchronous within the same handler, not
  "eventually consistent."

## Real concern — blocking, not a style note

**§22.4's "Allow becomes the direct write action" removes the *actual*
enforcement mechanism behind "Allow is disabled until Verify completes,"
not just its UI presentation.**

Traced `action_submit_allow()` as it exists today (`monitor_app.py:412-480`)
before raising this — it does **not** check `all_verified()` anywhere in its
own body. It only checks, per target, `cache.get(t)` against
`BLOCKED_LABELS` — and if a target has **never been scanned at all**
(`cache.get(t) is None`), that check is skipped entirely and the rule gets
written anyway. Today this is safe *only* because the Allow-form
(`#allow-form`, containing `#rule-pattern-input`) is `display=False` until
the Allow button — which *is* really `disabled=True` until `all_verified()`
— is clicked. The button's disabled state is what's tested and cited as "a
real Textual `disabled`, not just a visual hint" (STORY-1604's own AC) — but
the actual safety property depends on the field being *unreachable*, not on
the button per se.

`on_input_submitted` (`monitor_app.py:361-367`) already calls
`self.action_submit_allow()` directly whenever Enter is pressed in either
text input — completely independent of the Allow button's disabled state.
Today that's inert, because the input can't be focused (or even exist,
rendered) before Allow is clickable. **§22.4 makes the Pattern field visible
and focusable from the moment the review screen opens, before Verify has
ever run.** Pressing Enter in that field at that point calls
`action_submit_allow()` directly — which, as traced above, will write a
real Allow rule for a target that was **never scanned**, silently
bypassing the one property this project has repeatedly called out as its
core Nielsen #5 guarantee (default-deny, allow gated on verify — my own
consult praised this exact mechanism; STORY-1604's AC exists specifically
to protect it).

This is not a hypothetical: any operator's ordinary first move on this
redesigned screen (start typing a wider pattern, hit Enter out of habit) now
writes an unreviewed Allow rule.

```
REASON: §22.4 promotes the Pattern field to always-visible/focusable before
Verify runs, but the actual enforcement of "Allow requires Verify first"
lives entirely in the Allow button's own `disabled` state and the form's
old `display=False` gate — neither of which the Enter-key submit path
(`on_input_submitted` → `action_submit_allow()`) was ever gated by. Removing
the hidden-until-enabled form removes the thing that was actually doing the
enforcement; the button being disabled no longer protects the write path at
all, since Enter reaches `action_submit_allow()` directly.

FIX: `action_submit_allow()` itself must check `self._entry.all_verified(cache)`
and refuse to write (same `#allow-error` messaging path already used for a
bad-finding refusal) if false — enforced at the point of consequence, not
only at the button widget. This also closes the same gap for a future
caller that isn't a button at all, not just this specific Enter-key path.
```

## Verdict

**REJECTED**, single fixable issue — everything else in §22 is approved
as designed. Route back to Morpheus to add the `all_verified()` check inside
`action_submit_allow()` itself (§22.4), then re-submit for Gate 2. Not
asking for a redesign — the promoted-field layout and direct-submit
simplification are both still right, they just need the safety check moved
to where it's actually load-bearing now.

## Re-review (2026-08-03, same session)

Morpheus's fix: `action_submit_allow()`'s first line now checks
`self._entry.all_verified(ScanCache(self._cache_path))`, refuses via
`#allow-error` if false — enforced inside the method any caller reaches
(Enter-key path, the Allow button, or any future caller), not conditioned
on which widget triggered it. This is the correct fix: it closes the gap at
its actual source (the write action having no guard of its own) rather than
trying to patch every possible UI path into it individually. Button
`disabled` state is correctly kept as the visible first line of defense —
this isn't either/or, it's defense in depth, same shape as this project's
other doubled guards (e.g. `PolicyRule.__post_init__` validating at
construction *and* `action_submit_allow` catching `PolicyConfigError` at
the call site).

**APPROVED.** Handed to Mouse for phase planning.
