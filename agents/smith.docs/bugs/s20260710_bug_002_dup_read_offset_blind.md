# Bug 2026-07-10-002: `AP-DUP-READ` doesn't account for offset/content-change

**Severity**: P4 — Minor signal-to-noise problem, lower priority than bug 001
**Filed by**: Smith
**Route to**: Neo (script bug in `agents/tools/trace_annotate.py`)

---

## Reproduction

Run `make judge-trace DATE=2026-07-10 FORMAT=md`, grep for `AP-DUP-READ`. Nearly all 12 instances are `Read` calls on the same file at *different* `offset`/`limit` values while the file is under active edit (e.g. `monitor_app.py`, `test_monitor_app.py`, `task.md`), not re-reads of unchanged content.

## Expected

The rule's intent (per its own description): "Same file Read 3+ times in one session **without the file changing** between reads" — i.e. catch wasteful re-reads of static content.

## Actual

`annotate_events()` counts `Read` calls by `file_path` alone (`read_seen[path] += 1`) and flags on the 3rd+, regardless of `offset`/`limit` differing or an `Edit`/`Write` having landed on that path between reads.

## Root Cause

No offset/edit-interleaving check in the counting logic.

## Recommended Fix

Only count a repeat as "duplicate" if either (a) the `offset`/`limit` pair matches a prior read of the same path, or (b) no `Edit`/`Write` to that path occurred between the two reads. Reading different sections of a large file, or re-reading after an edit to verify the result, are both legitimate and shouldn't count toward the threshold.
