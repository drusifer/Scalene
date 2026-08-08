# E18 Retro Backlog

Compiled from all 6 persona retro posts (`agents/CHAT.md`, 2026-08-07). No Tank retro — no infra surface touched.

1. **Decision-undo/redo (Verify/Allow/Deny) — explicitly deferred, not built this epic.** User was asked directly and chose to skip it, since Allow/Verify write to shared files (`scalene_policy.yaml`/`scan_cache.json`) that something else may have already relied on by the time an "undo" would fire. Needs its own design pass (Neo/Morpheus) on safe unwind semantics before it's storied.
2. **The armed/confirm idiom (skip-all, rule-delete) is now used twice, independently implemented per screen** — `docs/ARCHITECTURE.md` §23.8 already flags this as worth extracting into a shared helper if a 3rd destructive action appears in a future epic. Not urgent at 2 instances (this project's own established preference against premature abstraction), but worth watching.
3. **The `decide_access` "clean session's first touch gets a free pass" mechanic is a recurring test-design trap** (Trin, Smith) — bit 2 different people writing E18 tests independently (the `update_rule`/`delete_rule` unit tests, then the sprint-close e2e test), even after the first catch. Worth a durable lesson entry (`agents/oracle.docs/lessons.md`): any test asserting a *block* outcome as proof a specific rule/edit mattered must use an already-tainted session (`trust="low"` state file), not a fresh one — a fresh session's first touch can be allowed by the free-pass alone, independent of rule state.
4. **Origin pattern worth watching**: a support/diagnostic question ("why do I see 11K pending reviews") surfaced a real, separate product gap (no backlog-handling mechanism) rather than being purely a one-off bug. Oracle flagged this as a pattern worth re-recognizing in future support investigations, not assuming every support question is self-contained.

## Not carried forward (already resolved this epic)
- All 5 of Cypher's own open questions to Morpheus (aggregation identity, cache-consistency bookkeeping, sort-vs-index-stability, edit-form widget shape, write-helper convention) — resolved during architecture, held up through implementation with no reversal.
