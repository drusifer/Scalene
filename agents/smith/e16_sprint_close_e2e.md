# `*user test E16` — sprint-close end-to-end (2026-07-23)

Wrote `tests/test_monitor_app.py::TestE16EndToEndUserJourney` — the full
epic exercised as one continuous real scenario, not per-phase in
isolation. Same standard as E14/E15's sprint-close tests.

Journey covered, all through real code (real `pre_tool_use`, real
`MonitorApp`, real `Pilot` clicks, real `PolicyConfig.from_yaml` reload —
nothing mocked):

1. A genuinely blocked call (tainted session, unrecognized file) — its
   `reason` carries STORY-1601's differentiated retry guidance ("wait" +
   "retry"), not a bare denial.
2. `scg monitor`: the 2 real builtin scanners appear idle (STORY-1602);
   the block appears in the tagged event log as `[WAIT]` (STORY-1603); the
   title picks up "1 pending review" (attention signal).
3. Opening the review (`r`): the dashboard shows the real blocked
   `tool_input` and the real target with `"not yet scanned"` status
   (STORY-1604).
4. Verify runs a real scan; Allow becomes genuinely un-disabled.
5. Allow's form is pre-filled (`public`/`allow`); Submit writes a real
   `mode: allow` rule to a real policy file (STORY-1605); the review
   dequeues and the title count drops back to zero.
6. The exact original call, retried through the real hook with a fresh
   `PolicyConfig.from_yaml()` reload, is now genuinely allowed.
7. That allow is itself visible in the monitor's tagged log as `[ALLOW]`
   on the next poll — confirms STORY-1603's full-stream requirement
   end-to-end, not just for the block half.

`make test`: 439/439. Standalone re-run of the new test confirmed clean
and stable.

**Verdict: PASSED.** No new bugs found — every phase gate's own
real-verification standard held up when chained together, same as prior
sprints' sprint-close tests. Handed to all for `*sprint retro`.
