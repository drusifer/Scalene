# `*user test E17` — Sprint-Close End-to-End (mandatory)

Not a phase gate — confirming the whole epic coheres as one continuous
real journey, not just each phase individually correct. Same standard as
every prior epic's sprint-close pass (E14/E15/E16): the real
`scalene-guard` hook + the real `MonitorApp`, nothing mocked.

## What I ran

Wrote `TestE17EndToEndUserJourney` (supersedes the retired
`TestE16EndToEndUserJourney`, which touched widgets this epic removed) —
one continuous scenario: a real blocked call through the real hook →
queue screen (session line, status strip, queue row, attention signal) →
Enter opens the real review → match-expr fields + live Matches? visible
before Verify → Verify → Allow (single click, writes directly) → real
retry through the hook now succeeds → a **second, fresh** `MonitorApp`
instance (genuinely restarting `scg monitor`, not reusing in-memory state)
opens the Rules screen and shows the rule that was just written.

## What this confirms that no single phase's own gate did alone

- The queue (Phase 1), status strip (Phase 2), and review screen (Phase 3)
  compose correctly in one real session — not just individually correct
  against their own phase's narrower tests.
- The rule Allow writes in the review screen is the *same* rule the Rules
  screen reads back, through a real process restart — no drift between the
  write path (`ReviewScreen.action_submit_allow`) and the read path
  (`RulesScreen._load_rules`), both going through `PolicyConfig.from_yaml`
  independently.
- The full loop this epic exists to shorten — block → see it → act on it →
  agent retries and succeeds — still holds end to end after 4 phases of
  real structural change to how it's presented.

## Documentation checked against the real shipped app

Re-read `docs/MONITOR_GUIDE.md` cold, the way a new user would, and
compared every claim against the real code: no session-picker language
survives, the "click Allow to reveal the form" flow is gone (replaced with
the always-visible-fields description), the Rules screen section matches
the real `k`/`j`/`Esc` bindings. Screenshots are real (`make screenshots`
output), not redrawn by hand.

## Retro input, carried to `*sprint retro`

- This sprint's real findings all came from **actually running the
  software**, not code review: the Gate 2 architecture bypass (traced by
  reading the real `on_input_submitted` path, not assumed safe from the
  design doc), the status-strip CSS dock-order assumption (caught by a
  `widget.region` geometry test, not a screenshot eyeball), and the
  `refresh_queue()` staleness bug (caught by Morpheus actually re-reading
  the diff, not rubber-stamping "looks fine"). Worth naming as validation
  that this project's "run it for real" standard isn't ceremony — three
  separate real bugs this sprint, each caught by a different kind of real
  check (code trace, geometry test, diff read), not the same technique
  three times.
- Mid-session process note (not a code finding): a destructive `git
  checkout -- <file>` used to revert a 4-line temporary test patch instead
  reverted the entire uncommitted Phase 1 implementation in that file.
  Fully recovered from memory of the session's own edits, no data lost,
  but it cost real time and was avoidable — the fix should have been a
  direct `Edit` reverting just the temporary lines, never a destructive
  git command for a change that specific.

## Verdict

**PASS.** No new bugs found in this integrated pass — every phase's own
gate already did its job. Handing to all personas for `*sprint retro`.
