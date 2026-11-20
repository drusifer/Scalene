# Bug S1-001: `Skill(make)` invoked twice in one session

**Severity**: P3 — Token waste only, no functional impact
**Filed by**: Smith
**Route to**: Bob (prompt/skill guidance, not a code bug)

---

## Reproduction

During `/bloop *impl Sprint 1` (Phase 1), the agent:
1. Called `Skill(make-discover)`, then `Skill(make)` with args `setup` — correct, first load of the session.
2. Later in the same session (Phase 1 self-validation), called `Skill(make)` again with args `test`.

## Expected

Per `agents/skills/bloop/SKILL.md` rule #6 ("No Sub-Skill Re-Invocation"): "Do NOT call `Skill(make, ...)` or `Skill(chat, ...)` more than once per session. Each call reloads the full SKILL.md body unnecessarily. After the first load, run `make <target>` ... via the Bash tool directly."

## Actual

`Skill(make)` was invoked a second time, reloading the full skill body (~a few hundred tokens) for no benefit — the agent already had the skill's guidance in context from the first load.

## Root Cause

Not a missing-documentation problem — the rule is already stated explicitly and unambiguously in `agents/skills/bloop/SKILL.md`. This was a momentary lapse in recalling/applying an already-known rule mid-session, not a gap in the skill text itself.

## Impact

Minor token waste (one redundant skill-body load). No functional or correctness impact — every `make` invocation itself still worked correctly.

## Recommended Fix

Since the rule text was already correct and explicit, more prose is unlikely to help. Bob should add a concrete, concrete-consequence anchor (referencing that this actually happened in Sprint 1) rather than additional abstract rule text — anchored examples tend to improve recall better than restating a rule that was already stated once and still missed.
