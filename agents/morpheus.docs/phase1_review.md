# Morpheus — Sprint 3 Phase 1 Review

**Date:** 2026-07-14
**Verdict:** REJECTED, round 1.

## Finding

`docs/GETTING_STARTED.md` hardcodes literal output — the mask literal string (`[MASKED_BY_POLICY_PROVENANCE_GUARD]`) and the exact `suggested_onboard_command` text (including its escaped regex) — as the doc's central proof that Scalene works. But `tests/test_getting_started_docs.py` only checks that certain terms appear *somewhere in the doc's prose*; it never actually runs the 3-call scenario and confirms that output is what's really produced.

If `MaskingEngine.MASK_LITERAL` or `_suggest_onboard_command()`'s format ever changes, this doc goes stale silently — `make test` stays green while the doc quietly lies. This is the same drift class as Sprint 2's two AC-text incidents (STORY-701's "timestamp" AC, STORY-702's placeholder wording) — both only caught mid-UAT by Trin, not by any test. The team's own Sprint 2 retro (Cypher, Trin) flagged watching for exactly this.

## Fix requested

Add an executable check to `tests/test_getting_started_docs.py` (or a new test) that calls `pre_tool_use`/`post_tool_use` directly — same pattern as `tests/test_hook_adapter.py` — replaying the doc's exact 3-call scenario (Read → PostToolUse → WebFetch) and asserting the real `updatedInput["prompt"]` equals `MaskingEngine.MASK_LITERAL`. This locks the doc's central claim into the test suite instead of just checking that words exist in prose.

## Gate Decision

Rejected. Back to Neo.
