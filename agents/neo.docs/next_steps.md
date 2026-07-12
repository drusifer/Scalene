# Next Steps

## Immediate Next Action
Sprint 2 fully closed+launched, and the `*qa judge session` (revised) loop that followed is also closed (TES=98). No active Neo task — awaiting next user direction.

## Waiting On
Nothing right now.

## Planned Work
- [ ] Bob's `agents/neo.docs/SKILL.md` update (2026-07-10) added a real enforcement note: Trin's UAT gate now runs `make judge-trace` before signing off a phase. Expect real `AP-MAKE-PIPE`/`AP-RAW-VENV`/`AP-VIA-GREP` flags to actually surface during Sprint 3's UAT passes — that's the mechanism working as intended, not a regression.
- [ ] `_suggest_onboard_command()` relocation out of `hook_adapter.py` still deferred until a 2nd harness adapter exists — no action needed now
- [ ] `install-hooks` still doesn't scaffold a starter `scalene_policy.yaml` (fresh installs default to mask-everything) — unaddressed, not yet a formal task
- [ ] Unexplained from Phase 1: `scalene-guard` computes/logs a "mask" decision for nearly every tool call, but the actual tool execution never appeared to receive the masked `updatedInput` — worth a closer look at some point, not blocking

---
*Last updated: 2026-07-10*
