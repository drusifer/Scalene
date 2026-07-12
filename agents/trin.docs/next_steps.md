# Next Steps

## Immediate Next Action
Sprint 2 fully closed and launched (see `task.md`). `*qa judge session` (revised) loop also closed, TES=98. No active Trin task — awaiting next user direction (Sprint 3 scope, or further judge/verification work).

## Waiting On
Nothing right now.

## Planned Work
- [ ] **New, from today's judge loop**: for every future `*qa uat`/`*qa test` phase sign-off, run `make judge-trace DATE=<today>` first and note anything real in the handoff (see `agents/trin.docs/SKILL.md` Test Workflow step 4) — this is now a required gate step, not optional.
- [ ] Next `*qa judge session` run: check whether that new checkpoint actually reduced real `make test|tail` / via-bypass counts vs. today's baseline (39 and 13 respectively) — this is the real test of whether Bob's 2026-07-10 fix worked, not just whether the mechanism exists.
- [ ] Sprint 1's old open items (AC-text staleness, Smith retroactive test) are resolved — see `task.md`/CHAT.md 2026-07-10 sprint-close entries.

---
*Last updated: 2026-07-10*
