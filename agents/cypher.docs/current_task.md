# Current Task

**Status:** Sprint 4 (E10) stories drafted, approved at both Gate 1 and Gate 2, architected (Morpheus §13), phased (Mouse), and plan LOCKED (Morpheus). No Cypher action pending — Sprint 4 is in implementation (Neo, Phase 1, not yet started as of this state save).
**Assigned to:** N/A (no active Cypher task)
**Started:** 2026-07-14
**Completed:** 2026-07-14 (planning stage)

## Task Description
Direct user design session (2026-07-14) identified a real gap in the just-shipped URI-scheme onboarding model (commit `df8eb08`): a rule's one-time scan of a representative `target` can vouch for an unbounded, never-rescanned future set matched by `pattern`. User specified a replacement in detail through conversation: named regex captures, per-scanner-type autonomous resource identification, a 24h mtime-keyed scan cache with background refresh, fail-safe-until-first-scan for never-seen resources, and fatal-non-zero-exit reserved for scanner-machinery failures (not scan findings). Wrote as E10 — Extensible Scanner Registry & Resource Verification — 5 stories (STORY-1001 through 1005) in `docs/USER_STORIES.md`, updated `docs/PRD.md` epic table + Sprint 4 goals, updated `task.md` header (Sprint 3 status was stale — implemented but never formally closed; noted honestly rather than silently marking it done).

## Progress
- [x] Captured the full design (already hashed out in conversation with the user, not something Cypher had to invent) as 5 testable stories.
- [x] Left one explicit open question for Morpheus in the epic's origin note: does E10's autonomous scanning *replace* the `scg onboard`/single-`allowlist` model, or coexist with it? Deliberately did not pre-decide this myself — it's an architecture call, not a product-scope call.
- [x] STORY-1004 explicitly flags that Morpheus must enumerate exactly which failure classes stay fail-safe-exit-0 vs. become fatal-non-zero, so the new "fatal" exception doesn't quietly widen past what the user specified (scanner-machinery failures only, never scan findings).
- [x] Handed off to Smith for Gate 1 review — **approved**.
- [x] Morpheus architected (§13, full-replacement decision), Smith Gate 2 — **approved**.
- [x] Mouse phased (5 phases, `task.md`), Morpheus plan review — **LOCKED**, handed to Neo.

## Blockers
None.

## Oracle Consultations
None yet.

---
*Last updated: 2026-07-14*
