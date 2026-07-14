# Smith — Sprint 4 Gate 2 Review (E10 architecture, §13)

**Date:** 2026-07-14
**Verdict:** APPROVED, two follow-up watch-items (not blocking).

## Review against my Gate 1 notes

**Fatal-exit note: fully addressed.** §13.5 draws the fail-safe-exit-0 vs fatal-exit-nonzero line precisely (scanning machinery failure only, never a scan finding), requires the same plain-language-message standard as the rest of this codebase, and explicitly tells Neo to verify the real exit code against Claude Code's actual hook contract rather than assume it — exactly what I asked for.

**First-sighting message note: addressed at the behavior level, not yet at the copy level.** §13.3's table correctly specifies that a never-scanned resource gets today's fail-safe default with zero added latency — the *behavior* is right. But the architecture doesn't yet say whether the resulting mask/block message text actually reads as "not yet verified" versus a generic untrusted message. This is a copy/UX detail reasonable to leave to implementation, but I want to personally verify it at UAT — not just trust that it "probably" reads right.

## Two non-blocking watch-items for implementation/review

1. **Perf NFR re-verification.** Resource `identify()` now runs on every tool call (before any cache lookup), and a cache lookup is a locked JSON file read, also on every call. Both are probably fine, but "probably fine" isn't how this project treats the <15ms NFR — `tests/test_performance.py` needs to actually re-pass with this in the hot path, not be assumed compatible because the individual pieces sound cheap.
2. **Concurrent-first-sighting dedup.** Not specified: if the same never-cached resource is hit by several rapid calls before its background scan completes, does that spawn N redundant background scans? Not a blocker, but worth Morpheus's review catching it if Neo's implementation doesn't handle it, rather than it surfacing later as a real bug the way Sprint 2 Phase 3's crash paths did.

## Gate Decision

Approved. Proceeding to Mouse for phase breakdown.
