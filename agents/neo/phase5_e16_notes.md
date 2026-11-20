# `*swe impl phase-5` — E16 Allow/Deny + Attention Signal (2026-07-23)

Full detail: `docs/ARCHITECTURE.md` §20.4/§20.5, `task.md` Sprint 10 Phase 5.

- Deny/Allow buttons added to `ReviewScreen`. Deny dismisses with no write.
  Allow is genuinely `disabled=True` (Textual's own disabled state, not
  just visual) until `ReviewEntry.all_verified`.
- Allow reveals an inline form (sensitivity/mode `Input` widgets, pre-filled
  `public`/`allow`). Submit constructs one `PolicyRule` per target with
  `pattern=re.escape(identity)` — `onboard.py`'s own existing default,
  reused verbatim, not a new derivation — and writes via `onboard.
  write_rule` (renamed from `_write_rule`, now a public function since the
  dashboard is a second real caller).
- Submit reuses the same `BLOCKED_LABELS` guard `_onboard_resource` already
  applies (also renamed public), checked against the result Verify already
  cached — no re-scan inside Allow.
- Attention signal on any new queued block: `self.bell()` + `self.title`
  gets a live pending-review count, verified against the actually-installed
  Textual version's real `App.bell()`/`App.title` API (not assumed).
- `MonitorApp._on_review_resolved` dequeues on a real resolution (Deny, or
  a successful Allow submit) via `push_screen(..., callback=...)`; a plain
  Escape leaves the entry queued (resolves with `False`).

**Real bug found and fixed while writing tests, not in production code**:
the default 80×24 headless test viewport clipped the Allow form (below the
button row) out of the visible render area — clicks at that region were
silent no-ops, not errors, which is why it looked like the dismiss callback
wasn't firing. Root-caused by reading Textual's own `screen.py` (`dismiss()`
schedules its callback via `requester.call_next(...)`, not synchronously)
and confirming render clipping was the real cause, not more waiting — fixed
tests with `size=(100, 50)`, not extra sleeps.

`make test`: 434/434, confirmed across 2 consecutive clean runs.
