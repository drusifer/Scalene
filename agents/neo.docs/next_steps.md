# Next Steps

## Immediate Next Action
Handed off to Trin: `*qa uat` on the "copyable system messages" feature (`hook_adapter.py` mask-suggestion + false-positive fix, `tests/test_hook_adapter.py`, `tests/test_onboard_suggestion_e2e.py`). Then Morpheus review. Then Smith `*user test` (required per the `*impl` chain's UX gate — this phase changes a developer-facing `systemMessage`/audit-log shape, and Smith already committed in her own `next_steps.md` to testing it).

## Waiting On
Trin (UAT) → Morpheus (review) → Smith (UX test against the real message).

## Planned Work
- [ ] If Trin/Morpheus/Smith find gaps: fix in this same phase, don't restart
- [ ] Not part of this task, still open from earlier this session: `install-hooks` doesn't scaffold a starter `scalene_policy.yaml` (fresh installs default to mask-everything) — still unaddressed, not yet a formal task

---
*Last updated: 2026-07-09*
