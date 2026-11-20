# Morpheus — `*lead review phase-3` — Sprint 9 (E15) — 2026-07-21

## Architecture fit
Confirmed myself: `composite_check()` is only ever invoked from `scan_worker.py::_scan_reputation`, which only ever runs inside `subprocess_isolation.run_scanner()`'s spawned child (`SCALENE_BYPASS=1` set) — the network call genuinely runs inside the existing isolation boundary, no new mechanism introduced. `_query_urlhaus()` isolating the actual HTTP call into its own function, mockable in-process, is good design regardless of the env-var story below.

## The env-var test-gate
A production module branching on an env var purely for test hermeticity is something I'd normally push back on as a smell — but the justification is real and specific, not general-purpose "test mode" creep: `scan_worker.py` runs in a genuinely separate OS process (STORY-601's own isolation requirement), so no in-process mock can reach it, and the alternative (no gate at all) is what Trin's timing check proved actually happens — every test touching a URL resource makes a real live call to a third party. Scoped tightly (one env var, one call site, checked once), documented thoroughly, and off by default in the shape that matters (unset in production). Accepting this as the right trade-off given the constraint, not a pattern to generalize elsewhere without the same justification.

## Trin's found gap
Confirmed `test_scan_cache.py`'s direct `refresh_if_needed()` calls now correctly guarded. Good independent catch — Neo's file list was reasonable but incomplete, and Trin's broader grep (by call-site pattern, not just URL-string matching) is the right way to have found it.

## Verdict

**APPROVED**, contingent — this phase does not close until Tank reviews (network egress, no-API-key claim, rate-limit/volume behavior). @Tank *devops review phase-3, per Cypher's original story flag and standing protocol (Tank sequenced last).
