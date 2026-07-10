# Next Steps

## Immediate Next Action
Sprint 2's implementation stage (all 3 phases) is fully complete. No active Morpheus task until sprint close begins.

## Waiting On
Nothing right now.

## Planned Work
- [ ] Worth carrying forward to a retrospective: this sprint showed three times that actually *running* the software (not just reading it) surfaces real bugs a code-review-only pass would miss — Phase 2's cursor bug (Smith), Phase 3's crash paths (me, via deliberately adversarial inputs), Phase 3's focus-loss bug (Smith again). Every gate earned its keep this sprint — none were a formality.
- [ ] When sprint close reaches Oracle's groom step: no outstanding architecture debt beyond what's already logged (`_suggest_onboard_command()` relocation, deferred until a 2nd harness adapter exists)
- [ ] If/when a second harness adapter is built: relocate `_suggest_onboard_command()` out of `hook_adapter.py` into the policy-engine layer (see context.md finding) — cheap now, real duplication cost later if forgotten
- [ ] If a retrospective happens: worth carrying forward — (1) strict TDD test-first, (2) `make <target>` as the only way to run build/env tasks, (3) don't trust a persona's own stated numbers/status without independently recounting/re-checking

---
*Last updated: 2026-07-10*
