# Sprint 4 Phase 2 Review — Latency Finding (2026-07-14)

## Verdict
Phase 2 (`scan_cache.py` + `cache_refresh_worker.py`) **APPROVED** on its own scope — functionally correct, matches §13.3's literal key formula, well-tested (195/195), no orphaned processes (Trin independently confirmed via `ps`), dedup holds under real cross-process concurrency (Trin's `ProcessPoolExecutor` test).

## The finding
§13.3 (my own architecture, written earlier this sprint) claims the "new resource" cache-lookup path is "identical to today's fail-safe-default behavior... zero-latency" and is the core justification for why this epic isn't a regression risk. I personally measured this rather than trusting the claim, and it does not hold as implemented:

- `refresh_if_needed()` on a never-cached resource: **~6.6ms avg / ~16ms max per call**
- Isolated the cause to `subprocess.Popen()`'s own spawn cost in a fire-and-forget pattern (not waiting between spawns) — reproduced the *same* ~3.6ms avg / ~19ms max using a trivial no-op command instead of the real worker script, ruling out worker-script complexity as the cause. This is real process-creation cost in this environment, not a measurement artifact.

## Why it matters
The existing hot-path NFR is <15ms total for `pre_tool_use`/`post_tool_use` (Trin's Sprint 1 informal baseline: ~6ms/call for the pre-Sprint-4 code). Adding ~6-16ms for a *single* never-seen resource could consume most or all of that budget by itself. A single tool call can identify *multiple* new resources (e.g., a `Bash` command containing 2 file paths + 1 URL = 3 separate spawns), which would compound the cost further.

This is not a brand-new surprise — Smith's Gate 2 watch-item and task.md's Phase 3 task 3.4 ("re-verify <15ms NFR... not assumed compatible") already flagged this as a risk to check. This finding turns that from "flagged but unverified" into "confirmed and quantified," which changes Phase 3 from *verify it's probably fine* into *this needs an actual design decision before wiring into the hot path*.

## Options (not yet decided — this is what needs your input)
1. **Accept the added latency, revise the NFR/architecture claim honestly.** Simplest path, but changes what "no regression" means for this epic — worth being explicit about rather than letting the perf test just fail unexpectedly during Phase 3.
2. **Redesign the spawn to be cheaper.** E.g., batch multiple never-seen resources from one call into a single spawn instead of one-per-resource; investigate whether a lower-level detach mechanism (vs. `subprocess.Popen`) meaningfully reduces the per-call cost in this environment.
3. **Decouple the spawn from the synchronous `pre_tool_use` path entirely.** E.g., only ever write a lightweight "needs scan" marker synchronously (fast, no subprocess), and let something less latency-sensitive (a session-scoped background process, or `post_tool_use`) actually trigger the scan.

## Non-blocking note (found during the same review)
`cache_refresh_worker.py`'s `try/except` wraps `scanner.scan()` but not the subsequent `ScanCache.put()` call — confirmed live with a mocked `OSError`, the exception propagates uncaught out of the worker's `main()`. Bounded impact: this is a detached background process, so its crash never reaches the parent's already-returned response. Practical effect is just that the affected resource sits in its 5-minute pending-reservation window before the next lookup retries it. Worth a one-line fix (wrap `put()` too) whenever Phase 3/4 next touches this file — not blocking Phase 2's approval.
