# Smith — Sprint 4 Gate 1 Review (E10: Extensible Scanner Registry & Resource Verification)

**Date:** 2026-07-14
**Stories reviewed:** STORY-1001 through STORY-1005
**Verdict:** APPROVED, two non-blocking notes.

## Review

All five stories have testable, user-facing acceptance criteria, and — unusually for this project — the epic's origin note already captures a real, previously-shipped defect with concrete reasoning, not a speculative nice-to-have. STORY-1003 in particular has the clearest AC in this whole document: it enumerates all three cache states (none / fresh / expired) and pins down the exact behavior for each, which is exactly the kind of precision that prevented ambiguity in past UAT passes.

## Non-blocking notes

**1. First-sighting friction (STORY-1003).** Every genuinely new resource — a file never read before, a domain never called before — will be masked or blocked on its very first appearance, always, until a scan completes and produces a cached label. This is the *correct* security behavior (no implicit trust for the unknown), but it's a real, repeated UX cost: a legitimate brand-new internal API endpoint or a freshly-created file under an already-allowlisted directory will get friction on first contact even though a human would immediately recognize it as fine. Whoever implements this should make sure the mask/block message for a "no cache entry yet" call reads differently from "known bad" — e.g. "not yet verified" rather than a generic untrusted message — so the user understands this is a first-contact wait, not a rejection. Not blocking Gate 1; flagging for Neo/Morpheus to carry into the message design.

**2. "Fatal" needs a concrete, plain-language failure mode before implementation (STORY-1004).** The AC correctly requires distinguishing scan-findings (exit 0) from scanning-machinery failures (exit non-zero), but doesn't yet say what the user actually *sees* when that happens. Given this project's established standard (no raw exceptions, ever — `secrets_scan.py`'s error-translation layer, `onboard.py`'s `OnboardError`), the fatal path needs the same treatment: a clear stderr message, and ideally a specific exit code chosen deliberately against Claude Code's real hook contract (recall the `hookSpecificOutput` research from the schema-fix work — a non-zero exit's exact effect on the harness should be verified, not assumed, same lesson as last time). Flagging for Morpheus's architecture step, not blocking here.

## Gate Decision

Approved. Proceeding to Morpheus for architecture — including the open replace-vs-coexist question Cypher flagged.
