# Next Steps

## Immediate Next Action
Sprint 2's implementation stage (all 3 planned phases) is fully complete. No active Neo task until sprint close begins or a new phase is scoped.

## Waiting On
User to trigger sprint close (Stage 3) or further work.

## Planned Work
- [ ] `_suggest_onboard_command()` relocation out of `hook_adapter.py` still deferred until a 2nd harness adapter exists — no action needed now
- [ ] `install-hooks` still doesn't scaffold a starter `scalene_policy.yaml` — unaddressed, not yet a formal task
- [ ] This is Sprint 2's last planned phase (`task.md` only has 3) — if all gates pass, next is Stage 3 sprint close (Oracle groom → Smith end-to-end test → retro → Cypher launch), per `/sprint`'s skill definition
- [ ] Not part of this task, still open: `install-hooks` doesn't scaffold a starter `scalene_policy.yaml`; the odd audit-log-vs-actual-execution masking discrepancy noticed during Phase 1 — neither blocking, neither actioned yet
- [ ] Not part of this task, still open from earlier: `install-hooks` doesn't scaffold a starter `scalene_policy.yaml` (fresh installs default to mask-everything) — still unaddressed, not yet a formal task
- [ ] Also noticed during Phase 1 work: this session's `scalene-guard` hook computes/logs a "mask" decision for nearly every tool call (real audit.log entries), but the actual tool execution never appeared to receive the masked `updatedInput` — worth a closer look at some point, not blocking

---
*Last updated: 2026-07-10*
