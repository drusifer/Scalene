# `*user approve` Phase 5 — mandatory gate (2026-07-23)

Per the standing no-ad-hoc-verification rule (reinforced this same session,
`feedback_no_adhoc_bash_verification.md`), verified through the real
repeatable suite rather than a scratch script: re-ran `test_
allow_writes_a_real_rule_and_a_retry_of_the_same_call_is_then_allowed`
standalone and read it end-to-end.

It drives real Textual `Pilot` clicks through the actual UI (Verify →
Allow → Submit), calls the real `pre_tool_use` hook twice — once before
(confirms the original call is genuinely denied), once after (confirms the
identical call is now allowed) — and reloads a real `PolicyConfig.
from_yaml()` from the just-written policy file in between. Nothing mocked.

This is the epic's core promise (block → review → Verify → Allow → retry
succeeds) and it's real, not simulated. Additional real checks confirmed:

- Allow is genuinely `disabled=True` (Textual's real disabled state, not
  just a visual hint) until every target's Verify completes.
- The `mode=block` override and multi-target Allow both write real rules,
  confirmed by Trin's 2 new tests this phase.
- Attention signal (`bell()` + title pending-count) verified against the
  actually-installed Textual API.
- Deny and a plain Escape are correctly distinct (Deny dequeues + writes
  nothing; Escape leaves the review queued).

**APPROVED.** This closes E16's core interactive flow — the highest-weight
gate in this epic, same standard as prior mandatory onboard-flow gates.
